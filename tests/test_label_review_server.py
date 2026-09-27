import csv
import json
import tempfile
import unittest
from pathlib import Path

from scripts.label_review_server import HTML, build_items, clamp_box, validate_annotation


class LabelReviewServerTest(unittest.TestCase):
    def test_clamp_box_orders_and_normalizes_coordinates(self):
        self.assertEqual(clamp_box([90, 80, -5, 10], 100, 100), [0.0, 10.0, 90.0, 80.0])

    def test_annotation_requires_known_class_and_event(self):
        good = {
            "image": "frame.jpg",
            "event_type": "near_miss",
            "boxes": [{"class": "electric_bicycle", "box": [1, 2, 10, 20]}],
        }
        self.assertEqual(validate_annotation(good), [])
        bad = {"image": "frame.jpg", "event_type": "unknown", "boxes": []}
        self.assertTrue(validate_annotation(bad))

    def test_annotation_accepts_car_class(self):
        payload = {
            "image": "frame.jpg",
            "event_type": "safe_pass",
            "boxes": [{"class": "car", "box": [1, 2, 10, 20]}],
        }
        self.assertEqual(validate_annotation(payload), [])

    def test_annotation_rejects_malformed_boxes(self):
        errors = validate_annotation(
            {
                "image": "frame.jpg",
                "event_type": "safe_pass",
                "boxes": [{"class": "person", "box": [1, 2]}],
            }
        )
        self.assertTrue(any("box" in error for error in errors))

    def test_build_items_matches_candidate_paths_by_resolved_path(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image = root / "frame.jpg"
            manifest = root / "manifest.csv"
            candidates = root / "candidates.json"
            with manifest.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["image", "video_id", "frame", "timestamp_s"])
                writer.writeheader()
                writer.writerow({"image": str(image), "video_id": "V1", "frame": "1", "timestamp_s": "0"})
            candidates.write_text(json.dumps({"detections": [{"image": str(image.resolve()), "box": [1, 2, 3, 4]}]}))

            items = build_items(manifest, candidates_path=candidates, only_candidates=True)

            self.assertEqual(len(items), 1)
            self.assertEqual(len(items[0]["candidates"]), 1)

    def test_review_page_autosaves_annotation_changes(self):
        self.assertIn("addEventListener('change'", HTML)
        self.assertIn("scheduleSave", HTML)


if __name__ == "__main__":
    unittest.main()
