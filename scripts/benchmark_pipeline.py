"""测量 YOLO + ByteTrack 管线的稳定逐帧延迟。"""

import argparse
import json
import math
import time
from statistics import mean, median

def summarize_timings(timings_ms, warmup, total_frames, target_fps=25.0):
    if not timings_ms:
        raise ValueError("timings_ms 不能为空")
    ordered = sorted(float(value) for value in timings_ms)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    mean_ms = mean(ordered)
    return {
        "warmup_frames": warmup,
        "total_frames": total_frames,
        "measured_frames": len(ordered),
        "mean_ms": round(mean_ms, 2),
        "median_ms": round(median(ordered), 2),
        "p95_ms": round(ordered[p95_index], 2),
        "steady_fps": round(1000.0 / mean_ms, 2),
        "target_fps": target_fps,
        "meets_25fps": 1000.0 / mean_ms >= target_fps,
        "meets_p95_latency": ordered[p95_index] <= 200.0,
    }


def benchmark(video_path, model_path="models/yolov8n.pt", device="mps", warmup=5):
    import cv2
    from ultralytics import YOLO

    model = YOLO(model_path)
    cap = cv2.VideoCapture(video_path)
    timings = []
    total_frames = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        start = time.perf_counter()
        model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            verbose=False,
            device=device,
        )
        total_frames += 1
        if total_frames > warmup:
            timings.append((time.perf_counter() - start) * 1000.0)
    cap.release()
    return summarize_timings(timings, warmup, total_frames)


def main():
    parser = argparse.ArgumentParser(description="Benchmark YOLO + ByteTrack")
    parser.add_argument("video")
    parser.add_argument("--model", default="models/yolov8n.pt")
    parser.add_argument("--device", default="mps", choices=["mps", "cpu"])
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    report = benchmark(args.video, args.model, args.device, args.warmup)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(f"JSON报告: {args.output}")
    else:
        print(text)


if __name__ == "__main__":
    main()
