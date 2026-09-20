import csv
import tempfile
import unittest
from pathlib import Path

from scripts.select_review_frames import select_rows


class SelectReviewFramesTest(unittest.TestCase):
    def test_selects_evenly_per_video_and_preserves_first_last(self):
        rows = [
            {"video_id": "a", "frame": str(frame), "image": f"a/{frame}.jpg"}
            for frame in range(1, 11)
        ] + [
            {"video_id": "b", "frame": str(frame), "image": f"b/{frame}.jpg"}
            for frame in range(1, 5)
        ]

        selected = select_rows(rows, max_per_video=4)

        self.assertEqual([row["frame"] for row in selected if row["video_id"] == "a"], ["1", "4", "7", "10"])
        self.assertEqual([row["frame"] for row in selected if row["video_id"] == "b"], ["1", "2", "3", "4"])
        self.assertTrue(all(row["annotation_status"] == "review" for row in selected))

    def test_rejects_non_positive_quota(self):
        with self.assertRaises(ValueError):
            select_rows([], max_per_video=0)


if __name__ == "__main__":
    unittest.main()
