import unittest

from scripts.review_to_yolo import annotation_to_rows, summarize_annotations


class ReviewToYoloTest(unittest.TestCase):
    def test_annotation_to_rows_maps_project_classes(self):
        rows = annotation_to_rows(
            {"boxes": [{"class": "electric_bicycle", "box": [10, 20, 30, 60]}]},
            width=100,
            height=100,
        )
        self.assertEqual(rows, ["0 0.2 0.4 0.2 0.4"])

    def test_safe_background_has_no_rows(self):
        self.assertEqual(annotation_to_rows({"boxes": []}, width=100, height=100), [])

    def test_annotation_to_rows_maps_car_class(self):
        rows = annotation_to_rows(
            {"boxes": [{"class": "car", "box": [10, 20, 30, 60]}]},
            width=100,
            height=100,
        )
        self.assertEqual(rows, ["4 0.2 0.4 0.2 0.4"])

    def test_summarize_annotations_keeps_empty_background_and_class_counts(self):
        summary = summarize_annotations(
            [
                {"image": "a.jpg", "event_type": "safe_pass", "boxes": []},
                {
                    "image": "b.jpg",
                    "event_type": "near_miss",
                    "boxes": [
                        {"class": "electric_bicycle", "box": [0, 0, 10, 10]},
                        {"class": "motorcycle", "box": [0, 0, 10, 10]},
                    ],
                },
            ]
        )
        self.assertEqual(summary["images"], 2)
        self.assertEqual(summary["empty_image_count"], 1)
        self.assertEqual(summary["box_count"], 2)
        self.assertEqual(summary["class_counts"], {"electric_bicycle": 1, "motorcycle": 1})


if __name__ == "__main__":
    unittest.main()
