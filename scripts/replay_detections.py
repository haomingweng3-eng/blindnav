"""从 JSON 检测记录离线回放风险引擎，不依赖 YOLO 或视频文件。"""

import argparse
import json
from pathlib import Path

try:
    from .evaluate_risk_engine import evaluate_detection_records
except ImportError:  # 支持直接执行脚本
    from evaluate_risk_engine import evaluate_detection_records


REQUIRED_RECORD_FIELDS = {"frame", "track_id", "cls", "box"}


def load_detection_input(path):
    path = Path(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("检测输入必须是 JSON 对象")

    width = payload.get("width")
    height = payload.get("height")
    records = payload.get("records")
    fps = payload.get("fps")
    if not isinstance(width, (int, float)) or width <= 0:
        raise ValueError("width 必须是正数")
    if not isinstance(height, (int, float)) or height <= 0:
        raise ValueError("height 必须是正数")
    if not isinstance(records, list):
        raise ValueError("records 必须是数组")
    if fps is not None and (not isinstance(fps, (int, float)) or fps <= 0):
        raise ValueError("fps 必须是正数")

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(f"records[{index}] 必须是对象")
        missing = REQUIRED_RECORD_FIELDS - record.keys()
        if missing:
            fields = ", ".join(sorted(missing))
            raise ValueError(f"records[{index}] 缺少字段: {fields}")
        box = record["box"]
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError(f"records[{index}].box 必须包含 4 个坐标")

    result = {"width": width, "height": height, "records": records}
    if fps is not None:
        result["fps"] = fps
    return result


def replay_detection_file(input_path, looming_threshold=0.06, fps=None):
    payload = load_detection_input(input_path)
    source_fps = payload.get("fps", 1.0) if fps is None else fps
    reference_fps = 30.0 if ("fps" in payload or fps is not None) else 1.0
    report = evaluate_detection_records(
        payload["records"],
        width=payload["width"],
        height=payload["height"],
        looming_threshold=looming_threshold,
        fps=source_fps,
        reference_fps=reference_fps,
    )
    return {
        "source_type": "detection_replay",
        "input": str(input_path),
        "width": payload["width"],
        "height": payload["height"],
        "looming_threshold": looming_threshold,
        "fps": source_fps,
        "reference_fps": reference_fps,
        **report,
    }


def main():
    parser = argparse.ArgumentParser(
        description="从 JSON 检测记录回放风险引擎并生成报告"
    )
    parser.add_argument("input", help="检测记录 JSON")
    parser.add_argument("-o", "--output", help="可选的报告输出路径")
    parser.add_argument(
        "--looming-threshold",
        type=float,
        default=0.06,
        help="快速接近阈值，默认 0.06",
    )
    args = parser.parse_args()

    report_json = json.dumps(
        replay_detection_file(
            args.input, looming_threshold=args.looming_threshold
        ),
        ensure_ascii=False,
        indent=2,
    )
    if args.output:
        Path(args.output).write_text(report_json + "\n", encoding="utf-8")
        print(f"JSON报告: {args.output}")
    else:
        print(report_json)


if __name__ == "__main__":
    main()
