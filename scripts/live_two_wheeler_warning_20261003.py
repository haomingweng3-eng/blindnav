"""End-to-end two-wheeler early-warning replay/demo.

This candidate pipeline reads a video or webcam, runs the broad two-wheeler
detector with BoT-SORT, applies a COCO person-overlap gate, and feeds the
tracks into the route-risk prototype.  It writes an annotated video and a
candidate-only JSON report.  It does not edit labels, train weights, or enable
safety alerts.
"""

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path


def _overlap_in_box(box, person):
    x1 = max(box[0], person[0])
    y1 = max(box[1], person[1])
    x2 = min(box[2], person[2])
    y2 = min(box[3], person[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area = max(1.0, box[2] - box[0]) * max(1.0, box[3] - box[1])
    return inter / area


def run(args):
    import cv2
    from ultralytics import YOLO

    from alert_arbiter import AlertArbiter
    from feedback_policy import feedback_for
    from risk_engine import LVL_HIGH, LVL_MID, LVL_NAME, TrackState

    source = int(args.source) if str(args.source).isdigit() else args.source
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        raise RuntimeError(f"cannot open source: {args.source}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    source_fps = float(cap.get(cv2.CAP_PROP_FPS) or args.input_fps or 30.0)
    if width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError(f"invalid source dimensions: {args.source}")

    detector = YOLO(args.two_wheeler_model)
    person_detector = YOLO(args.person_model)
    writer = None
    if args.output_video:
        out_path = Path(args.output_video)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(
            str(out_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            source_fps,
            (width, height),
        )
        if not writer.isOpened():
            cap.release()
            raise RuntimeError(f"cannot open output: {out_path}")

    scale = 640.0 / max(width, height)
    inference_scale = min(1.0, args.inference_long_side / max(width, height))
    inference_width = max(1, int(round(width * inference_scale)))
    inference_height = max(1, int(round(height * inference_scale)))
    states = {}
    arbiter = AlertArbiter(cooldown_frames=args.alert_cooldown_frames)
    cached_people = []
    alerts = []
    frame_count = 0
    detections = 0
    passed_gate = 0
    start = time.perf_counter()
    timings = []
    stages = defaultdict(list)
    detection_records = []
    colors = {0: (120, 120, 120), 1: (0, 190, 255), 2: (0, 120, 255), 3: (0, 0, 255)}

    try:
        while True:
            decode_tick = time.perf_counter()
            ok, frame = cap.read()
            decode_ms = (time.perf_counter() - decode_tick) * 1000.0
            if not ok:
                break
            stages["decode"].append(decode_ms)
            frame_idx = frame_count
            frame_count += 1
            tick = time.perf_counter()
            inference_frame = frame
            if inference_scale != 1.0:
                inference_frame = cv2.resize(
                    frame,
                    (inference_width, inference_height),
                    interpolation=cv2.INTER_AREA,
                )
            stages["resize"].append((time.perf_counter() - tick) * 1000.0)
            track_tick = time.perf_counter()
            results = detector.track(
                inference_frame,
                persist=True,
                tracker=args.tracker,
                conf=args.two_wheeler_confidence,
                classes=[args.two_wheeler_class_id],
                imgsz=args.imgsz,
                device=args.device,
                verbose=False,
            )[0]
            stages["detector_tracker"].append(
                (time.perf_counter() - track_tick) * 1000.0
            )

            if args.person_stride <= 1 or frame_idx % args.person_stride == 0:
                person_tick = time.perf_counter()
                person_result = person_detector.predict(
                    inference_frame,
                    conf=args.person_confidence,
                    classes=[0],
                    imgsz=args.imgsz,
                    device=args.device,
                    verbose=False,
                )[0]
                cached_people = [
                    {
                        "box": [
                            float(value) / inference_scale for value in box
                        ],
                        "confidence": float(confidence),
                    }
                    for box, confidence in zip(
                        person_result.boxes.xyxy.cpu().tolist(),
                        person_result.boxes.conf.cpu().tolist(),
                    )
                ]
                stages["person_detector"].append(
                    (time.perf_counter() - person_tick) * 1000.0
                )

            vis = frame.copy()
            boxes = results.boxes
            if boxes.id is not None:
                for box, confidence, track_id in zip(
                    boxes.xyxy.cpu().tolist(),
                    boxes.conf.cpu().tolist(),
                    boxes.id.cpu().tolist(),
                ):
                    # Tracking and person detection run on the resized frame;
                    # restore coordinates before applying overlap and drawing.
                    box = [float(value) / inference_scale for value in box]
                    detections += 1
                    track_key = f"track_{int(track_id)}"
                    people_inside = [
                        person
                        for person in cached_people
                        if person["confidence"] >= args.person_confidence
                        and _overlap_in_box(box, person["box"])
                        >= args.person_min_overlap
                    ]
                    gate_pass = bool(people_inside)
                    if args.detections_log:
                        detection_records.append(
                            {
                                "frame": frame_idx,
                                "track_id": track_key,
                                "confidence": float(confidence),
                                "x1": box[0],
                                "y1": box[1],
                                "x2": box[2],
                                "y2": box[3],
                                "person_gate": gate_pass,
                                "person_confidence": max(
                                    (p["confidence"] for p in people_inside),
                                    default=0.0,
                                ),
                            }
                        )
                    if gate_pass:
                        passed_gate += 1
                    if track_key not in states:
                        states[track_key] = TrackState(
                            track_key,
                            "two_wheeler_candidate",
                            looming_threshold=args.looming_threshold,
                            corridor_half_width=args.corridor_half_width,
                            entry_lateral_threshold=args.entry_lateral_threshold,
                            entry_confirm_frames=args.entry_confirm_frames,
                            prediction_frames=args.prediction_frames,
                            approach_vertical_threshold=args.approach_vertical_threshold,
                            fps=source_fps,
                            reference_fps=30.0,
                            min_approach_area=args.min_approach_area,
                            route_blocked_warning=args.route_blocked_warning,
                            predictive_urgent=args.predictive_urgent,
                            early_urgent_time_to_close_s=args.early_urgent_time_to_close,
                            coordinate_width=width * scale,
                            coordinate_height=height * scale,
                        )
                    state = states[track_key]
                    scaled_box = [value * scale for value in box]
                    state.update(scaled_box, frame_idx=frame_idx)
                    level, info = state.assess(frame_idx)
                    if not gate_pass:
                        level = 0
                    if level >= LVL_MID and gate_pass:
                        risk_band = (
                            "clear_approach" if level >= LVL_HIGH
                            else "possible_route_impact"
                        )
                        risk_band_name = "明显接近" if level >= LVL_HIGH else "可能影响路线"
                        candidate = {
                            "frame": frame_idx,
                            "track_id": track_key,
                            "cls": "two_wheeler_candidate",
                            "conf": round(float(confidence), 4),
                            "level": level,
                            "level_name": LVL_NAME[level],
                            "risk_band": risk_band,
                            "risk_band_name": risk_band_name,
                            "info": info,
                            "feedback": feedback_for(
                                level, "two_wheeler_candidate", info
                            ),
                            "person_gate": {
                                "passed": True,
                                "person_count": len(people_inside),
                            },
                            "candidate_only": True,
                            "human_confirmed": False,
                            "training_eligible": False,
                            "safety_alert_enabled": False,
                        }
                        if arbiter.accept(candidate):
                            alerts.append(candidate)
                    if args.output_video:
                        color = colors.get(level, colors[0])
                        x1, y1, x2, y2 = [int(value) for value in box]
                        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 3)
                        label = (
                            f"2w {track_key} {LVL_NAME[level]}"
                            if gate_pass
                            else f"2w {track_key} no-rider"
                        )
                        cv2.putText(
                            vis,
                            label,
                            (x1, max(24, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.65,
                            color,
                            2,
                            cv2.LINE_AA,
                        )

            if args.output_video:
                write_tick = time.perf_counter()
                elapsed = time.perf_counter() - start
                live_fps = frame_count / elapsed if elapsed else 0.0
                cv2.putText(
                    vis,
                    f"candidate FPS {live_fps:.1f} frame {frame_idx}",
                    (12, 28),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.7,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )
                writer.write(vis)
                stages["video_write"].append(
                    (time.perf_counter() - write_tick) * 1000.0
                )
            timings.append((time.perf_counter() - tick) * 1000.0)
            if args.max_frames and frame_count >= args.max_frames:
                break
    finally:
        cap.release()
        if writer is not None:
            writer.release()

    elapsed = time.perf_counter() - start
    report = {
        "source": str(Path(args.source).resolve()),
        "frames": frame_count,
        "source_fps": round(source_fps, 3),
        "width": width,
        "height": height,
        "tracks": len(states),
        "detections": detections,
        "gate_pass_detections": passed_gate,
        "alerts": alerts,
        "alert_count": len(alerts),
        "elapsed_seconds": round(elapsed, 3),
        "processed_fps": round(frame_count / elapsed, 2) if elapsed else 0.0,
        "stage_timing_ms": {
            name: {
                "calls": len(values),
                "total": round(sum(values), 3),
                "mean": round(sum(values) / len(values), 3),
            }
            for name, values in stages.items()
        },
        "parameters": {
            "two_wheeler_model": str(Path(args.two_wheeler_model).resolve()),
            "person_model": str(Path(args.person_model).resolve()),
            "tracker": args.tracker,
            "device": args.device,
            "imgsz": args.imgsz,
            "inference_long_side": args.inference_long_side,
            "inference_width": inference_width,
            "inference_height": inference_height,
            "two_wheeler_confidence": args.two_wheeler_confidence,
            "person_confidence": args.person_confidence,
            "person_min_overlap": args.person_min_overlap,
            "person_stride": args.person_stride,
            "looming_threshold": args.looming_threshold,
            "min_approach_area": args.min_approach_area,
            "approach_vertical_threshold": args.approach_vertical_threshold,
            "route_blocked_warning": args.route_blocked_warning,
            "predictive_urgent": args.predictive_urgent,
            "early_urgent_time_to_close": args.early_urgent_time_to_close,
            "corridor_half_width": args.corridor_half_width,
        },
        "candidate_only": True,
        "human_confirmed": False,
        "training_eligible": False,
        "safety_alert_enabled": False,
    }
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    if args.detections_log:
        detection_path = Path(args.detections_log)
        detection_path.parent.mkdir(parents=True, exist_ok=True)
        with detection_path.open("w", newline="", encoding="utf-8") as handle:
            fields = list(detection_records[0]) if detection_records else ["frame"]
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(detection_records)
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--two-wheeler-model", required=True)
    parser.add_argument("--person-model", required=True)
    parser.add_argument("--output-video")
    parser.add_argument("--report")
    parser.add_argument("--detections-log")
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--tracker", default="botsort.yaml")
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--inference-long-side", type=int, default=640)
    parser.add_argument("--two-wheeler-class-id", type=int, default=1)
    parser.add_argument("--two-wheeler-confidence", type=float, default=0.10)
    parser.add_argument("--person-confidence", type=float, default=0.5)
    parser.add_argument("--person-min-overlap", type=float, default=0.25)
    parser.add_argument("--person-stride", type=int, default=1)
    parser.add_argument("--looming-threshold", type=float, default=0.02)
    parser.add_argument("--min-approach-area", type=float, default=0.005)
    parser.add_argument("--approach-vertical-threshold", type=float, default=0.003)
    parser.add_argument(
        "--route-blocked-warning",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="在目标稳定占据路线后先发路线占用提示",
    )
    parser.add_argument(
        "--predictive-urgent",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="按短时面积预测提前进入危险阶段",
    )
    parser.add_argument(
        "--early-urgent-time-to-close",
        type=float,
        default=1.2,
        help="预计进入近距离的剩余秒数小于该值时提前升级危险",
    )
    parser.add_argument("--corridor-half-width", type=float, default=0.18)
    parser.add_argument("--entry-lateral-threshold", type=float, default=0.04)
    parser.add_argument("--entry-confirm-frames", type=int, default=3)
    parser.add_argument("--prediction-frames", type=int, default=5)
    parser.add_argument("--alert-cooldown-frames", type=int, default=30)
    parser.add_argument("--input-fps", type=float, default=30.0)
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({key: value for key, value in report.items() if key != "alerts"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
