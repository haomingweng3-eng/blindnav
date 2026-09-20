"""Build a clearly marked, video-disjoint pseudo-label dataset from YOLO-World output."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path


def box_to_yolo(box, width: int, height: int) -> str:
    x1, y1, x2, y2 = [float(value) for value in box]
    x1, x2 = sorted((max(0.0, min(x1, width)), max(0.0, min(x2, width))))
    y1, y2 = sorted((max(0.0, min(y1, height)), max(0.0, min(y2, height))))
    cx = (x1 + x2) / 2 / width
    cy = (y1 + y2) / 2 / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return f"0 {cx:g} {cy:g} {bw:g} {bh:g}"


def assign_video_splits(video_ids: list[str]) -> dict[str, str]:
    ordered = sorted(set(video_ids))
    if len(ordered) < 3:
        raise ValueError("at least three videos are required for train/val/test")
    n_train = max(1, round(len(ordered) * 0.7))
    n_val = max(1, round(len(ordered) * 0.15))
    if n_train + n_val >= len(ordered):
        n_train = len(ordered) - 2
        n_val = 1
    return {
        video_id: ("train" if index < n_train else "val" if index < n_train + n_val else "test")
        for index, video_id in enumerate(ordered)
    }


def select_candidates(scan: dict, source_term: str, min_conf: float) -> list[dict]:
    return [
        detection
        for detection in scan.get("detections", [])
        if detection.get("term", detection.get("source_class")) == source_term
        and float(detection["confidence"]) >= min_conf
    ]


def build_dataset(scan_path: str | Path, output_dir: str | Path, min_conf: float = 0.7, source_term: str = "moped") -> dict:
    import cv2

    scan = json.loads(Path(scan_path).read_text(encoding="utf-8"))
    candidates = select_candidates(scan, source_term, min_conf)
    by_image = defaultdict(list)
    for detection in candidates:
        by_image[detection["image"]].append(detection)
    splits = assign_video_splits([d["video_id"] for d in candidates])
    output = Path(output_dir)
    manifest_rows = []
    counts = defaultdict(int)
    for source_image, detections in sorted(by_image.items()):
        first = detections[0]
        split = splits[first["video_id"]]
        image = cv2.imread(source_image)
        if image is None:
            raise ValueError(f"cannot read candidate image: {source_image}")
        height, width = image.shape[:2]
        stem = f"{first['video_id']}_{int(first['frame']):06d}"
        image_target = output / "images" / split / f"{stem}.jpg"
        label_target = output / "labels" / split / f"{stem}.txt"
        image_target.parent.mkdir(parents=True, exist_ok=True)
        label_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_image, image_target)
        label_target.write_text(
            "\n".join(box_to_yolo(d["box"], width, height) for d in detections) + "\n",
            encoding="utf-8",
        )
        counts[split] += 1
        manifest_rows.append(
            {
                "source_image": source_image,
                "output_image": str(image_target),
                "video_id": first["video_id"],
                "frame": first["frame"],
                "split": split,
                "source_term": source_term,
                "min_conf": min_conf,
                "annotation_status": "pseudo_candidate_review_required",
            }
        )

    data_yaml = output / "data.yaml"
    data_yaml.write_text(
        f"path: {output.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\n"
        "names:\n  0: electric_bicycle\n",
        encoding="utf-8",
    )
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]) if manifest_rows else ["source_image"])
        writer.writeheader()
        writer.writerows(manifest_rows)
    summary = {
        "source": str(scan_path),
        "min_conf": min_conf,
        "source_term": source_term,
        "images": len(manifest_rows),
        "boxes": len(candidates),
        "split_images": dict(counts),
        "video_count": len(splits),
        "annotation_status": "pseudo_candidate_review_required",
    }
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build pseudo-label candidates for local e-bike adaptation")
    parser.add_argument("scan_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--min-conf", type=float, default=0.7)
    parser.add_argument("--source-term", default="moped")
    args = parser.parse_args()
    print(json.dumps(build_dataset(args.scan_json, args.output_dir, args.min_conf, args.source_term), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
