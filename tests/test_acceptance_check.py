import json
import tempfile
import unittest
from pathlib import Path

from scripts.acceptance_check import build_acceptance_report


class AcceptanceCheckTests(unittest.TestCase):
    def test_acceptance_report_covers_simulation_and_feedback_replay(self):
        fixture = Path(__file__).parent / "fixtures" / "synthetic_approach_detections.json"
        report = build_acceptance_report(fixture)

        self.assertTrue(report["simulation"]["passed"])
        self.assertTrue(report["replay"]["passed"])
        self.assertTrue(report["replay"]["contract_passed"])
        self.assertEqual(report["replay"]["alert_count"], 1)
        self.assertEqual(report["replay"]["speech"], "注意，前方自行车")

    def test_report_is_json_serializable(self):
        fixture = Path(__file__).parent / "fixtures" / "synthetic_approach_detections.json"
        report = build_acceptance_report(fixture)
        encoded = json.dumps(report, ensure_ascii=False)
        self.assertIn('"passed": true', encoded)


if __name__ == "__main__":
    unittest.main()
