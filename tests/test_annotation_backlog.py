import unittest

from scripts.build_annotation_backlog import build_backlog


class AnnotationBacklogTests(unittest.TestCase):
    def test_prioritizes_positive_event_videos_and_excludes_reviewed_images(self):
        candidates = [
            {"image": "/frames/safe/frame_000001.jpg", "source_class": "motorcycle", "confidence": 0.9},
            {"image": "/frames/conflict/frame_000002.jpg", "source_class": "motorcycle", "confidence": 0.6},
            {"image": "/frames/conflict/frame_000002.jpg", "source_class": "person", "confidence": 0.8},
            {"image": "/frames/conflict/frame_000003.jpg", "source_class": "car", "confidence": 0.99},
        ]
        rows = build_backlog(
            candidates,
            reviewed_images={"/frames/safe/frame_000001.jpg"},
            target_video_ids={"conflict"},
        )

        self.assertEqual([row["video_id"] for row in rows], ["conflict"] * 1)
        self.assertEqual(rows[0]["frame"], 2)
        self.assertEqual(rows[0]["candidate_count"], 1)
        self.assertEqual(rows[0]["source_classes"], "motorcycle")

    def test_ignores_non_vehicle_candidates(self):
        rows = build_backlog(
            [{"image": "/frames/v/frame_000001.jpg", "source_class": "person", "confidence": 0.9}],
            reviewed_images=set(),
            target_video_ids=set(),
        )
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
