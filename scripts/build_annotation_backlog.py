"""Build a prioritized manual-review CSV from detector candidate boxes."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


VEHICLE_CANDIDATE_CLASSES = {"motorcycle", "bicycle", "electric_bicycle", "scooter"}


def _image_parts(image: str) -> tuple[str, int]:
    path = Path(image)
    video_id = path.parent.name
    stem = path.stem
    frame_text = stem.rsplit("_", 1)[-1]
    try:
        frame = int(frame_text)
    except ValueError:
        frame = -1
    return video_id, frame


def build_backlog(candidates, reviewed_images=None, target_video_ids=None):
    reviewed = {str(Path(path).resolve()) for path in (reviewed_images or set())}
    targets = set(target_video_ids or set())
    grouped = defaultdict(list)
    for candidate in candidates:
        if candidate.get("source_class") not in VEHICLE_CANDIDATE_CLASSES:
            continue
        image = str(Path(candidate["image"]).resolve())
        if image in reviewed:
            continue
        grouped[image].append(candidate)

    rows = []
    for image, detections in grouped.items():
        video_id, frame = _image_parts(image)
        rows.append(
            {
                "image": image,
                "video_id": video_id,
                "frame": frame,
                "candidate_count": len(detections),
                "max_confidence": round(max(float(d["confidence"]) for d in detections), 4),
                "source_classes": ",".join(sorted({str(d["source_class"]) for d in detections})),
                "priority": 0 if video_id in targets else 1,
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            row["priority"],
            -row["candidate_count"],
            -row["max_confidence"],
            row["video_id"],
            row["frame"],
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidates", type=Path)
    parser.add_argument("annotations", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--target-video", action="append", default=[])
    args = parser.parse_args()

    candidate_payload = json.loads(args.candidates.read_text(encoding="utf-8"))
    annotation_payload = json.loads(args.annotations.read_text(encoding="utf-8"))
    reviewed = {item["image"] for item in annotation_payload.get("annotations", [])}
    rows = build_backlog(candidate_payload.get("detections", []), reviewed, set(args.target_video))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["image"])
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
