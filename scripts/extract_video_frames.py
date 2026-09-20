"""Extract review/training frames from videos without inventing labels."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def sample_frame_indices(total_frames: int, stride: int):
    """Return one-based frame numbers at a fixed stride, including the last frame."""
    if total_frames <= 0:
        raise ValueError("total_frames must be positive")
    if stride <= 0:
        raise ValueError("stride must be positive")
    indices = list(range(1, total_frames + 1, stride))
    if indices[-1] != total_frames:
        indices.append(total_frames)
    return indices


def extract_video(video_path, output_dir, video_id=None, stride=5, jpeg_quality=95):
    """Write sampled frames and an unlabeled manifest for one video."""
    import cv2

    video_path = Path(video_path)
    output_dir = Path(output_dir)
    video_id = video_id or video_path.stem
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open video: {video_path}")
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if total_frames <= 0 or width <= 0 or height <= 0:
        cap.release()
        raise RuntimeError(f"invalid video metadata: {video_path}")

    frame_dir = output_dir / video_id
    frame_dir.mkdir(parents=True, exist_ok=True)
    wanted = set(sample_frame_indices(total_frames, stride))
    rows = []
    frame_no = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frame_no += 1
        if frame_no not in wanted:
            continue
        target = frame_dir / f"frame_{frame_no:06d}.jpg"
        if not cv2.imwrite(str(target), frame, [cv2.IMWRITE_JPEG_QUALITY, jpeg_quality]):
            cap.release()
            raise RuntimeError(f"failed to write frame: {target}")
        rows.append(
            {
                "video_id": video_id,
                "source_video": str(video_path),
                "frame": frame_no,
                "timestamp_s": round((frame_no - 1) / fps, 4),
                "fps": fps,
                "width": width,
                "height": height,
                "image": str(target),
                "annotation_status": "unlabeled",
            }
        )
    cap.release()
    return rows


def extract_directory(raw_dir, output_dir, stride=5):
    raw_dir = Path(raw_dir)
    output_dir = Path(output_dir)
    all_rows = []
    for video_path in sorted(raw_dir.iterdir()):
        if video_path.suffix.lower() not in {".mp4", ".mov", ".m4v", ".avi", ".mkv"}:
            continue
        all_rows.extend(extract_video(video_path, output_dir, stride=stride))
    if not all_rows:
        raise ValueError("no videos found")
    manifest = output_dir / "frames_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_rows[0]))
        writer.writeheader()
        writer.writerows(all_rows)
    (output_dir / "README.md").write_text(
        "# Unlabeled video frames\n\n"
        "These frames are not a training dataset until every target frame is reviewed and\n"
        "given bounding-box labels. Keep videos separated when creating train/val/test.\n",
        encoding="utf-8",
    )
    return {"videos": len({row["video_id"] for row in all_rows}), "frames": len(all_rows), "manifest": str(manifest)}


def main():
    parser = argparse.ArgumentParser(description="Extract unlabeled review frames from project videos")
    parser.add_argument("raw_dir")
    parser.add_argument("output_dir")
    parser.add_argument("--stride", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(extract_directory(args.raw_dir, args.output_dir, args.stride), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
