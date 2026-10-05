"""批量运行 data/raw 中的视频检测并生成报告总览。"""

import argparse
import json
from pathlib import Path

try:
    from .detect_video import process_video
except ImportError:  # 支持直接执行脚本
    from detect_video import process_video


VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".avi", ".mkv"}


def discover_videos(raw_dir):
    raw_dir = Path(raw_dir)
    if not raw_dir.is_dir():
        return []
    return sorted(
        (path for path in raw_dir.iterdir() if path.is_file() and path.suffix.lower() in VIDEO_SUFFIXES),
        key=lambda path: path.name.lower(),
    )


def report_name(video_path):
    return f"{Path(video_path).stem}.json"


def process_batch(
    raw_dir="data/raw",
    output_dir="runs/video_reports",
    model_path="models/yolov8n.pt",
    looming_threshold=0.06,
    device=None,
    conf=0.25,
    min_approach_area=0.01,
    corridor_center=0.0,
    corridor_half_width=0.14,
    entry_lateral_threshold=0.04,
    entry_confirm_frames=3,
    prediction_frames=5,
    approach_vertical_threshold=0.001,
    walkable_model=None,
    walkable_interval=4,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    videos = discover_videos(raw_dir)
    processed = []
    failed = []
    guidance_state_counts = {}
    guidance_alert_videos = 0

    for video_path in videos:
        try:
            report = process_video(
                video_path,
                model_path=model_path,
                looming_threshold=looming_threshold,
                device=device,
                conf=conf,
                min_approach_area=min_approach_area,
                corridor_center=corridor_center,
                corridor_half_width=corridor_half_width,
                entry_lateral_threshold=entry_lateral_threshold,
                entry_confirm_frames=entry_confirm_frames,
                prediction_frames=prediction_frames,
                approach_vertical_threshold=approach_vertical_threshold,
                walkable_model=walkable_model,
                walkable_interval=walkable_interval,
            )
            target = output_dir / report_name(video_path)
            target.write_text(
                json.dumps(report, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            guidance = report.get("guidance") or {}
            state_counts = guidance.get("state_counts") or {}
            for state, count in state_counts.items():
                guidance_state_counts[state] = guidance_state_counts.get(state, 0) + int(count)
            if any(state in state_counts for state in ("CAUTION", "DANGER", "STOP", "UNKNOWN_SLOW_DOWN")):
                guidance_alert_videos += 1
            processed.append(
                {
                    "video": str(video_path),
                    "report": str(target),
                    "track_count": report["track_count"],
                    "alert_count": report["alert_count"],
                    "guidance_state_counts": dict(sorted(state_counts.items())),
                    "first_guidance_frame": next(
                        (
                            item.get("frame")
                            for item in (guidance.get("trace") or [])
                            if item.get("state") in {"CAUTION", "DANGER", "STOP", "UNKNOWN_SLOW_DOWN"}
                        ),
                        None,
                    ),
                }
            )
        except Exception as exc:  # 单段失败不应吞掉其他视频的结果
            failed.append({"video": str(video_path), "error": str(exc)})

    summary = {
        "raw_dir": str(raw_dir),
        "output_dir": str(output_dir),
        "model": model_path,
        "looming_threshold": looming_threshold,
        "min_approach_area": min_approach_area,
        "corridor_center": corridor_center,
        "corridor_half_width": corridor_half_width,
        "entry_lateral_threshold": entry_lateral_threshold,
        "entry_confirm_frames": entry_confirm_frames,
        "prediction_frames": prediction_frames,
        "approach_vertical_threshold": approach_vertical_threshold,
        "walkable_model": walkable_model,
        "walkable_interval": walkable_interval,
        "video_count": len(videos),
        "processed": processed,
        "failed": failed,
        "guidance_state_counts": dict(sorted(guidance_state_counts.items())),
        "guidance_alert_video_count": guidance_alert_videos,
        "ready_for_calibration": bool(videos) and not failed and bool(processed),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main():
    parser = argparse.ArgumentParser(description="批量运行真实视频检测")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("--output-dir", default="runs/video_reports")
    parser.add_argument("--model", default="models/yolov8n.pt")
    parser.add_argument("--device", default=None)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--looming-threshold", type=float, default=0.06)
    parser.add_argument("--min-approach-area", type=float, default=0.01)
    parser.add_argument("--corridor-center", type=float, default=0.0)
    parser.add_argument("--corridor-half-width", type=float, default=0.14)
    parser.add_argument("--entry-lateral-threshold", type=float, default=0.04)
    parser.add_argument("--entry-confirm-frames", type=int, default=3)
    parser.add_argument("--prediction-frames", type=int, default=5)
    parser.add_argument("--approach-vertical-threshold", type=float, default=0.001)
    parser.add_argument("--walkable-model", default=None)
    parser.add_argument("--walkable-interval", type=int, default=4)
    args = parser.parse_args()
    summary = process_batch(
        raw_dir=args.raw_dir,
        output_dir=args.output_dir,
        model_path=args.model,
        looming_threshold=args.looming_threshold,
        min_approach_area=args.min_approach_area,
        corridor_center=args.corridor_center,
        corridor_half_width=args.corridor_half_width,
        entry_lateral_threshold=args.entry_lateral_threshold,
        entry_confirm_frames=args.entry_confirm_frames,
        prediction_frames=args.prediction_frames,
        approach_vertical_threshold=args.approach_vertical_threshold,
        walkable_model=args.walkable_model,
        walkable_interval=args.walkable_interval,
        device=args.device,
        conf=args.conf,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["ready_for_calibration"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
