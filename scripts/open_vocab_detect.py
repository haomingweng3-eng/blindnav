"""Run chunked YOLO-World candidate detection on extracted local frames.

The output is a candidate list for human review, not ground-truth annotation.
Chunking is explicit because Ultralytics treats a list of paths as one source
batch and can otherwise allocate excessive MPS memory.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Iterator, Sequence


DEFAULT_CLASSES = [
    "electric bicycle",
    "electric scooter",
    "bicycle",
    "motorcycle",
    "person",
    "car",
    "truck",
    "bus",
]


def chunked(values: Sequence, size: int) -> Iterator[list]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    for start in range(0, len(values), size):
        yield list(values[start : start + size])


def canonical_class(name: str) -> str:
    if name in {"electric bicycle", "electric scooter", "e-bike", "electric_bike"}:
        return "electric_bicycle"
    return name


def scan_manifest(
    rows: Sequence[dict[str, str]],
    model_path: str,
    classes: Sequence[str] = DEFAULT_CLASSES,
    device: str = "mps",
    conf: float = 0.05,
    imgsz: int = 640,
    chunk_size: int = 32,
) -> dict:
    from ultralytics import YOLOWorld

    model = YOLOWorld(model_path)
    model.set_classes(list(classes))
    detections = []
    for chunk in chunked(list(rows), chunk_size):
        results = model.predict(
            [row["image"] for row in chunk],
            imgsz=imgsz,
            conf=conf,
            device=device,
            verbose=False,
        )
        for row, result in zip(chunk, results):
            for box, score, class_id in zip(
                result.boxes.xyxy.tolist(),
                result.boxes.conf.tolist(),
                result.boxes.cls.tolist(),
            ):
                source_class = result.names[int(class_id)]
                detections.append(
                    {
                        "video_id": row["video_id"],
                        "frame": int(row["frame"]),
                        "timestamp_s": float(row["timestamp_s"]),
                        "image": row["image"],
                        "source_class": source_class,
                        "canonical_class": canonical_class(source_class),
                        "confidence": round(float(score), 6),
                        "box": [round(float(value), 2) for value in box],
                        "annotation_status": "candidate_review",
                    }
                )
    return {
        "model": model_path,
        "classes": list(classes),
        "confidence_threshold": conf,
        "image_count": len(rows),
        "chunk_size": chunk_size,
        "detections": detections,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scan extracted frames with YOLO-World")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--model", default="models/yolov8s-worldv2.pt")
    parser.add_argument("--device", default="mps")
    parser.add_argument("--conf", type=float, default=0.05)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--chunk-size", type=int, default=32)
    args = parser.parse_args()

    with args.manifest.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    result = scan_manifest(
        rows,
        model_path=args.model,
        device=args.device,
        conf=args.conf,
        imgsz=args.imgsz,
        chunk_size=args.chunk_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"images={result['image_count']} detections={len(result['detections'])} output={args.output}")


if __name__ == "__main__":
    main()
