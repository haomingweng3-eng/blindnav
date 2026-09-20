import unittest

from scripts.build_pseudo_labels import assign_video_splits, box_to_yolo


class BuildPseudoLabelsTest(unittest.TestCase):
    def test_box_to_yolo_normalizes_coordinates(self):
        self.assertEqual(box_to_yolo([10, 20, 30, 60], width=100, height=100), "0 0.2 0.4 0.2 0.4")

    def test_video_split_has_no_video_overlap(self):
        splits = assign_video_splits(["v3", "v1", "v2", "v4", "v5", "v6"])
        self.assertEqual(set(splits), {"v1", "v2", "v3", "v4", "v5", "v6"})
        self.assertEqual(len(set(splits.values())), 3)
        self.assertEqual(len(set(splits.values()) & {"train"}), 1)


if __name__ == "__main__":
    unittest.main()
