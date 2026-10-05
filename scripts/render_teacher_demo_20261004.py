"""Render an archived presentation demo without changing model truth.

This older artifact may draw a future projection for comparison. The current
phone overlay intentionally shows only observed trails and risk boxes; this
script is not evidence of live phone behavior or collision prediction.
"""

import argparse
import csv
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


def load_rows(path, video_name):
    rows = {}
    with Path(path).open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("source_video") == video_name:
                rows[int(row["frame_index"])] = row
    return rows


def load_alerts(path, video_name):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    items = payload.get("alerts", []) if isinstance(payload, dict) else payload
    return {
        int(item["frame"]): item
        for item in items
        if item.get("video") in (None, video_name)
    }


def latest_alert(alerts, frame_index):
    candidates = [item for frame, item in alerts.items() if frame <= frame_index]
    return max(candidates, key=lambda item: int(item["frame"])) if candidates else None


def font(path, size, bold=False):
    try:
        return ImageFont.truetype(path, size=size)
    except OSError:
        fallback = "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf"
        return ImageFont.truetype(fallback, size=size)


def as_float(row, key, default=0.0):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError):
        return default


def area(row):
    return max(0.0, as_float(row, "x2") - as_float(row, "x1")) * max(
        0.0, as_float(row, "y2") - as_float(row, "y1")
    )


def stage_for(frame_index, alert):
    if alert and int(alert.get("level", 0)) >= 3:
        return 2, "明显接近", "DANGER"
    if alert:
        return 1, "可能影响路线", "NOTICE"
    return 0, "连续跟踪", "TRACKING"


