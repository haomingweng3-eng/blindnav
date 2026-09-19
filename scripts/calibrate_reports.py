"""对已保存的检测框报告重扫 looming 阈值，不重复运行 YOLO。"""

import argparse
import json
from pathlib import Path

try:
    from .evaluate_risk_engine import evaluate_detection_records
    from .risk_engine import LVL_HIGH, LVL_MID
except ImportError:  # 支持直接执行脚本
    from evaluate_risk_engine import evaluate_detection_records
    from risk_engine import LVL_HIGH, LVL_MID


DEFAULT_THRESHOLDS = [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]


def calibrate_report_payload(payload, thresholds=DEFAULT_THRESHOLDS):
    """返回每个阈值下的告警摘要；payload 必须含原始 records。"""
    required = {"width", "height", "records"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"报告缺少原始检测字段: {', '.join(missing)}")
    if not isinstance(payload["records"], list):
        raise ValueError("报告中的 records 必须是数组")

    source_fps = float(payload.get("fps", 1.0))
    reference_fps = float(payload.get("reference_fps", 1.0))
    normalized_thresholds = [float(value) for value in thresholds]
    if any(value <= 0 for value in normalized_thresholds):
        raise ValueError("looming thresholds must be positive")

    results = []
    for threshold in normalized_thresholds:
        report = evaluate_detection_records(
            payload["records"],
            width=payload["width"],
            height=payload["height"],
            looming_threshold=threshold,
            fps=source_fps,
            reference_fps=reference_fps,
        )
        results.append(
            {
                "threshold": threshold,
                "alert_count": report["alert_count"],
                "warning_count": sum(
                    alert["level"] == LVL_MID for alert in report["alerts"]
                ),
                "high_count": sum(
                    alert["level"] >= LVL_HIGH for alert in report["alerts"]
                ),
                "first_alert_frame": (
                    report["alerts"][0]["frame"] if report["alerts"] else None
                ),
                "speech": [
                    alert["feedback"]["speech"]
                    for alert in report["alerts"]
                    if alert.get("feedback", {}).get("speech")
                ],
            }
        )

    return {
        "source_type": "threshold_calibration",
        "source_video": payload.get("video"),
        "fps": source_fps,
        "reference_fps": reference_fps,
        "thresholds": normalized_thresholds,
        "results": results,
        "interpretation": "告警数量和首帧用于调参，不等于真实准确率；需结合人工标注判断误报/漏报。",
    }


def main():
    parser = argparse.ArgumentParser(description="重扫已保存报告的 looming 阈值")
    parser.add_argument("reports", nargs="+", help="detect_video 输出的 JSON 报告")
    parser.add_argument(
        "--thresholds",
        nargs="+",
        type=float,
        default=DEFAULT_THRESHOLDS,
        help="待扫描阈值，默认 0.02 0.03 0.04 0.05 0.06 0.08 0.10",
    )
    parser.add_argument("-o", "--output", help="输出汇总 JSON")
    args = parser.parse_args()

    reports = []
    for report_path in args.reports:
        payload = json.loads(Path(report_path).read_text(encoding="utf-8"))
        calibrated = calibrate_report_payload(payload, thresholds=args.thresholds)
        calibrated["input"] = report_path
        reports.append(calibrated)

    result = {"report_count": len(reports), "reports": reports}
    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
