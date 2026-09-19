"""对录制视频跑 YOLO + ByteTrack + 风险引擎，输出检测记录和风险报告。"""

import argparse
import json
from pathlib import Path


ALERT_CLASSES = {
    "person",
    "bicycle",
    "motorcycle",
    "scooter",
    "electric_bicycle",
    "electric_bike",
    "e-bike",
    "electric bicycle",
    "car",
    "bus",
    "truck",
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="对视频运行 YOLO + ByteTrack + 风险引擎"
    )
    parser.add_argument("video", help="输入视频路径")
    parser.add_argument("report", nargs="?", help="可选的 JSON 报告路径")
    parser.add_argument(
        "looming_threshold",
        nargs="?",
        type=float,
        default=0.06,
        help="快速接近阈值，默认 0.06",
    )
    parser.add_argument(
        "--model",
        default="models/yolov8n.pt",
        help="YOLO 权重路径，可替换为自定义 scooter/e-bike 模型",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="推理设备，例如 mps、cpu 或 cuda:0；默认由 Ultralytics 选择",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="检测置信度阈值，默认 0.25",
    )
    return parser.parse_args(argv)


def process_video(
    video_path,
    model_path="models/yolov8n.pt",
    looming_threshold=0.06,
    device=None,
    conf=0.25,
):
    """运行一次视频检测并返回可序列化报告。"""
    import cv2
    from ultralytics import YOLO

    try:
        from .evaluate_risk_engine import evaluate_detection_records
    except ImportError:
        from evaluate_risk_engine import evaluate_detection_records

    model = YOLO(model_path)
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    video_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    video_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if video_width <= 0 or video_height <= 0:
        cap.release()
        raise RuntimeError("无法从视频读取宽高，不能进行坐标归一化")

    frame_idx = 0
    detection_records = []
    track_kwargs = {
        "persist": True,
        "tracker": "bytetrack.yaml",
        "verbose": False,
        "conf": conf,
    }
    if device is not None:
        track_kwargs["device"] = device

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_idx += 1
        results = model.track(frame, **track_kwargs)
        tracked = results[0]
        if tracked.boxes.id is None:
            continue

        for box, box_conf, cls, tracked_id in zip(
            tracked.boxes.xyxy,
            tracked.boxes.conf,
            tracked.boxes.cls,
            tracked.boxes.id,
        ):
            name = model.names[int(cls)]
            if name not in ALERT_CLASSES:
                continue
            x1, y1, x2, y2 = [float(value) for value in box]
            detection_records.append(
                {
                    "frame": frame_idx,
                    "track_id": f"{name}_{int(tracked_id)}",
                    "cls": name,
                    "conf": float(box_conf),
                    "box": [x1, y1, x2, y2],
                }
            )

    cap.release()
    source_fps = fps if fps > 0 else 30.0
    report = evaluate_detection_records(
        detection_records,
        width=video_width,
        height=video_height,
        looming_threshold=looming_threshold,
        fps=source_fps,
        reference_fps=30.0,
    )
    return {
        "video": str(video_path),
        "model": str(model_path),
        "device": device,
        "conf": conf,
        "fps": fps,
        "width": video_width,
        "height": video_height,
        "total_frames": total,
        "looming_threshold": looming_threshold,
        "reference_fps": 30.0,
        "records": detection_records,
        **report,
    }


def main(argv=None):
    args = parse_args(argv)
    report = process_video(
        args.video,
        model_path=args.model,
        looming_threshold=args.looming_threshold,
        device=args.device,
        conf=args.conf,
    )
    print(
        f"视频: {args.video}  fps={report['fps']:.0f} "
        f"总帧={report['total_frames']}"
    )
    print(f"模型: {args.model}  conf={args.conf}")
    print(f"looming阈值: {args.looming_threshold}")
    print("\n检出目标统计:", report["detection_stats"] or "无")
    print(f"追踪目标 {report['track_count']} 个")
    print(f"告警 {report['alert_count']} 次（警告+危险）")
    for alert in report["alerts"][:15]:
        print(
            f"帧{alert['frame']:4d} {alert['track_id']:20s} "
            f"{alert['cls']:16s} conf={alert['conf']} "
            f"{alert['level_name']} {alert['info']}"
        )
    if report["alert_count"] > 15:
        print(f"... 共 {report['alert_count']} 条，仅显示前 15 条")

    if args.report:
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"JSON报告: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
