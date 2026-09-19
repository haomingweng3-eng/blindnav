import json
import tempfile
import unittest
from pathlib import Path

from scripts.replay_detections import load_detection_input, replay_detection_file


class ReplayDetectionsTests(unittest.TestCase):
    def test_load_detection_input_reads_video_metadata_and_records(self):
        payload = {
            "width": 1280,
            "height": 720,
            "records": [
                {
                    "frame": 1,
                    "track_id": "bike_0",
                    "cls": "bicycle",
                    "conf": 0.9,
                    "box": [100, 100, 200, 200],
                }
            ],
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detections.json"
            path.write_text(json.dumps(payload), encoding="utf-8")

            loaded = load_detection_input(path)

        self.assertEqual(loaded["width"], 1280)
        self.assertEqual(loaded["height"], 720)
        self.assertEqual(len(loaded["records"]), 1)

    def test_load_detection_input_rejects_missing_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detections.json"
            path.write_text(json.dumps({"records": []}), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_detection_input(path)

    def test_replay_detection_file_accepts_calibration_threshold(self):
        sides = [60, 61, 62, 63, 64, 65, 66]
        records = []
        for frame, side in enumerate(sides, start=1):
            half = side / 2
            records.append(
                {
                    "frame": frame,
                    "track_id": "bike_0",
                    "cls": "bicycle",
                    "conf": 0.9,
                    "box": [320 - half, 300 - half, 320 + half, 300 + half],
                }
            )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "detections.json"
            path.write_text(
                json.dumps({"width": 640, "height": 640, "records": records}),
                encoding="utf-8",
            )
            default_report = replay_detection_file(path)
            sensitive_report = replay_detection_file(path, looming_threshold=0.02)

        self.assertEqual(default_report["alert_count"], 0)
        self.assertEqual(sensitive_report["alert_count"], 1)


if __name__ == "__main__":
    unittest.main()
