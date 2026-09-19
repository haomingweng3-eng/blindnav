import unittest

from scripts.prepare_annotations import build_annotation


class PrepareAnnotationsTests(unittest.TestCase):
    def test_builds_explicit_incomplete_template_from_report_metadata(self):
        annotation = build_annotation(
            {
                "video": "data/raw/V01.mp4",
                "fps": 25.0,
                "total_frames": 750,
            }
        )

        self.assertEqual(annotation["video_id"], "V01")
        self.assertEqual(annotation["fps"], 25.0)
        self.assertEqual(annotation["duration_s"], 30.0)
        self.assertEqual(annotation["events"], [])
        self.assertFalse(annotation["annotation_complete"])

    def test_rejects_report_without_frame_metadata(self):
        with self.assertRaises(ValueError):
            build_annotation({"video": "V01.mp4", "fps": 0, "total_frames": 10})


if __name__ == "__main__":
    unittest.main()
