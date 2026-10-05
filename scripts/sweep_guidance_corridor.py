"""Offline sweep of the route corridor using saved detections only."""
import argparse
import csv
import json
from pathlib import Path

try:
    from .evaluate_risk_engine import evaluate_detection_records
    from .guidance_engine import WalkableRegion
except ImportError:
    from evaluate_risk_engine import evaluate_detection_records
    from guidance_engine import WalkableRegion


WARNING_STATES = {"CAUTION", "DANGER", "STOP"}


def run(labels_path, reports_dir, centers, half_widths):
    with Path(labels_path).open(newline="", encoding="utf-8-sig") as handle:
        labels = list(csv.DictReader(handle))
    reports = {
        path.stem + ".mp4": json.loads(path.read_text(encoding="utf-8"))
        for path in Path(reports_dir).glob("*.json") if path.name != "summary.json"
    }
    rows = []
    for center in centers:
        for half_width in half_widths:
            region = WalkableRegion(
                left=max(0.0, 0.5 + center - half_width),
                right=min(1.0, 0.5 + center + half_width),
                floor_y=0.38,
                confidence=0.8,
                source="calibration_geometry",
            )
            per_video = []
            for label in labels:
                payload = reports[label["video_file"]]
                result = evaluate_detection_records(
                    payload["records"], payload["width"], payload["height"],
                    fps=float(payload.get("fps", 1.0)),
                    reference_fps=float(payload.get("reference_fps", 1.0)),
                    guidance_regions={int(item["frame"]): region for item in payload["records"]},
                )
                states = result["guidance"]["state_counts"]
                per_video.append((label["status"].strip().lower(), any(s in states for s in WARNING_STATES)))
            safe = [warning for status, warning in per_video if status == "safe"]
            conflict = [warning for status, warning in per_video if status in {"conflict", "dangerous"}]
            near = [warning for status, warning in per_video if status in {"near_miss", "near miss"}]
            rows.append({
                "center": center, "half_width": half_width,
                "safe_warning_rate": sum(safe) / len(safe) if safe else None,
                "conflict_recall": sum(conflict) / len(conflict) if conflict else None,
                "near_miss_warning_rate": sum(near) / len(near) if near else None,
            })
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("labels")
    parser.add_argument("reports_dir")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    rows = run(args.labels, args.reports_dir, [-0.05, 0.0, 0.05], [0.06, 0.08, 0.10, 0.12, 0.14, 0.18])
    Path(args.output).write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))
