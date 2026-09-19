"""按人工事件标注评估真实视频报告的召回、提前量和误报告警。"""

import argparse
import json
from pathlib import Path
from statistics import median


def _require_positive_number(value, name):
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{name} 必须是正数")


def _validate_annotation(annotation):
    if not isinstance(annotation, dict):
        raise ValueError("annotation 必须是对象")
    _require_positive_number(annotation.get("fps"), "fps")
    _require_positive_number(annotation.get("duration_s"), "duration_s")
    events = annotation.get("events")
    if not isinstance(events, list):
        raise ValueError("events 必须是数组")
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise ValueError(f"events[{index}] 必须是对象")
        for field in ("event_id", "start_frame", "conflict_frame"):
            if field not in event:
                raise ValueError(f"events[{index}] 缺少字段: {field}")
        start = event["start_frame"]
        conflict = event["conflict_frame"]
        if not isinstance(start, int) or not isinstance(conflict, int) or start < 0 or conflict < start:
            raise ValueError(f"events[{index}] 帧范围无效")
        if event.get("target_class") is not None and not isinstance(event["target_class"], str):
            raise ValueError(f"events[{index}].target_class 必须是字符串或 null")


def _alert_matches_event(alert, event):
    frame = alert.get("frame")
    if not isinstance(frame, int):
        return False
    if not event["start_frame"] <= frame <= event["conflict_frame"]:
        return False
    target_class = event.get("target_class")
    return target_class in (None, "any") or alert.get("cls") == target_class


def evaluate_event_report(annotation, report):
    """评估一段视频；事件窗口含首尾帧，首个匹配告警用于提前量。"""
    _validate_annotation(annotation)
    if not isinstance(report, dict) or not isinstance(report.get("alerts"), list):
        raise ValueError("report.alerts 必须是数组")

    alerts = [alert for alert in report["alerts"] if isinstance(alert, dict)]
    events = annotation["events"]
    matched_events = []
    lead_times = []

    for event in events:
        candidates = [
            (index, alert)
            for index, alert in enumerate(alerts)
            if _alert_matches_event(alert, event)
        ]
        if not candidates:
            matched_events.append({"event_id": event["event_id"], "detected": False})
            continue
        _, first_alert = min(candidates, key=lambda item: item[1]["frame"])
        lead_time = (event["conflict_frame"] - first_alert["frame"]) / annotation["fps"]
        lead_times.append(round(lead_time, 4))
        matched_events.append(
            {
                "event_id": event["event_id"],
                "detected": True,
                "first_alert_frame": first_alert["frame"],
                "lead_time_s": round(lead_time, 4),
            }
        )

    # Any alert outside every annotated event window is an operational false alert.
    event_window_indices = {
        index
        for index, alert in enumerate(alerts)
        if any(_alert_matches_event(alert, event) for event in events)
    }
    false_alert_indices = sorted(set(range(len(alerts))) - event_window_indices)
    duration_minutes = annotation["duration_s"] / 60.0
    false_rate = len(false_alert_indices) / duration_minutes

    detected_count = sum(item["detected"] for item in matched_events)
    event_count = len(events)
    return {
        "video_id": annotation.get("video_id"),
        "duration_s": annotation["duration_s"],
        "event_count": event_count,
        "detected_event_count": detected_count,
        "event_recall": round(detected_count / event_count, 4) if event_count else None,
        "lead_times_s": lead_times,
        "median_lead_time_s": round(median(lead_times), 4) if lead_times else None,
        "matched_events": matched_events,
        "alert_count": len(alerts),
        "false_alert_count": len(false_alert_indices),
        "false_alerts_per_minute": round(false_rate, 4),
        "false_alert_frames": [alerts[index].get("frame") for index in false_alert_indices],
    }


def evaluate_event_files(annotation_path, report_path):
    annotation = json.loads(Path(annotation_path).read_text(encoding="utf-8"))
    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    return evaluate_event_report(annotation, report)


def main():
    parser = argparse.ArgumentParser(description="按人工事件标注评估风险报告")
    parser.add_argument("annotation", help="事件标注 JSON")
    parser.add_argument("report", help="风险报告 JSON")
    parser.add_argument("-o", "--output", help="输出指标 JSON")
    args = parser.parse_args()
    result = evaluate_event_files(args.annotation, args.report)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
