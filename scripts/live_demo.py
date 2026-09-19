"""实时管线：rawvideo -> YOLO + ByteTrack -> 风险引擎 -> 可视化。

默认从 stdin 读取 1280x720 BGR rawvideo。使用 ``--headless`` 和
``--max-frames`` 可以在没有摄像头权限或 GUI 的环境中做端到端回归。
"""

import argparse
import json
import sys
import threading
import time
from collections import deque
from pathlib import Path


DEFAULT_WIDTH = 1280
DEFAULT_HEIGHT = 720


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="BlindNav 实时视频 Demo")
    parser.add_argument("--width", type=int, default=DEFAULT_WIDTH)
    parser.add_argument("--height", type=int, default=DEFAULT_HEIGHT)
    parser.add_argument("--model", default="models/yolov8n.pt")
    parser.add_argument("--device", choices=["mps", "cpu"], default="mps")
    parser.add_argument("--input-fps", type=float, default=30.0)
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--max-frames", type=int, default=None)
    parser.add_argument("--looming-threshold", type=float, default=0.06)
    parser.add_argument("--report", help="可选的实时运行 JSON 报告路径")
    return parser.parse_args(argv)


def capture_rawvideo(stream, frame_q, stop_event, width, height):
    """后台读取 BGR rawvideo，只保留最新一帧。"""
    import numpy as np

    need = width * height * 3
    buffer = b""
    source_frame_idx = 0
    while not stop_event.is_set():
        chunk = stream.buffer.read(need - len(buffer) if len(buffer) < need else 8192)
        if not chunk:
            break
        buffer += chunk
        while len(buffer) >= need:
            frame = (
                np.frombuffer(buffer[:need], dtype=np.uint8)
                .reshape(height, width, 3)
                .copy()
            )
            source_frame_idx += 1
            frame_q.append((source_frame_idx, frame))
            buffer = buffer[need:]


def run_demo(
    stream=None,
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    model_path="models/yolov8n.pt",
    device="mps",
    headless=False,
    max_frames=None,
    looming_threshold=0.06,
    input_fps=30.0,
    reference_fps=30.0,
):
    import cv2
    from ultralytics import YOLO

    sys.path.insert(0, "scripts")
    from risk_engine import LVL_NAME, TrackState

    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")
    if max_frames is not None and max_frames <= 0:
        raise ValueError("max_frames must be positive")
    if input_fps <= 0 or reference_fps <= 0:
        raise ValueError("input_fps and reference_fps must be positive")

    stream = stream or sys.stdin
    model = YOLO(model_path)
    alert_classes = {
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
    level_color = {
        0: (100, 100, 100),
        1: (0, 200, 200),
        2: (0, 120, 255),
        3: (0, 0, 255),
    }
    frame_q = deque(maxlen=1)
    stop_event = threading.Event()
    capture_thread = threading.Thread(
        target=capture_rawvideo,
        args=(stream, frame_q, stop_event, width, height),
        daemon=True,
    )
    capture_thread.start()

    tracks = {}
    processed_frames = 0
    last_source_frame = 0
    timings_ms = []
    alert_count = 0
    scale = 640 / max(height, width)
    print("等待视频流... (q 退出)")

    try:
        while True:
            if not frame_q:
                if not capture_thread.is_alive():
                    break
                if not headless:
                    cv2.waitKey(1)
                continue

            source_frame_idx, frame = frame_q[-1]
            processed_frames += 1
            last_source_frame = source_frame_idx
            start = time.perf_counter()
            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                verbose=False,
                device=device,
                imgsz=480,
            )
            tracked = results[0]
            vis = frame.copy()

            if tracked.boxes.id is not None:
                for box, conf, cls, tracked_id in zip(
                    tracked.boxes.xyxy,
                    tracked.boxes.conf,
                    tracked.boxes.cls,
                    tracked.boxes.id,
                ):
                    name = model.names[int(cls)]
                    if name not in alert_classes:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in box]
                    track_key = f"{name}_{int(tracked_id)}"
                    if track_key not in tracks:
                        tracks[track_key] = TrackState(
                            track_key,
                            name,
                            looming_threshold=looming_threshold,
                            fps=input_fps,
                            reference_fps=reference_fps,
                        )
                    state = tracks[track_key]
                    state.update(
                        [x1 * scale, y1 * scale, x2 * scale, y2 * scale],
                        frame_idx=source_frame_idx,
                    )
                    level, info = state.assess(source_frame_idx)
                    if level >= 2:
                        alert_count += 1

                    if not headless:
                        color = level_color[level]
                        cv2.rectangle(vis, (x1, y1), (x2, y2), color, 2)
                        label = f"{name} {LVL_NAME[level]} {info.get('reason', '')}"
                        cv2.putText(
                            vis,
                            label,
                            (x1, max(y1 - 10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            color,
                            2,
                        )

            timings_ms.append((time.perf_counter() - start) * 1000.0)
            if not headless:
                recent = timings_ms[-30:]
                fps = 1000 / (sum(recent) / len(recent))
                cv2.putText(
                    vis,
                    f"FPS: {fps:.1f} f:{source_frame_idx}",
                    (10, 25),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
                cv2.imshow("blindnav", vis)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

            if max_frames is not None and processed_frames >= max_frames:
                break
    finally:
        stop_event.set()
        capture_thread.join(timeout=1.0)
        if not headless:
            cv2.destroyAllWindows()

    recent = timings_ms[-30:]
    avg_fps = 0.0 if not recent else 1000 / (sum(recent) / len(recent))
    report = {
        "frames": processed_frames,
        "last_source_frame": last_source_frame,
        "tracks": len(tracks),
        "alerts": alert_count,
        "avg_recent_fps": round(avg_fps, 2),
    }
    print(
        f"结束。处理 {processed_frames} 帧（源帧到 {last_source_frame}），"
        f"轨迹 {len(tracks)} 个，"
        f"告警 {alert_count} 次，最近 FPS {avg_fps:.1f}"
    )
    return report


def main(argv=None):
    args = parse_args(argv)
    report = run_demo(
        width=args.width,
        height=args.height,
        model_path=args.model,
        device=args.device,
        headless=args.headless,
        max_frames=args.max_frames,
        looming_threshold=args.looming_threshold,
        input_fps=args.input_fps,
        reference_fps=30.0,
    )
    report.update(
        {
            "width": args.width,
            "height": args.height,
            "device": args.device,
            "model": args.model,
            "looming_threshold": args.looming_threshold,
            "input_fps": args.input_fps,
            "reference_fps": 30.0,
            "headless": args.headless,
        }
    )
    if args.report:
        Path(args.report).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"JSON报告: {args.report}")


if __name__ == "__main__":
    main()
