"""检查真实视频采集目录与 manifest 是否一致。"""

import argparse
import csv
import json
from pathlib import Path


REQUIRED_COLUMNS = {"video_id", "filename", "scene"}


def inspect_collection(manifest_path, raw_dir):
    """返回采集进度报告；不依赖 OpenCV，视频可到位后再做模型回放。"""
    manifest_path = Path(manifest_path)
    raw_dir = Path(raw_dir)
    errors = []
    rows = []

    with manifest_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        missing_columns = sorted(REQUIRED_COLUMNS - columns)
        errors.extend(f"missing_column:{column}" for column in missing_columns)
        rows = list(reader)

    ids = [row.get("video_id", "").strip() for row in rows]
    filenames = [row.get("filename", "").strip() for row in rows]
    for value in sorted({item for item in ids if item and ids.count(item) > 1}):
        errors.append(f"duplicate_video_id:{value}")
    for value in sorted({item for item in filenames if item and filenames.count(item) > 1}):
        errors.append(f"duplicate_filename:{value}")

    missing = []
    present = []
    metadata_incomplete = []
    seen_paths = set()
    for row in rows:
        video_id = row.get("video_id", "").strip()
        filename = row.get("filename", "").strip()
        if not video_id or not filename:
            errors.append(f"empty_identity:{video_id or '<no-id>'}")
            continue

        file_path = raw_dir / filename
        if file_path in seen_paths:
            continue
        seen_paths.add(file_path)
        if not file_path.is_file():
            missing.append(video_id)
            continue
        if file_path.stat().st_size == 0:
            errors.append(f"empty_file:{filename}")
            continue
        if not row.get("duration_s", "").strip() or not row.get("valid_events", "").strip():
            metadata_incomplete.append(video_id)
        present.append(
            {
                "video_id": video_id,
                "filename": filename,
                "bytes": file_path.stat().st_size,
                "scene": row.get("scene", "").strip(),
            }
        )

    ready = bool(rows) and not errors and not missing and not metadata_incomplete
    return {
        "manifest": str(manifest_path),
        "raw_dir": str(raw_dir),
        "expected_count": len(rows),
        "present_count": len(present),
        "missing": missing,
        "present": present,
        "metadata_incomplete": metadata_incomplete,
        "errors": sorted(set(errors)),
        "ready": ready,
    }


def main():
    parser = argparse.ArgumentParser(description="检查真实视频采集目录")
    parser.add_argument("--manifest", default="data/collection_manifest.csv")
    parser.add_argument("--raw-dir", default="data/raw")
    parser.add_argument("-o", "--output")
    args = parser.parse_args()

    report = inspect_collection(args.manifest, args.raw_dir)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
