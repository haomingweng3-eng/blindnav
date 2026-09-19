"""批量汇总事件标注与风险报告，生成提交前的总体指标。"""

import argparse
import json
from pathlib import Path
from statistics import median

try:
    from .evaluate_events import evaluate_event_files
except ImportError:  # 支持直接执行脚本
    from evaluate_events import evaluate_event_files


def aggregate_results(results):
    total_events = sum(item["event_count"] for item in results)
    detected_events = sum(item["detected_event_count"] for item in results)
    total_duration_s = sum(item["duration_s"] for item in results)
    false_alerts = sum(item["false_alert_count"] for item in results)
    lead_times = [lead for item in results for lead in item["lead_times_s"]]
    duration_minutes = total_duration_s / 60.0
    return {
        "video_count": len(results),
        "event_count": total_events,
        "detected_event_count": detected_events,
        "event_recall": round(detected_events / total_events, 4) if total_events else None,
        "median_lead_time_s": round(median(lead_times), 4) if lead_times else None,
        "false_alert_count": false_alerts,
        "false_alerts_per_minute": round(false_alerts / duration_minutes, 4)
        if duration_minutes
        else None,
        "total_duration_s": round(total_duration_s, 4),
    }


def evaluate_directories(annotations_dir, reports_dir):
    annotations_dir = Path(annotations_dir)
    reports_dir = Path(reports_dir)
    results = []
    missing_reports = []
    for annotation_path in sorted(annotations_dir.glob("*.json")):
        report_path = reports_dir / annotation_path.name
        if not report_path.exists():
            missing_reports.append(annotation_path.stem)
            continue
        result = evaluate_event_files(annotation_path, report_path)
        result["annotation"] = str(annotation_path)
        result["report"] = str(report_path)
        results.append(result)
    return {
        "summary": aggregate_results(results),
        "videos": results,
        "missing_reports": missing_reports,
    }


def main():
    parser = argparse.ArgumentParser(description="批量汇总真实视频事件指标")
    parser.add_argument("annotations_dir", help="事件标注 JSON 目录")
    parser.add_argument("reports_dir", help="风险报告 JSON 目录")
    parser.add_argument("-o", "--output", help="输出汇总 JSON")
    args = parser.parse_args()
    result = evaluate_directories(args.annotations_dir, args.reports_dir)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)
    raise SystemExit(1 if result["missing_reports"] else 0)


if __name__ == "__main__":
    main()
