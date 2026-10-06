"""Render an archived review video with tracked boxes and projected path.

This is a visual review artifact only.  It consumes the existing candidate
track CSV and risk JSON, never creates labels, changes models, or enables
safety alerts.  The projected line is a short image-space extrapolation of the
recent track center, not a calibrated collision trajectory and not the current
phone path.
"""

import argparse
import json
from statistics import median
from collections import defaultdict, deque
from pathlib import Path


def _box_center(row):
    return ((float(row["x1"]) + float(row["x2"])) / 2.0,
            (float(row["y1"]) + float(row["y2"])) / 2.0)


def _road_contact(row):
    """Approximate the vehicle's road contact point from the box bottom."""
    return ((float(row["x1"]) + float(row["x2"])) / 2.0,
            float(row["y2"]))


def _relative_motion_is_stable(motions, width, height):
    """Return true only for coherent motion after scene-motion removal.

    Parking rows often move together when the camera pans.  A raw contact
    point displacement would turn that camera motion into a fake future path.
    The caller stores per-track motion after subtracting the frame-wide median;
    require a few same-direction samples before drawing a prediction.
    """
    if len(motions) < 3:
        return False
    threshold = max(2.0, min(width, height) * 0.002)
    dx = [float(item[0]) for item in motions]
    dy = [float(item[1]) for item in motions]
    axis = dx if median(abs(value) for value in dx) >= median(abs(value) for value in dy) else dy
    active = [value for value in axis if abs(value) >= threshold * 0.35]
    if len(active) < 3:
        return False
    dominant_sign = 1 if median(active) >= 0 else -1
    agreement = sum(1 for value in active if value * dominant_sign >= 0) / len(active)
    return agreement >= 0.75 and median(abs(value) for value in active) >= threshold


def _read_tracks(path, video_name):
    import csv

    grouped = defaultdict(dict)
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["source_video"] != video_name:
                continue
            grouped[int(row["frame_index"])][f"track_{row['track_id']}"] = row
    return grouped


