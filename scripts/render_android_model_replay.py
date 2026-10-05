"""Causal video replay of the shipped Android model and Kotlin risk engine.

prepare records real ONNX outputs; RecordedModelReplayTest performs the same
Android decoder/risk configuration; render visualizes its per-frame trace.
No labels or weights are changed. Desktop playback is not phone FPS evidence.
"""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import cv2
import numpy as np


def motion_gray(rgb):
    """Match the Kotlin 96px, 2x2 integer luminance sampler exactly."""
    height, width = rgb.shape[:2]
    ratio = min(1.0, 96 / max(width, height))
    out_width, out_height = max(1, int(width * ratio + .5)), max(1, int(height * ratio + .5))
    gray = np.zeros((out_height, out_width), dtype=np.int32)
    for oy in (0, 1):
        for ox in (0, 1):
            xs = np.minimum(((np.arange(out_width, dtype=np.float32) + np.float32(.25 + ox * .5)) * np.float32(width) / np.float32(out_width)).astype(int), width - 1)
            ys = np.minimum(((np.arange(out_height, dtype=np.float32) + np.float32(.25 + oy * .5)) * np.float32(height) / np.float32(out_height)).astype(int), height - 1)
            samples = rgb[ys[:, None], xs[None, :]].astype(np.int32)
            gray += (samples[..., 0] * 77 + samples[..., 1] * 150 + samples[..., 2] * 29) >> 8
    return (gray // 4).astype(np.uint8)


def motion_fixture(args):
    """Reuse frozen real ONNX outputs; add background pixels in a new directory."""
    directory = Path(args.output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    fixture = json.loads(Path(args.source_fixture).read_text(encoding="utf-8"))
    assert hashlib.sha256(Path(fixture["model"]).read_bytes()).hexdigest() == fixture["model_sha256"]
    assert args.sample_stride > 0
    gray_file = directory / "background_gray.u8"
    cap = cv2.VideoCapture(fixture["video"])
    assert cap.isOpened()
    try:
        with gray_file.open("xb") as handle:
            for meta in fixture["frames"]:
                ok, frame = cap.read()
                if not ok:
                    raise RuntimeError("Video ended before recorded model outputs")
                rgb = cv2.cvtColor(cv2.resize(frame, (meta["width"], meta["height"])), cv2.COLOR_BGR2RGB)
                gray = motion_gray(rgb)
                handle.write(gray.tobytes())
            gray_height, gray_width = gray.shape
    finally:
        cap.release()
    fixture.update(gray_file=str(gray_file), gray_width=gray_width, gray_height=gray_height,
                   sample_stride=args.sample_stride, trace_file=str(directory / "android_trace.json"))
    with (directory / "fixture.json").open("x", encoding="utf-8") as handle:
        json.dump(fixture, handle, indent=2)
    print(json.dumps({"fixture": str(directory / "fixture.json"), "sample_stride": args.sample_stride,
                      "sample_fps": fixture["fps"] / args.sample_stride, "gray_shape": [gray_height, gray_width]}))


def prepare(args):
    import onnxruntime as ort
    directory = Path(args.output_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    model = Path(args.model).resolve()
    session = ort.InferenceSession(str(model), providers=["CPUExecutionProvider"])
    assert session.get_inputs()[0].shape == [1, 3, 320, 320]
    shape = session.get_outputs()[0].shape
    assert shape[0] == 1 and shape[1] >= 5
    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        raise RuntimeError("Cannot open original video")
    fps = cap.get(cv2.CAP_PROP_FPS)
    source_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    source_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    width = 640
    height = round(width * source_height / source_width)
    ratio = min(320 / width, 320 / height)
    scaled_width, scaled_height = round(width * ratio), round(height * ratio)
    pad_left, pad_top = (320 - scaled_width) // 2, (320 - scaled_height) // 2
    xs = np.minimum((np.arange(scaled_width) / ratio).astype(int), width - 1)
    ys = np.minimum((np.arange(scaled_height) / ratio).astype(int), height - 1)
    raw_file = directory / "onnx_outputs.f32"
    frames = []
    try:
        with raw_file.open("xb") as handle:
            index = 0
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                # Emulate the camera analysis dimensions; the letterbox uses
                # the exact nearest-neighbour sampling of the Kotlin code.
                rgb = cv2.cvtColor(cv2.resize(frame, (width, height)), cv2.COLOR_BGR2RGB)
                tensor = np.full((320, 320, 3), 114 / 255, dtype=np.float32)
                tensor[pad_top:pad_top + scaled_height, pad_left:pad_left + scaled_width] = rgb[ys[:, None], xs[None, :]] / 255.0
                output = session.run(None, {session.get_inputs()[0].name: tensor.transpose(2, 0, 1)[None].copy()})[0]
                handle.write(output.astype("<f4").tobytes())
                frames.append(dict(source_frame=index, timestamp_ms=round(index * 1000 / fps), width=width, height=height,
                                   ratio=ratio, pad_left=pad_left, pad_top=pad_top))
                index += 1
    finally:
        cap.release()
    fixture = dict(video=str(Path(args.video).resolve()), source_width=source_width, source_height=source_height, fps=fps,
                   model=str(model), model_asset=model.name, model_sha256=hashlib.sha256(model.read_bytes()).hexdigest(),
                   input_size=320, channels=shape[1], candidates=shape[2], raw_file=str(raw_file),
                   trace_file=str(directory / "android_trace.json"), frames=frames)
    (directory / "fixture.json").write_text(json.dumps(fixture, indent=2), encoding="utf-8")
    print(json.dumps({"frames": len(frames), "model_sha256": fixture["model_sha256"], "fixture": str(directory / "fixture.json")}))


def render(args):
    from PIL import Image, ImageDraw, ImageFont
    directory = Path(args.output_dir).resolve()
    fixture = json.loads((directory / "fixture.json").read_text(encoding="utf-8"))
    trace = json.loads((directory / "android_trace.json").read_text(encoding="utf-8"))
    assert fixture["model_sha256"] == trace["model_sha256"]
    cap = cv2.VideoCapture(fixture["video"])
    width = 1280
    height = round(width * fixture["source_height"] / fixture["source_width"])
    output = directory / "android320_route_prediction.mp4"
    replay_fps = fixture["fps"] / fixture.get("sample_stride", 1)
    writer = cv2.VideoWriter(str(output), cv2.VideoWriter_fourcc(*"mp4v"), replay_fps, (width, height + 96))
    if not writer.isOpened():
        raise RuntimeError("Cannot create replay video")
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 24)
    font_small = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
    first_notice = first_danger = None
    guidance_counts = Counter()
    first_guidance = {}
    render_count = 0
    source_index = -1
    for record in trace["frames"]:
        index = record["source_frame"]
        while source_index < index:
            ok, frame = cap.read()
            if not ok:
                raise RuntimeError("Source ended before trace")
            source_index += 1
        vis = cv2.resize(frame, (width, height))
        shaded = vis.copy()
        cv2.rectangle(shaded, (int(width * .36), int(height * .38)), (int(width * .64), height), (110, 65, 20), -1)
        vis = cv2.addWeighted(shaded, .12, vis, .88, 0)
        # Use only the current snapshot, never retain an earlier alert as
        # perpetual danger when a vehicle disappears or leaves the route.
        max_level = max((track["risk_level"] for track in record["tracks"]), default=0)
        if max_level >= 1 and first_notice is None:
            first_notice = index
        if max_level == 2 and first_danger is None:
            first_danger = index
        scale = width / fixture["frames"][index]["width"]
        for track in record["tracks"]:
            box = track["box"]
            contact_y = track["history"][-1]["y"] if track["history"] else 0.0
            contact_x = (box[0] + box[2]) / 2.0
            route_relevant = contact_y >= fixture["frames"][index]["height"] * 0.38 and 0.36 <= contact_x / fixture["frames"][index]["width"] <= 0.64
            if track["risk_level"] == 0 and not route_relevant:
                continue
            x1, y1, x2, y2 = [round(value * scale) for value in track["box"]]
            uncertain_route_track = track["risk_level"] == 0 and route_relevant and record.get("guidance_state") == "UNKNOWN_SLOW_DOWN"
            display_level = 1 if uncertain_route_track else track["risk_level"]
            color = [(30, 220, 70), (0, 180, 255), (30, 30, 255)][display_level]
            cv2.rectangle(vis, (x1, y1), (x2, y2), color, 3)
            label = track["track_id"] + (" SLOW DOWN" if uncertain_route_track else "")
            cv2.putText(vis, label, (x1, max(26, y1 - 10)), cv2.FONT_HERSHEY_SIMPLEX, .65, color, 2)
            points = track["history"]
            for old, new in zip(points, points[1:]):
                cv2.line(vis, (round(old["x"] * scale), round(old["y"] * scale)),
                         (round(new["x"] * scale), round(new["y"] * scale)), (255, 210, 0), 4)
        canvas = np.full((height + 96, width, 3), 18, dtype=np.uint8)
        canvas[:height] = vis
        pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
        draw = ImageDraw.Draw(pil)
        stage = ["跟踪中", "注意：可能影响行进路线", "危险：路线内持续接近"][max_level]
        guidance_state = record.get("guidance_state")
        guidance_names = {
            "KEEP_STRAIGHT": "保持直行",
            "MOVE_LEFT": "向左绕行",
            "MOVE_RIGHT": "向右绕行",
            "STOP": "停止",
            "CAUTION": "注意",
            "DANGER": "危险",
            "UNKNOWN_SLOW_DOWN": "前方不明，请减速",
        }
        if guidance_state:
            guidance_counts[guidance_state] += 1
            first_guidance.setdefault(guidance_state, index)
            stage = f"{stage}  |  引路：{guidance_names.get(guidance_state, guidance_state)}"
        color = [(100, 230, 140), (255, 185, 50), (255, 80, 80)][max_level]
        draw.rectangle((16, 12, 680, 58), fill=(12, 20, 32))
        draw.text((28, 19), stage, font=font, fill=color)
        motion = record.get("background_motion", {})
        compensation = "背景平移补偿" if motion.get("reliable") else "补偿不可用"
        draw.text((20, height + 8), f"手机同款模型 + Kotlin | {index / fixture['fps']:.2f}s | 帧 {index} | {compensation}", font=font, fill=(240, 240, 240))
        draw.text((20, height + 47), "青色：已走轨迹  淡蓝：中央路线  |  离线回放，不代表手机实测速度或碰撞保证", font=font_small, fill=(180, 200, 220))
        writer.write(cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR))
        if index in (100, 130, 167) or index in (first_notice, first_danger):
            pil.save(directory / f"frame_{index:04d}.jpg")
        render_count += 1
    cap.release()
    writer.release()
    summary = dict(video=str(output), model=str(fixture["model"]), model_sha256=fixture["model_sha256"],
                   frames=render_count, first_notice_frame=first_notice, first_danger_frame=first_danger,
                   first_notice_seconds=None if first_notice is None else first_notice / fixture["fps"],
                   first_danger_seconds=None if first_danger is None else first_danger / fixture["fps"],
                   phone_fps_verified=False, risk_engine="Actual Android Kotlin TemporalRiskEngine", new_training=False)
    summary.update(guidance_state_counts=dict(sorted(guidance_counts.items())),
                   first_guidance_frame=first_guidance,
                   guidance_engine="Android GuidanceEngine + GeometryWalkableRegionEstimator")
    motions = [item["background_motion"] for item in trace["frames"] if "background_motion" in item]
    summary.update(sample_fps=replay_fps, background_motion_evaluated=bool(motions),
                   background_motion_reliable_frames=sum(item["reliable"] for item in motions))
    (directory / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["prepare", "render", "motion-fixture"])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--video")
    parser.add_argument("--model")
    parser.add_argument("--source-fixture")
    parser.add_argument("--sample-stride", type=int, default=1)
    parsed = parser.parse_args()
    {"prepare": prepare, "render": render, "motion-fixture": motion_fixture}[parsed.mode](parsed)
