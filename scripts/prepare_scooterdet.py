"""Convert ScooterDet LabelMe annotations into a reproducible YOLO dataset.

The source dataset contains continuous frame sequences. This module assigns whole
sequences to one split so adjacent frames cannot leak between train/val/test.
The generated dataset is intended to live outside the repository.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import shutil
from collections import Counter
from pathlib import Path


CLASS_NAMES = ["electric_bicycle", "person", "bicycle", "motorcycle"]
SOURCE_TO_CLASS = {
    "scooter": "electric_bicycle",
    "person": "person",
    "bicycle": "bicycle",
    "motorcycle": "motorcycle",
}
FRAME_RE = re.compile(r"(?:frame_)?(\d+)", re.IGNORECASE)


def _frame_id(path: Path) -> int:
    match = FRAME_RE.search(path.stem)
    if not match:
        raise ValueError(f"cannot parse numeric frame id from {path.name}")
    return int(match.group(1))


def _class_counts(annotation: dict) -> Counter:
    counts = Counter()
    for shape in annotation.get("shapes", []):
        mapped = SOURCE_TO_CLASS.get(str(shape.get("label", "")).strip().lower())
        if mapped:
            counts[mapped] += 1
    return counts


def _normalise_rectangle(points, width: float, height: float):
    if len(points) < 2 or width <= 0 or height <= 0:
        return None
    try:
        x_values = [float(point[0]) for point in points]
        y_values = [float(point[1]) for point in points]
    except (TypeError, ValueError, IndexError):
        return None
    x1 = max(0.0, min(width, min(x_values)))
    y1 = max(0.0, min(height, min(y_values)))
    x2 = max(0.0, min(width, max(x_values)))
    y2 = max(0.0, min(height, max(y_values)))
    if x2 <= x1 or y2 <= y1:
        return None
    return x1, y1, x2, y2


def convert_annotation(annotation: dict):
    """Return YOLO rows and mapped class counts for one LabelMe annotation."""
    width = float(annotation.get("imageWidth", 0))
    height = float(annotation.get("imageHeight", 0))
    rows = []
    counts = Counter()
    class_ids = {name: index for index, name in enumerate(CLASS_NAMES)}
    for shape in annotation.get("shapes", []):
        label = str(shape.get("label", "")).strip().lower()
        mapped = SOURCE_TO_CLASS.get(label)
        if mapped is None or shape.get("shape_type", "rectangle") != "rectangle":
            continue
        rect = _normalise_rectangle(shape.get("points", []), width, height)
        if rect is None:
            continue
        x1, y1, x2, y2 = rect
        cx = ((x1 + x2) / 2) / width
        cy = ((y1 + y2) / 2) / height
        box_width = (x2 - x1) / width
        box_height = (y2 - y1) / height
        rows.append(
            f"{class_ids[mapped]} {cx:.6f} {cy:.6f} {box_width:.6f} {box_height:.6f}"
        )
        counts[mapped] += 1
    return rows, dict(counts)


def group_frame_records(records, max_gap: int = 10):
    """Group sorted numeric frames while a gap is at most ``max_gap``."""
    if max_gap < 0:
        raise ValueError("max_gap must be non-negative")
    ordered = sorted(records, key=lambda item: item["frame_id"])
    groups = []
    for record in ordered:
        if not groups or record["frame_id"] - groups[-1][-1]["frame_id"] > max_gap:
            groups.append([])
        groups[-1].append(record)
    return groups


def _group_size(group):
    return len(group)


def _group_rare_count(group, rare_class="electric_bicycle"):
    return sum(record.get("class_counts", {}).get(rare_class, 0) for record in group)


def assign_group_splits(groups, train_ratio=0.8, val_ratio=0.1, seed=0):
    """Assign every complete frame group to train, val or test.

    At least one rare-class-containing group is reserved for validation and test
    when the source has enough such groups. The remaining groups are greedily
    packed toward the requested image ratios.
    """
    if not groups:
        return {}
    if not 0 < train_ratio < 1 or not 0 < val_ratio < 1 or train_ratio + val_ratio >= 1:
        raise ValueError("train_ratio and val_ratio must leave a positive test ratio")

    rng = random.Random(seed)
    total = sum(_group_size(group) for group in groups)
    targets = {
        "train": total * train_ratio,
        "val": total * val_ratio,
        "test": total * (1 - train_ratio - val_ratio),
    }
    assignments = {}
    remaining = set(range(len(groups)))
    rare_ids = [i for i, group in enumerate(groups) if _group_rare_count(group) > 0]
    rng.shuffle(rare_ids)
    target_rare = sum(_group_rare_count(groups[i]) for i in rare_ids) / 3

    # Keep the largest rare-class sequence in training. It carries the most
    # intra-sequence variation and is too valuable to spend as a holdout.
    largest_rare_id = max(rare_ids, key=lambda i: _group_rare_count(groups[i])) if rare_ids else None
    anchor_candidates = [i for i in rare_ids if i != largest_rare_id]
    # Pick two rare groups close to the per-split target for validation/test.
    anchor_candidates.sort(
        key=lambda i: (abs(_group_rare_count(groups[i]) - target_rare), _group_rare_count(groups[i]))
    )
    for split in ("val", "test"):
        if len(anchor_candidates) == 0:
            break
        selected = anchor_candidates.pop(0)
        assignments[selected] = split
        remaining.discard(selected)

    assigned_sizes = Counter()
    for group_id, split in assignments.items():
        assigned_sizes[split] += _group_size(groups[group_id])

    # Large groups first keeps the split sizes stable while preserving whole
    # sequences. Ties are randomized deterministically by the caller's seed.
    rest = list(remaining)
    rng.shuffle(rest)
    rest.sort(key=lambda i: _group_size(groups[i]), reverse=True)
    for group_id in rest:
        split = min(
            ("train", "val", "test"),
            key=lambda name: (assigned_sizes[name] - targets[name], assigned_sizes[name]),
        )
        assignments[group_id] = split
        assigned_sizes[split] += _group_size(groups[group_id])
    return assignments


def _write_yaml(path: Path, dataset_root: Path):
    lines = [
        f"path: {dataset_root.as_posix()}",
        "train: images/train",
        "val: images/val",
        "test: images/test",
        "names:",
    ]
    lines.extend(f"  {index}: {name}" for index, name in enumerate(CLASS_NAMES))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def prepare_dataset(source_dir, output_dir, max_gap=10, train_ratio=0.8, val_ratio=0.1, seed=0):
    """Build a YOLO directory from an extracted ``Mixed`` directory."""
    source_dir = Path(source_dir)
    output_dir = Path(output_dir)
    image_dir = source_dir / "images"
    label_dir = source_dir / "labels"
    if not image_dir.is_dir() or not label_dir.is_dir():
        raise FileNotFoundError("source must contain images/ and labels/")

    records = []
    for image_path in sorted(image_dir.glob("*")):
        if image_path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
            continue
        annotation_path = label_dir / f"{image_path.stem}.json"
        if not annotation_path.is_file():
            continue
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        rows, counts = convert_annotation(annotation)
        records.append(
            {
                "image_path": image_path,
                "annotation_path": annotation_path,
                "frame_id": _frame_id(image_path),
                "rows": rows,
                "class_counts": counts,
            }
        )
    if not records:
        raise ValueError("no image/annotation pairs found")

    groups = group_frame_records(records, max_gap=max_gap)
    assignments = assign_group_splits(groups, train_ratio=train_ratio, val_ratio=val_ratio, seed=seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    for split in ("train", "val", "test"):
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)

    manifest_rows = []
    image_counts = Counter()
    class_counts = Counter()
    group_index = {id(record): group_id for group_id, group in enumerate(groups) for record in group}
    for record in records:
        split = assignments[group_index[id(record)]]
        image_target = output_dir / "images" / split / record["image_path"].name
        label_target = output_dir / "labels" / split / f"{record['image_path'].stem}.txt"
        shutil.copy2(record["image_path"], image_target)
        label_target.write_text("\n".join(record["rows"]) + ("\n" if record["rows"] else ""), encoding="utf-8")
        image_counts[split] += 1
        class_counts.update(record["class_counts"])
        manifest_rows.append(
            {
                "image": str(image_target.relative_to(output_dir)),
                "label": str(label_target.relative_to(output_dir)),
                "frame_id": record["frame_id"],
                "group_id": group_index[id(record)],
                "split": split,
                **{name: record["class_counts"].get(name, 0) for name in CLASS_NAMES},
            }
        )

    with (output_dir / "split_manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(manifest_rows[0]))
        writer.writeheader()
        writer.writerows(sorted(manifest_rows, key=lambda row: row["frame_id"]))
    _write_yaml(output_dir / "data.yaml", output_dir)
    summary = {
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "class_names": CLASS_NAMES,
        "images_total": len(records),
        "groups_total": len(groups),
        "images_by_split": dict(image_counts),
        "boxes_by_class": dict(class_counts),
        "max_gap": max_gap,
        "seed": seed,
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Prepare ScooterDet as a four-class YOLO dataset")
    parser.add_argument("source_dir", help="extracted Mixed directory")
    parser.add_argument("output_dir", help="generated dataset directory; keep outside Git")
    parser.add_argument("--max-gap", type=int, default=10)
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=20260919)
    args = parser.parse_args()
    result = prepare_dataset(
        args.source_dir,
        args.output_dir,
        max_gap=args.max_gap,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    raise SystemExit(main())
