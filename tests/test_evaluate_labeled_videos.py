import json
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_labeled_videos import evaluate_labeled_videos


class EvaluateLabeledVideosTests(unittest.TestCase):
    def test_reports_video_level_recall_and_safe_false_positive_rate(self):
        fixture = Path(__file__).parent / "fixtures" / "synthetic_approach_detections.json"
        approach = json.loads(fixture.read_text(encoding="utf-8"))
        approach["fps"] = 30.0
        approach["reference_fps"] = 30.0
        safe = {
            "width": 640,
            "height": 640,
            "fps": 30.0,
            "reference_fps": 30.0,
            "records": [],
        }
        labels = [
            {"video_file": "near.mp4", "status": "near_miss", "approx_time_s": "1.0"},
            {"video_file": "safe.mp4", "status": "safe", "approx_time_s": ""},
        ]

        result = evaluate_labeled_videos(
            labels,
            {"near.mp4": approach, "safe.mp4": safe},
            thresholds=[0.06],
        )

        metrics = result["results"][0]
        self.assertEqual(metrics["video_count"], 2)
        self.assertEqual(metrics["positive_video_count"], 1)
        self.assertEqual(metrics["detected_positive_count"], 1)
        self.assertEqual(metrics["safe_video_count"], 1)
        self.assertEqual(metrics["false_positive_video_count"], 0)
        self.assertEqual(metrics["recall"], 1.0)
        self.assertEqual(metrics["false_positive_rate"], 0.0)

    def test_missing_report_is_reported_not_silently_ignored(self):
        labels = [{"video_file": "missing.mp4", "status": "safe"}]
        with self.assertRaises(ValueError):
            evaluate_labeled_videos(labels, {}, thresholds=[0.06])


if __name__ == "__main__":
    unittest.main()
