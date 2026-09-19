"""测量 ONNX Runtime 单模型推理延迟，不包含摄像头和 Android 系统开销。"""

import argparse
import json
import math
import time
from statistics import mean, median

import numpy as np

try:
    from .onnx_inference import create_session, letterbox
except ImportError:  # 支持直接执行脚本
    from onnx_inference import create_session, letterbox


def summarize_onnx_timings(timings_ms, warmup, total_frames):
    if not timings_ms:
        raise ValueError("timings_ms 不能为空")
    ordered = sorted(float(value) for value in timings_ms)
    p95_index = max(0, math.ceil(len(ordered) * 0.95) - 1)
    average = mean(ordered)
    return {
        "warmup_frames": warmup,
        "total_frames": total_frames,
        "measured_frames": len(ordered),
        "mean_ms": round(average, 2),
        "median_ms": round(median(ordered), 2),
        "p95_ms": round(ordered[p95_index], 2),
        "steady_fps": round(1000.0 / average, 2),
    }


def benchmark_onnx(model_path, frames=30, warmup=5, size=640):
    if frames <= warmup:
        raise ValueError("frames 必须大于 warmup")
    image = np.zeros((size, size, 3), dtype=np.uint8)
    tensor, _, _ = letterbox(image, size)
    session = create_session(model_path)
    input_name = session.get_inputs()[0].name
    timings = []
    for index in range(frames):
        start = time.perf_counter()
        session.run(None, {input_name: tensor})
        if index >= warmup:
            timings.append((time.perf_counter() - start) * 1000.0)
    return summarize_onnx_timings(timings, warmup, frames)


def main():
    parser = argparse.ArgumentParser(description="Benchmark ONNX Runtime inference")
    parser.add_argument("model", nargs="?", default="models/yolov8n.onnx")
    parser.add_argument("--frames", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("-o", "--output")
    args = parser.parse_args()
    result = benchmark_onnx(args.model, args.frames, args.warmup)
    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            handle.write(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
