"""用视频级人工标签评估风险告警的召回和安全场景误报。"""

import argparse
import csv
import json
from pathlib import Path

try:
    from .evaluate_risk_engine import evaluate_detection_records
    from .risk_engine import LVL_HIGH, LVL_MID
except ImportError:  # 支持直接执行脚本
    from evaluate_risk_engine import evaluate_detection_records
    from risk_engine import LVL_HIGH, LVL_MID


POSITIVE_STATUSES = {"near_miss", "near miss", "conflict", "dangerous"}
SAFE_STATUS = "safe"


def _normalize_status(value):
    return str(value or "").strip().lower().replace("-", "_")


def _approx_time(row):
    value = str(row.get("approx_time_s", "")).strip().lower().replace("s", "")
    if not value:
        return None
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"approx_time_s 不是数字: {row.get('video_file')}") from exc


def _metrics_for_threshold(
    labels,
    reports,
    threshold,
    min_approach_area,
    corridor_center,
    corridor_half_width,
    entry_lateral_threshold,
):
    per_video = []
    for row in labels:
        video_file = str(row.get("video_file", "")).strip()
        if not video_file:
            raise ValueError("标签缺少 video_file")
        if video_file not in reports:
            raise ValueError(f"找不到视频报告: {video_file}")
        status = _normalize_status(row.get("status"))
        if status not in POSITIVE_STATUSES and status != SAFE_STATUS:
            raise ValueError(f"不支持的 status: {row.get('status')} ({video_file})")

        payload = reports[video_file]
        report = evaluate_detection_records(
            payload["records"],
            width=payload["width"],
            height=payload["height"],
            looming_threshold=threshold,
            fps=float(payload.get("fps", 1.0)),
            reference_fps=float(payload.get("reference_fps", 1.0)),
            min_approach_area=min_approach_area,
            corridor_center=corridor_center,
            corridor_half_width=corridor_half_width,
            entry_lateral_threshold=entry_lateral_threshold,
        )
        alerts = report.get("alerts", [])
        first_frame = alerts[0]["frame"] if alerts else None
        fps = float(payload.get("fps", 1.0))
        first_alert_s = first_frame / fps if first_frame is not None else None
        approx_s = _approx_time(row)
        positive = status in POSITIVE_STATUSES
        detected = bool(alerts)
        per_video.append(
            {
                "video_file": video_file,
                "status": status,
                "positive": positive,
                "detected": detected,
                "alert_count": len(alerts),
                "warning_count": sum(a.get("level") == LVL_MID for a in alerts),
                "conflict_count": sum(a.get("level", 0) >= LVL_HIGH for a in alerts),
                "first_alert_frame": first_frame,
                "first_alert_s": round(first_alert_s, 4) if first_alert_s is not None else None,
                "approx_time_s": approx_s,
                "lead_time_s": (
                    round(approx_s - first_alert_s, 4)
                    if approx_s is not None and first_alert_s is not None
                    else None
                ),
            }
        )

    positive_rows = [item for item in per_video if item["positive"]]
    safe_rows = [item for item in per_video if not item["positive"]]
    detected_positive = sum(item["detected"] for item in positive_rows)
    false_positive = sum(item["detected"] for item in safe_rows)
    total = len(per_video)
    positive_count = len(positive_rows)
    safe_count = len(safe_rows)
    recall = detected_positive / positive_count if positive_count else 0.0
    false_positive_rate = false_positive / safe_count if safe_count else 0.0
    precision_denominator = detected_positive + false_positive
    precision = detected_positive / precision_denominator if precision_denominator else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    lead_times = [
        item["lead_time_s"]
        for item in positive_rows
        if item["detected"] and item["lead_time_s"] is not None
    ]
    return {
        "threshold": float(threshold),
        "video_count": total,
        "positive_video_count": positive_count,
        "detected_positive_count": detected_positive,
        "safe_video_count": safe_count,
        "false_positive_video_count": false_positive,
        "recall": round(recall, 6),
        "false_positive_rate": round(false_positive_rate, 6),
        "precision": round(precision, 6),
        "f1": round(f1, 6),
        "lead_time_s": lead_times,
        "per_video": per_video,
    }


def evaluate_labeled_videos(
    labels,
    reports,
    thresholds=(0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10),
    min_approach_area=0.01,
    corridor_center=0.0,
    corridor_half_width=0.18,
    entry_lateral_threshold=0.04,
):
    """对已有检测报告做视频级代理评估，不重新运行模型。"""
    if not labels:
        raise ValueError("至少需要一条视频标签")
    normalized_thresholds = [float(value) for value in thresholds]
    if any(value <= 0 for value in normalized_thresholds):
        raise ValueError("looming thresholds must be positive")
    results = [
        _metrics_for_threshold(
            labels,
            reports,
            threshold,
            min_approach_area,
            corridor_center,
            corridor_half_width,
            entry_lateral_threshold,
        )
        for threshold in normalized_thresholds
    ]
    return {
        "source_type": "video_level_proxy_evaluation",
        "label_count": len(labels),
        "thresholds": normalized_thresholds,
        "min_approach_area": min_approach_area,
        "corridor_center": corridor_center,
        "corridor_half_width": corridor_half_width,
        "entry_lateral_threshold": entry_lateral_threshold,
        "results": results,
        "interpretation": (
            "指标以整段视频是否出现告警为单位，不能替代逐帧目标框精度；"
            "lead_time_s 使用人工填写的近似事件时间，仅用于工程调参。"
        ),
    }


def _load_labels(path):
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _load_reports(directory):
    result = {}
    for path in sorted(Path(directory).glob("*.json")):
        if path.name == "summary.json":
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        result[path.stem + ".mp4"] = payload
    return result


def main():
    parser = argparse.ArgumentParser(description="评估视频级标签与风险告警的一致性")
    parser.add_argument("labels", help="人工标注 CSV")
    parser.add_argument("reports_dir", help="batch_detect_videos 输出目录")
    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=[0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10],
    )
    parser.add_argument("--min-approach-area", type=float, default=0.01)
    parser.add_argument("--corridor-center", type=float, default=0.0)
    parser.add_argument("--corridor-half-width", type=float, default=0.18)
    parser.add_argument("--entry-lateral-threshold", type=float, default=0.04)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    result = evaluate_labeled_videos(
        _load_labels(args.labels),
        _load_reports(args.reports_dir),
        thresholds=args.thresholds,
        min_approach_area=args.min_approach_area,
        corridor_center=args.corridor_center,
        corridor_half_width=args.corridor_half_width,
        entry_lateral_threshold=args.entry_lateral_threshold,
    )
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
