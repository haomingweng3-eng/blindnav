import unittest

from scripts.review_to_yolo import annotation_to_rows


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


if __name__ == "__main__":
    unittest.main()
