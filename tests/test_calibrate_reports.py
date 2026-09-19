import json
import unittest
from pathlib import Path

from scripts.calibrate_reports import calibrate_report_payload


class CalibrateReportsTests(unittest.TestCase):
    def test_sweeps_real_report_records_without_rerunning_detector(self):
        fixture = Path(__file__).parent / "fixtures" / "synthetic_approach_detections.json"
        payload = json.loads(fixture.read_text(encoding="utf-8"))
        report = calibrate_report_payload(payload, thresholds=[0.02, 0.06, 0.10])

        self.assertEqual(report["thresholds"], [0.02, 0.06, 0.10])
        self.assertEqual(len(report["results"]), 3)
        self.assertEqual(report["results"][1]["threshold"], 0.06)
        self.assertGreaterEqual(report["results"][1]["alert_count"], 1)
        self.assertTrue(report["results"][1]["first_alert_frame"] is not None)

    def test_rejects_report_without_raw_records(self):
        with self.assertRaises(ValueError):
            calibrate_report_payload({"width": 640, "height": 640}, thresholds=[0.06])


if __name__ == "__main__":
    unittest.main()
