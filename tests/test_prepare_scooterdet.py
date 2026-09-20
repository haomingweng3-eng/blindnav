import json
import tempfile
import unittest
from pathlib import Path

from scripts.prepare_scooterdet import (
    CLASS_NAMES,
    assign_group_splits,
    convert_annotation,
    group_frame_records,
    prepare_dataset,
)


class ScooterDetConversionTests(unittest.TestCase):
    def test_converts_and_clips_labelme_rectangles_to_project_classes(self):
        annotation = {
            "imageWidth": 100,
            "imageHeight": 50,
            "shapes": [
                {"label": "scooter", "shape_type": "rectangle", "points": [[-10, 5], [60, 45]]},
                {"label": "person", "shape_type": "rectangle", "points": [[10, 10], [30, 30]]},
                {"label": "car", "shape_type": "rectangle", "points": [[0, 0], [10, 10]]},
            ],
        }

        rows, counts = convert_annotation(annotation)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], "0 0.300000 0.500000 0.600000 0.800000")
        self.assertEqual(rows[1], "1 0.200000 0.400000 0.200000 0.400000")
        self.assertEqual(counts, {"electric_bicycle": 1, "person": 1})

    def test_groups_only_adjacent_numeric_frames(self):
        records = [
            {"frame_id": 10},
            {"frame_id": 20},
            {"frame_id": 40},
            {"frame_id": 50},
            {"frame_id": 100},
        ]

        groups = group_frame_records(records, max_gap=10)

        self.assertEqual([[r["frame_id"] for r in group] for group in groups], [[10, 20], [40, 50], [100]])

    def test_assigns_whole_groups_and_keeps_rare_examples_in_each_split(self):
        groups = []
        for group_id, (size, rare_count) in enumerate([(8, 8), (3, 3), (2, 2), (7, 0), (5, 0), (4, 0)]):
            groups.append(
                [
                    {
                        "frame_id": group_id * 100 + offset,
                        "class_counts": {"electric_bicycle": rare_count if offset == 0 else 0},
                    }
                    for offset in range(size)
                ]
            )

        assignments = assign_group_splits(groups, train_ratio=0.6, val_ratio=0.2, seed=7)

        self.assertEqual(set(assignments), set(range(len(groups))))
        self.assertEqual(set(assignments.values()), {"train", "val", "test"})
        self.assertEqual(assignments[0], "train")
        for split in ("train", "val", "test"):
            rare = sum(
                record["class_counts"].get("electric_bicycle", 0)
                for group_id, group in enumerate(groups)
                if assignments[group_id] == split
                for record in group
            )
            self.assertGreater(rare, 0, split)

    def test_prepares_yolo_layout_manifest_and_summary(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "Mixed"
            (source / "images").mkdir(parents=True)
            (source / "labels").mkdir()
            for frame_id, label in [(10, "scooter"), (20, "person"), (100, "bicycle")]:
                (source / "images" / f"frame_{frame_id}.jpg").write_bytes(b"jpeg")
                annotation = {
                    "imageWidth": 100,
                    "imageHeight": 100,
                    "shapes": [
                        {
                            "label": label,
                            "shape_type": "rectangle",
                            "points": [[10, 10], [50, 50]],
                        }
                    ],
                }
                (source / "labels" / f"frame_{frame_id}.json").write_text(json.dumps(annotation))

            output = root / "prepared"
            summary = prepare_dataset(source, output, max_gap=10, train_ratio=1 / 3, val_ratio=1 / 3, seed=1)

            self.assertEqual(summary["images_total"], 3)
            self.assertEqual(summary["class_names"], CLASS_NAMES)
            self.assertTrue((output / "data.yaml").is_file())
            self.assertTrue((output / "split_manifest.csv").is_file())
            self.assertTrue((output / "summary.json").is_file())
            self.assertEqual(len(list(output.glob("images/*/*.jpg"))), 3)
            self.assertEqual(len(list(output.glob("labels/*/*.txt"))), 3)


if __name__ == "__main__":
    unittest.main()
