"""Convert manually reviewed JSON into a video-disjoint YOLO dataset."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
from collections import defaultdict
from pathlib import Path

try:
    from .build_pseudo_labels import assign_video_splits, box_to_yolo
except ImportError:
    from build_pseudo_labels import assign_video_splits, box_to_yolo


CLASS_IDS = {"electric_bicycle": 0, "person": 1, "bicycle": 2, "motorcycle": 3}


def annotation_to_rows(annotation, width, height):
    rows = []
    for item in annotation.get("boxes", []):
        if item.get("class") not in CLASS_IDS:
            raise ValueError(f"unknown class: {item.get('class')}")
        base = box_to_yolo(item["box"], width, height)
        rows.append(f"{CLASS_IDS[item['class']]}" + base[1:])
    return rows


def convert_review(review_path, output_dir):
    import cv2

    payload = json.loads(Path(review_path).read_text(encoding="utf-8"))
    annotations = payload.get("annotations", [])
    if not annotations:
        raise ValueError("review JSON contains no annotations")
    video_by_image = {item["image"]: item.get("video_id", Path(item["image"]).parent.name) for item in annotations}
    splits = assign_video_splits(list(video_by_image.values()))
    output = Path(output_dir)
    manifest = []
    for annotation in annotations:
        source = Path(annotation["image"])
        image = cv2.imread(str(source))
        if image is None:
            raise ValueError(f"cannot read image: {source}")
        height, width = image.shape[:2]
        video_id = video_by_image[str(source)]
        split = splits[video_id]
        stem = source.stem
        image_target = output / "images" / split / f"{video_id}_{stem}.jpg"
        label_target = output / "labels" / split / f"{video_id}_{stem}.txt"
        image_target.parent.mkdir(parents=True, exist_ok=True)
        label_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, image_target)
        label_target.write_text("\n".join(annotation_to_rows(annotation, width, height)) + ("\n" if annotation.get("boxes") else ""), encoding="utf-8")
        manifest.append({"image": str(image_target), "video_id": video_id, "split": split, "event_type": annotation.get("event_type")})
    (output / "data.yaml").write_text(
        f"path: {output.resolve()}\ntrain: images/train\nval: images/val\ntest: images/test\nnames:\n"
        "  0: electric_bicycle\n  1: person\n  2: bicycle\n  3: motorcycle\n",
        encoding="utf-8",
    )
    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest[0]))
        writer.writeheader(); writer.writerows(manifest)
    summary = {"images": len(manifest), "videos": len(splits), "annotation_source": str(review_path), "status": "manual_reviewed"}
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Convert manual review JSON into YOLO data")
    parser.add_argument("review_json", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()
    print(json.dumps(convert_review(args.review_json, args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
