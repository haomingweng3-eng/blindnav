import unittest

from scripts.label_review_server import clamp_box, validate_annotation


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

    def test_annotation_rejects_malformed_boxes(self):
        errors = validate_annotation(
            {
                "image": "frame.jpg",
                "event_type": "safe_pass",
                "boxes": [{"class": "person", "box": [1, 2]}],
            }
        )
        self.assertTrue(any("box" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