def draw_round(draw, xy, fill, outline=None, radius=16, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def render(args):
    cap = cv2.VideoCapture(str(args.input))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open input: {args.input}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height)
    )
    if not writer.isOpened():
        raise RuntimeError(f"cannot open output: {output}")

    rows = load_rows(args.detections, args.video)
    alerts = load_alerts(args.alerts, args.video)
    font_path = args.font
    f_title = font(font_path, 34, bold=True)
    f_subtitle = font(font_path, 19)
    f_section = font(font_path, 23, bold=True)
    f_body = font(font_path, 20)
    f_small = font(font_path, 16)
    panel_x = int(width * 0.765)
    panel_w = width - panel_x
    frame_index = 0

    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        row = rows.get(frame_index)
        alert = latest_alert(alerts, frame_index)
        level, stage_cn, stage_en = stage_for(frame_index, alert)

        rgb = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)).convert("RGBA")
        draw = ImageDraw.Draw(rgb, "RGBA")

        # Presentation banner over the original scene.
        draw.rectangle((0, 0, panel_x, 66), fill=(7, 15, 29, 215))
        draw.text((24, 12), "BlindNav  路面预测线演示", font=f_title, fill=(255, 255, 255, 255))
        draw.text((24, 47), "连续跟踪 → 路线预测 → 提前提醒   /   candidate demo", font=f_small, fill=(180, 220, 255, 255))

        # Contact-point zoom makes the road anchor and line obvious to an audience.
        if row:
            x1, y1, x2, y2 = [int(as_float(row, key)) for key in ("x1", "y1", "x2", "y2")]
            pad = max(90, int(max(x2 - x1, y2 - y1) * 0.9))
            left = max(0, x1 - pad)
            top = max(66, y1 - pad)
            right = min(width, x2 + pad)
            bottom = min(height, y2 + pad)
            crop = rgb.crop((left, top, right, bottom)).convert("RGB")
            crop.thumbnail((390, 250), Image.Resampling.LANCZOS)
            inset_w, inset_h = crop.size
            inset_x, inset_y = 30, 92
            draw.rectangle((inset_x - 5, inset_y - 5, inset_x + inset_w + 5, inset_y + inset_h + 5), fill=(0, 0, 0, 220))
            rgb.paste(crop.convert("RGBA"), (inset_x, inset_y))
            draw = ImageDraw.Draw(rgb, "RGBA")
            draw.rectangle((inset_x, inset_y, inset_x + inset_w, inset_y + inset_h), outline=(255, 0, 255, 255), width=4)
            draw.text((inset_x + 12, inset_y + 8), "车轮接地点放大 / CONTACT POINT", font=f_small, fill=(255, 255, 255, 255), stroke_width=2, stroke_fill=(0, 0, 0, 210))

        # Right-hand explanation dashboard.
        draw.rectangle((panel_x, 0, width, height), fill=(8, 13, 24, 235))
        draw.text((panel_x + 28, 28), "EARLY WARNING", font=f_title, fill=(255, 255, 255, 255))
        draw.text((panel_x + 28, 70), "实时风险解释面板", font=f_subtitle, fill=(180, 220, 255, 255))

        stage_color = (70, 210, 110, 255) if level == 0 else (255, 165, 0, 255) if level == 1 else (255, 65, 65, 255)
        draw_round(draw, (panel_x + 24, 118, width - 24, 218), fill=tuple(stage_color), radius=18)
        draw.text((panel_x + 46, 133), stage_en, font=f_title, fill=(10, 18, 28, 255))
        draw.text((panel_x + 48, 181), stage_cn, font=f_section, fill=(10, 18, 28, 255))
        draw.text((panel_x + 48, 215), "提前判断，不等待碰撞", font=f_body, fill=(10, 18, 28, 255))

        y = 258
        draw.text((panel_x + 28, y), "当前证据", font=f_section, fill=(255, 255, 255, 255))
        y += 46
        metrics = []
        if row:
            current_area = area(row) / max(width * height, 1)
            prev_row = rows.get(max(0, frame_index - 10))
            prev_area = area(prev_row) / max(width * height, 1) if prev_row else current_area
            growth = current_area / max(prev_area, 1e-6) - 1.0
            cx = (as_float(row, "x1") + as_float(row, "x2")) / 2 / width - 0.5
            route = "路线走廊内" if abs(cx) <= 0.18 else "路线外侧"
            metrics = [
                ("目标", "2W-01  连续跟踪"),
                ("接近趋势", "↑  框面积持续变大" if growth > 0.02 else "监测中"),
                ("路线关系", route),
                ("预测窗口", "约 1.5 秒"),
            ]
        else:
            metrics = [("目标", "等待检测"), ("接近趋势", "--"), ("路线关系", "--"), ("预测窗口", "约 1.5 秒")]
        for key, value in metrics:
            draw.text((panel_x + 28, y), key, font=f_small, fill=(140, 170, 205, 255))
            draw.text((panel_x + 138, y), value, font=f_body, fill=(255, 255, 255, 255))
            y += 39

        y += 8
        draw.text((panel_x + 28, y), "可解释流程", font=f_section, fill=(255, 255, 255, 255))
        y += 42
        steps = [("检测框", True), ("同一目标", True), ("路面外推", True), ("提前提醒", level > 0)]
        for label, active in steps:
            color = (80, 220, 130, 255) if active else (105, 120, 145, 255)
            draw.ellipse((panel_x + 32, y + 4, panel_x + 52, y + 24), fill=color)
            draw.text((panel_x + 70, y), label, font=f_body, fill=(255, 255, 255, 255))
            y += 36

        # Warning timeline with exact trigger frames from the replay evidence.
        timeline_y = height - 116
        draw.text((panel_x + 28, timeline_y - 40), "预警时间线", font=f_section, fill=(255, 255, 255, 255))
        line_left, line_right = panel_x + 30, width - 30
        draw.line((line_left, timeline_y, line_right, timeline_y), fill=(95, 120, 155, 255), width=5)
        total_frames = 249
        marker_specs = []
        if alerts:
            first_frame = min(alerts)
            marker_specs.append((first_frame, "路线占用", (255, 165, 0, 255)))
            approach_frames = [
                frame for frame, item in alerts.items()
                if "快速接近" in str((item.get("info") or {}).get("reason", ""))
            ]
            if approach_frames:
                marker_specs.append((min(approach_frames), "接近", (255, 185, 0, 255)))
            danger_frames = [frame for frame, item in alerts.items() if int(item.get("level", 0)) >= 3]
            if danger_frames:
                marker_specs.append((min(danger_frames), "危险", (255, 65, 65, 255)))
        for mark, label, color in marker_specs:
            x = line_left + (line_right - line_left) * mark / total_frames
            draw.line((x, timeline_y - 16, x, timeline_y + 16), fill=color, width=5)
            draw.text((x - 20, timeline_y + 22), label, font=f_small, fill=color)
        current_x = line_left + (line_right - line_left) * frame_index / total_frames
        draw.ellipse((current_x - 8, timeline_y - 8, current_x + 8, timeline_y + 8), fill=(255, 255, 255, 255))
        draw.text((line_left, timeline_y + 54), f"frame {frame_index} / 249", font=f_small, fill=(180, 220, 255, 255))

        # Bottom disclosure keeps the demo honest while making the purpose clear.
        draw.rectangle((0, height - 44, panel_x, height), fill=(7, 15, 29, 215))
        draw.text((24, height - 34), "紫色 = 未来短时路面预测   |   这是候选演示，不代表已标定碰撞距离", font=f_small, fill=(230, 240, 255, 255))

        writer.write(cv2.cvtColor(np.array(rgb.convert("RGB")), cv2.COLOR_RGB2BGR))
        frame_index += 1

    cap.release()
    writer.release()
    report = {
        "video": args.video,
        "output": str(output.resolve()),
        "frames": frame_index,
        "alert_frames": sorted(alerts),
        "presentation_only": True,
        "candidate_only": True,
        "human_confirmed": False,
        "collision_guarantee": False,
    }
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--video", required=True)
    parser.add_argument("--detections", required=True)
    parser.add_argument("--alerts", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report")
    parser.add_argument("--font", default="C:/Windows/Fonts/msyh.ttc")
    render(parser.parse_args())


if __name__ == "__main__":
    main()
