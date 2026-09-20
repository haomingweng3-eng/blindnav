"""Select a small, evenly spaced manual-review set from an extracted-frame manifest."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable


def select_rows(rows: Iterable[dict[str, str]], max_per_video: int) -> list[dict[str, str]]:
    if max_per_video <= 0:
        raise ValueError("max_per_video must be positive")

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["video_id"]].append(dict(row))

    selected: list[dict[str, str]] = []
    for video_id in sorted(grouped):
        video_rows = sorted(grouped[video_id], key=lambda row: int(row["frame"]))
        if len(video_rows) <= max_per_video:
            indexes = range(len(video_rows))
        else:
            indexes = [round(i * (len(video_rows) - 1) / (max_per_video - 1)) for i in range(max_per_video)]
        for index in indexes:
            row = video_rows[index]
            row["annotation_status"] = "review"
            selected.append(row)
    return selected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--max-per-video", type=int, default=20)
    args = parser.parse_args()

    with args.manifest.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    selected = select_rows(rows, args.max_per_video)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0].keys()) if selected else list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(selected)
    print(f"selected={len(selected)} output={args.output}")


if __name__ == "__main__":
    main()