def _load_alerts(path, video_name):
    alerts = {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload.get("alerts", []) if isinstance(payload, dict) else payload
    for item in items:
        if item.get("video") not in (None, video_name):
            continue
        alerts[(int(item["frame"]), str(item["track_id"]))] = item
    return alerts


def _risk_for(frame, track_id, alerts):
    # Sparse alert events are not a persistent risk snapshot. Never leave an
    # object red indefinitely after it has stopped or left the route.
    return alerts.get((frame, track_id))


def render(args):
    import cv2

    cap = cv2.VideoCapture(str(Path(args.video_root) / args.video))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {args.video}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        cap.release()
        raise RuntimeError(f"cannot open output: {output}")

    tracks = _read_tracks(args.detections, args.video)
    alerts = _load_alerts(args.alerts, args.video)
    trails = defaultdict(lambda: deque(maxlen=args.trail_length))
    road_trails = defaultdict(lambda: deque(maxlen=args.trail_length))
    relative_motions = defaultdict(lambda: deque(maxlen=6))
    previous_contacts = {}
    trail_thickness = max(5, width // 320)
    arrow_thickness = max(6, width // 240)
    dot_radius = max(8, width // 160)
    # Keep the motion cues visually distinct from the risk-state box color.
    # OpenCV uses BGR here: cyan trail, magenta projected path.
    # Keep the historical path visible but subordinate to the prediction.
    trail_color = (180, 180, 0)
    projection_color = (255, 0, 255)
    frame_index = 0
    alert_frames = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        current = tracks.get(frame_index, {})
        current_contacts = {
            track_id: _road_contact(row) for track_id, row in current.items()
        }
        scene_deltas = [
            (point[0] - previous_contacts[track_id][0],
             point[1] - previous_contacts[track_id][1])
            for track_id, point in current_contacts.items()
            if track_id in previous_contacts
        ]
        scene_dx = median([item[0] for item in scene_deltas]) if scene_deltas else 0.0
        scene_dy = median([item[1] for item in scene_deltas]) if scene_deltas else 0.0
        for track_id, row in current.items():
            x1, y1, x2, y2 = [int(float(row[name])) for name in ("x1", "y1", "x2", "y2")]
            center = _box_center(row)
            road_contact = _road_contact(row)
            trails[track_id].append(center)
            road_trails[track_id].append(road_contact)
            if track_id in previous_contacts:
                relative_motions[track_id].append((
                    road_contact[0] - previous_contacts[track_id][0] - scene_dx,
                    road_contact[1] - previous_contacts[track_id][1] - scene_dy,
                ))
            alert = _risk_for(frame_index, track_id, alerts)
            level = int(alert["level"]) if alert else 0
            color = (0, 190, 255) if level < 3 else (0, 0, 255)
            if level == 0:
                color = (0, 220, 0)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3)
            label = f"2w {track_id}"
            if alert:
                band_label = "APPROACH" if int(alert["level"]) >= 3 else "WARNING"
                label += f"  {band_label}"
                if int(alert["frame"]) == frame_index:
                    alert_frames.append(frame_index)
            cv2.putText(frame, label, (x1, max(28, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.72, color, 2, cv2.LINE_AA)
            points = list(trails[track_id])
            for old, new in zip(points, points[1:]):
                cv2.line(frame, tuple(map(int, old)), tuple(map(int, new)), trail_color, trail_thickness)
            road_points = list(road_trails[track_id])
            # Draw the historical contact path directly on the road surface.
            for old, new in zip(road_points, road_points[1:]):
                cv2.line(frame, tuple(map(int, old)), tuple(map(int, new)), trail_color,
                         max(4, trail_thickness - 1))
            if args.allow_archived_projection and len(road_points) >= 2 and _relative_motion_is_stable(
                relative_motions[track_id], width, height
            ):
                use = road_points[-min(args.prediction_points, len(road_points)):]
                motion = list(relative_motions[track_id])[-min(args.prediction_points - 1, len(relative_motions[track_id])):]
                dx = median(item[0] for item in motion)
                dy = median(item[1] for item in motion)
                projected = (use[-1][0] + dx * args.horizon_frames,
                             use[-1][1] + dy * args.horizon_frames)
                start = tuple(map(int, use[-1]))
                end = tuple(map(int, projected))
                # Dark outline keeps the road line visible over asphalt and lane markings.
                cv2.arrowedLine(frame, start, end, (0, 0, 0), arrow_thickness + 8, tipLength=0.18)
                cv2.arrowedLine(frame, start, end, projection_color, arrow_thickness, tipLength=0.18)
                cv2.circle(frame, start, dot_radius + 4, (0, 0, 0), -1)
                cv2.circle(frame, start, dot_radius, projection_color, -1)
                cv2.circle(frame, end, dot_radius + 4, (0, 0, 0), -1)
                cv2.circle(frame, end, dot_radius, projection_color, -1)
                for fraction in (1 / 3, 2 / 3, 1.0):
                    label = f"{args.horizon_frames * fraction / fps:.2f}s"
                    future = (
                        use[-1][0] + dx * args.horizon_frames * fraction,
                        use[-1][1] + dy * args.horizon_frames * fraction,
                    )
                    future_point = tuple(map(int, future))
                    future_radius = max(6, dot_radius // 2)
                    cv2.circle(frame, future_point, future_radius + 3, (0, 0, 0), -1)
                    cv2.circle(frame, future_point, future_radius, projection_color, -1)
                    fx = min(max(future_point[0] + future_radius + 6, 8), width - 72)
                    fy = min(max(future_point[1] - future_radius - 5, 24), height - 8)
                    cv2.putText(frame, label, (fx, fy), cv2.FONT_HERSHEY_SIMPLEX,
                                0.58, projection_color, 2, cv2.LINE_AA)
                tx = min(max(int(projected[0]) + dot_radius + 8, 8), width - 170)
                ty = min(max(int(projected[1]) - dot_radius - 8, 28), height - 8)
                cv2.putText(frame, "FUTURE ROAD PATH", (tx, ty),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, projection_color, 2, cv2.LINE_AA)
        previous_contacts = current_contacts
        cv2.putText(frame, f"ARCHIVED frame {frame_index}  cyan=observed trail  risk=current event only",
                    (18, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.78, (255, 255, 255), 2, cv2.LINE_AA)
        writer.write(frame)
        frame_index += 1
    cap.release()
    writer.release()
    report = {
        "video": args.video,
        "output": str(output.resolve()),
        "frames": frame_index,
        "alert_frames": sorted(set(alert_frames)),
        "candidate_only": True,
        "human_confirmed": False,
        "trajectory_line": "bold magenta short constant-velocity image-space projection on the road contact path",
        "path_anchor": "bounding-box bottom center (road contact proxy)",
        "projection_horizon_frames": args.horizon_frames,
        "collision_guarantee": False,
    }
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--video-root", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--detections", required=True)
    parser.add_argument("--alerts", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--trail-length", type=int, default=24)
    parser.add_argument("--prediction-points", type=int, default=8)
    parser.add_argument("--horizon-frames", type=int, default=20)
    parser.add_argument("--allow-archived-projection", action="store_true",
                        help="Historical comparison only; disabled without reliable camera motion")
    args = parser.parse_args()
    print(json.dumps(render(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
