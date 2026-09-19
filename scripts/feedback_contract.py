"""校验风险报告中 Android FeedbackDispatcher 所消费的 JSON 契约。"""


ALLOWED_PRIORITIES = {"low", "warning", "urgent"}
ALLOWED_TONES = {None, "warning", "danger"}


def _is_nonnegative_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_report(report):
    """返回错误字符串列表；空列表表示报告可交给安卓联调。"""
    errors = []
    if not isinstance(report, dict):
        return ["report 必须是对象"]

    alerts = report.get("alerts")
    if not isinstance(alerts, list):
        return ["alerts 必须是数组"]

    for index, alert in enumerate(alerts):
        path = f"alerts[{index}]"
        if not isinstance(alert, dict):
            errors.append(f"{path} 必须是对象")
            continue
        for field in ("frame", "track_id", "cls", "level"):
            if field not in alert:
                errors.append(f"{path} 缺少字段: {field}")
        if "frame" in alert and not _is_nonnegative_int(alert["frame"]):
            errors.append(f"{path}.frame 必须是非负整数")
        if "track_id" in alert and not isinstance(alert["track_id"], str):
            errors.append(f"{path}.track_id 必须是字符串")
        if "cls" in alert and not isinstance(alert["cls"], str):
            errors.append(f"{path}.cls 必须是字符串")
        if "level" in alert and alert["level"] not in (0, 1, 2, 3):
            errors.append(f"{path}.level 必须是 0、1、2 或 3")

        feedback = alert.get("feedback")
        if feedback is None:
            continue
        if not isinstance(feedback, dict):
            errors.append(f"{path}.feedback 必须是对象或 null")
            continue

        required = ("priority", "vibration_ms", "tone", "speech", "speech_delay_ms")
        for field in required:
            if field not in feedback:
                errors.append(f"{path}.feedback 缺少字段: {field}")

        priority = feedback.get("priority")
        if priority not in ALLOWED_PRIORITIES:
            errors.append(f"{path}.feedback.priority 值无效")

        vibration = feedback.get("vibration_ms")
        if (
            not isinstance(vibration, list)
            or not vibration
            or any(not _is_nonnegative_int(value) or value == 0 for value in vibration)
        ):
            errors.append(f"{path}.feedback.vibration_ms 必须是正整数数组")

        if feedback.get("tone") not in ALLOWED_TONES:
            errors.append(f"{path}.feedback.tone 值无效")
        if feedback.get("speech") is not None and not isinstance(feedback.get("speech"), str):
            errors.append(f"{path}.feedback.speech 必须是字符串或 null")
        delay = feedback.get("speech_delay_ms")
        if delay is not None and not _is_nonnegative_int(delay):
            errors.append(f"{path}.feedback.speech_delay_ms 必须是非负整数或 null")

    return errors


def validate_report_file(path):
    """读取报告文件并返回错误列表，供 CLI 或批处理调用。"""
    import json
    from pathlib import Path

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_report(payload)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="校验 Android feedback JSON 契约")
    parser.add_argument("report", help="风险报告 JSON")
    args = parser.parse_args()
    result = validate_report_file(args.report)
    print(json.dumps({"valid": not result, "errors": result}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not result else 1)
