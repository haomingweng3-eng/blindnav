"""Filter broad two-wheeler warning candidates with a person-overlap gate.

The broad external detector is deliberately permissive and also detects parked
scooters.  This candidate-only post-filter asks a small COCO detector whether
the two-wheeler box contains a person.  It is an evaluation aid for rider-on-
vehicle scenes; it never changes YOLO labels, training data, or safety state.
"""

import argparse
import csv
import json
from pathlib import Path


def _overlap_in_box(box, person):
    x1 = max(box[0], person[0])
    y1 = max(box[1], person[1])
    x2 = min(box[2], person[2])
    y2 = min(box[3], person[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area = max(1.0, box[2] - box[0]) * max(1.0, box[3] - box[1])
    return inter / area


def _load_boxes(path):
    boxes = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            key = (
                row["source_video"],
                f"track_{row['track_id']}",
                int(row["frame_index"]),
            )
            boxes[key] = [float(row[name]) for name in ("x1", "y1", "x2", "y2")]
    return boxes


def run(args):
    import cv2
    from ultralytics import YOLO

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    alerts = json.loads(Path(args.alerts).read_text(encoding="utf-8"))
    boxes = _load_boxes(args.detections)
    model = YOLO(args.person_model)
    kept = []
    diagnostics = []
    cache = {}

    for alert in alerts:
        video = alert["video"]
        frame = int(alert["frame"])
        key = (video, frame)
        if key not in cache:
            cap = cv2.VideoCapture(str(Path(args.video_root) / video))
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
            ok, image = cap.read()
            cap.release()
            people = []
            if ok:
                result = model.predict(
                    image,
                    conf=args.person_confidence,
                    classes=[0],
                    imgsz=args.imgsz,
                    verbose=False,
                )[0]
                for box, confidence in zip(
                    result.boxes.xyxy.cpu().tolist(),
                    result.boxes.conf.cpu().tolist(),
                ):
                    people.append(
                        {
                            "box": [float(value) for value in box],
                            "confidence": float(confidence),
                        }
                    )
            cache[key] = people

        two_wheeler = boxes.get((video, alert["track_id"], frame))
        candidates = []
        if two_wheeler:
            for person in cache[key]:
                overlap = _overlap_in_box(two_wheeler, person["box"])
                candidates.append(
                    {
                        "confidence": round(person["confidence"], 4),
                        "overlap_in_two_wheeler": round(overlap, 4),
                    }
                )
        gate_pass = any(
            item["confidence"] >= args.person_confidence
            and item["overlap_in_two_wheeler"] >= args.min_overlap
            for item in candidates
        )
        item = dict(alert)
        item["person_gate"] = {
            "passed": gate_pass,
            "person_confidence_threshold": args.person_confidence,
            "minimum_overlap": args.min_overlap,
            "candidates": candidates,
        }
        diagnostics.append(
            {
                "video": video,
                "frame": frame,
                "track_id": alert["track_id"],
                "level": alert["level"],
                "two_wheeler_confidence": alert["conf"],
                "person_gate_pass": gate_pass,
                "person_candidates": len(candidates),
                "max_person_overlap": max(
                    (item["overlap_in_two_wheeler"] for item in candidates),
                    default=0.0,
                ),
            }
        )
        if gate_pass:
            kept.append(item)

    (out / "alerts.json").write_text(
        json.dumps(kept, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (out / "person_gate_diagnostics.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        fields = list(diagnostics[0]) if diagnostics else ["video"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(diagnostics)
    manifest = {
        "source_alerts": str(Path(args.alerts).resolve()),
        "detections": str(Path(args.detections).resolve()),
        "video_root": str(Path(args.video_root).resolve()),
        "person_model": str(Path(args.person_model).resolve()),
        "raw_alerts": len(alerts),
        "kept_alerts": len(kept),
        "filtered_alerts": len(alerts) - len(kept),
        "raw_videos": sorted({item["video"] for item in alerts}),
        "kept_videos": sorted({item["video"] for item in kept}),
        "filtered_videos": sorted(
            {item["video"] for item in alerts}
            - {item["video"] for item in kept}
        ),
        "person_confidence": args.person_confidence,
        "min_overlap": args.min_overlap,
        "imgsz": args.imgsz,
        "candidate_only": True,
        "human_confirmed": False,
        "training_eligible": False,
        "safety_alert_enabled": False,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alerts", required=True)
    parser.add_argument("--detections", required=True)
    parser.add_argument("--video-root", required=True)
    parser.add_argument("--person-model", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--person-confidence", type=float, default=0.5)
    parser.add_argument("--min-overlap", type=float, default=0.25)
    parser.add_argument("--imgsz", type=int, default=640)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
