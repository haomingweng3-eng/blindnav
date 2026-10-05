"""Re-score saved video detections with the current guidance contract.

This does not run a detector, alter labels, or treat guidance output as
training truth. It separates confirmed route warnings from the model's raw
detection alerts so geometry changes can be compared without reprocessing
the videos.
"""

import argparse
import csv
import json
from pathlib import Path

try:
    from .evaluate_risk_engine import evaluate_detection_records
except ImportError:
    from evaluate_risk_engine import evaluate_detection_records


WARNING_STATES = {"CAUTION", "DANGER", "STOP"}
UNCERTAIN_STATES = {"UNKNOWN_SLOW_DOWN"}


def load_labels(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def load_reports(directory):
    reports = {}
    for path in sorted(Path(directory).glob("*.json")):
        if path.name == "summary.json":
            continue
        reports[path.stem + ".mp4"] = json.loads(path.read_text(encoding="utf-8"))
    return reports


def evaluate(labels, reports):
    rows = []
    for label in labels:
        video = label["video_file"]
        payload = reports[video]
        result = evaluate_detection_records(
            payload["records"],
            width=payload["width"],
            height=payload["height"],
            fps=float(payload.get("fps", 1.0)),
            reference_fps=float(payload.get("reference_fps", 1.0)),
            guidance_regions=None,
        )
        trace = result["guidance"]["trace"]
        warning_frames = [item["frame"] for item in trace if item["state"] in WARNING_STATES]
        warning_feedback_frames = [
            item["frame"] for item in trace
            if item["state"] in WARNING_STATES and item.get("speech")
        ]
        uncertain_frames = [item["frame"] for item in trace if item["state"] in UNCERTAIN_STATES]
        status = str(label.get("status", "")).strip().lower()
        rows.append({
            "video_file": video,
            "status": status,
            "warning": bool(warning_frames),
            "warning_feedback": bool(warning_feedback_frames),
            "uncertain": bool(uncertain_frames),
            "first_warning_frame": min(warning_frames) if warning_frames else None,
            "first_warning_feedback_frame": min(warning_feedback_frames) if warning_feedback_frames else None,
            "warning_feedback_count": len(warning_feedback_frames),
            "first_uncertain_frame": min(uncertain_frames) if uncertain_frames else None,
            "state_counts": result["guidance"]["state_counts"],
        })
    safe = [row for row in rows if row["status"] == "safe"]
    conflict = [row for row in rows if row["status"] in {"conflict", "dangerous"}]
    near_miss = [row for row in rows if row["status"] in {"near_miss", "near miss"}]
    def rate(numerator, denominator):
        return round(numerator / denominator, 6) if denominator else None
    return {
        "video_count": len(rows),
        "safe_count": len(safe),
        "safe_warning_count": sum(row["warning"] for row in safe),
        "safe_warning_rate": rate(sum(row["warning"] for row in safe), len(safe)),
        "safe_warning_feedback_count": sum(row["warning_feedback"] for row in safe),
        "safe_warning_feedback_rate": rate(sum(row["warning_feedback"] for row in safe), len(safe)),
        "conflict_count": len(conflict),
        "conflict_warning_count": sum(row["warning"] for row in conflict),
        "conflict_warning_recall": rate(sum(row["warning"] for row in conflict), len(conflict)),
        "conflict_warning_feedback_count": sum(row["warning_feedback"] for row in conflict),
        "conflict_warning_feedback_recall": rate(sum(row["warning_feedback"] for row in conflict), len(conflict)),
        "near_miss_count": len(near_miss),
        "near_miss_warning_count": sum(row["warning"] for row in near_miss),
        "near_miss_warning_rate": rate(sum(row["warning"] for row in near_miss), len(near_miss)),
        "near_miss_warning_feedback_count": sum(row["warning_feedback"] for row in near_miss),
        "near_miss_warning_feedback_rate": rate(sum(row["warning_feedback"] for row in near_miss), len(near_miss)),
        "per_video": rows,
        "interpretation": "Guidance state and emitted-feedback proxy from saved detections; no frame-level ground truth or phone performance claim.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("labels")
    parser.add_argument("reports_dir")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = evaluate(load_labels(args.labels), load_reports(args.reports_dir))
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
