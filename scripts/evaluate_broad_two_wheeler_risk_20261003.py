"""Run the candidate broad two-wheeler tracks through the route-risk prototype.

This consumes detections already produced by the public two-wheeler model and
ByteTrack. It does not create labels and does not make a collision claim. The
result is a candidate-only early-warning diagnostic for recorded videos.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

try:
    from .evaluate_risk_engine import evaluate_detection_records
except ImportError:
    from evaluate_risk_engine import evaluate_detection_records


def _video_meta(video_root, video_name):
    import cv2

    path = Path(video_root) / video_name
    cap = cv2.VideoCapture(str(path))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if width <= 0 or height <= 0:
        raise RuntimeError(f"cannot read video dimensions: {path}")
    return fps, width, height, frame_count


def _load_records(path):
    grouped = defaultdict(list)
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            grouped[row["source_video"]].append(
                {
                    "frame": int(row["frame_index"]),
                    "track_id": f"track_{row['track_id']}",
                    "cls": "2-wheeler",
                    "conf": float(row["confidence"]),
                    "box": [
                        float(row["x1"]),
                        float(row["y1"]),
                        float(row["x2"]),
                        float(row["y2"]),
                    ],
                }
            )
    return grouped


def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    grouped = _load_records(args.detections)
    rows = []
    all_alerts = []
    for video_name in sorted(grouped):
        fps, width, height, frame_count = _video_meta(args.video_root, video_name)
        report = evaluate_detection_records(
            grouped[video_name],
            width=width,
            height=height,
            looming_threshold=args.looming_threshold,
            fps=fps,
            reference_fps=30.0,
            min_approach_area=args.min_approach_area,
            corridor_center=args.corridor_center,
            corridor_half_width=args.corridor_half_width,
            entry_lateral_threshold=args.entry_lateral_threshold,
            entry_confirm_frames=args.entry_confirm_frames,
            prediction_frames=args.prediction_frames,
            approach_vertical_threshold=args.approach_vertical_threshold,
        )
        report.update(
            {
                "video": video_name,
                "fps": fps,
                "width": width,
                "height": height,
                "source_frame_count": frame_count,
                "model_scope": "two_wheeler_candidate",
                "candidate_only": True,
                "human_confirmed": False,
                "training_eligible": False,
                "safety_alert_enabled": False,
            }
        )
        (out / f"{Path(video_name).stem}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        route_entries = sum(
            1 for item in report["track_diagnostics"] if item["route_entry_seen"]
        )
        predicted_entries = sum(
            1
            for item in report["track_diagnostics"]
            if item["predicted_entry_seen"]
        )
        row = {
            "video": video_name,
            "frames": frame_count,
            "fps": round(fps, 3),
            "tracks": report["track_count"],
            "alerts": report["alert_count"],
            "raw_alerts": report["raw_alert_count"],
            "route_entry_tracks": route_entries,
            "predicted_entry_tracks": predicted_entries,
            "candidate_only": True,
        }
        rows.append(row)
        for alert in report["alerts"]:
            all_alerts.append({"video": video_name, **alert})

    with (out / "video_summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["video"])
        writer.writeheader()
        writer.writerows(rows)
    (out / "alerts.json").write_text(
        json.dumps(all_alerts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    manifest = {
        "detections": str(Path(args.detections).resolve()),
        "video_root": str(Path(args.video_root).resolve()),
        "videos": len(rows),
        "total_tracks": sum(row["tracks"] for row in rows),
        "videos_with_alerts": sum(row["alerts"] > 0 for row in rows),
        "total_alerts": len(all_alerts),
        "parameters": {
            "looming_threshold": args.looming_threshold,
            "min_approach_area": args.min_approach_area,
            "corridor_center": args.corridor_center,
            "corridor_half_width": args.corridor_half_width,
            "entry_lateral_threshold": args.entry_lateral_threshold,
            "entry_confirm_frames": args.entry_confirm_frames,
            "prediction_frames": args.prediction_frames,
            "approach_vertical_threshold": args.approach_vertical_threshold,
        },
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
    parser.add_argument("--detections", required=True)
    parser.add_argument("--video-root", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--looming-threshold", type=float, default=0.06)
    parser.add_argument("--min-approach-area", type=float, default=0.01)
    parser.add_argument("--corridor-center", type=float, default=0.0)
    parser.add_argument("--corridor-half-width", type=float, default=0.14)
    parser.add_argument("--entry-lateral-threshold", type=float, default=0.04)
    parser.add_argument("--entry-confirm-frames", type=int, default=3)
    parser.add_argument("--prediction-frames", type=int, default=5)
    parser.add_argument("--approach-vertical-threshold", type=float, default=0.001)
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
