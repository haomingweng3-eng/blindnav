import unittest

from scripts.evaluate_risk_engine import run_suite, sweep_looming_thresholds


class RiskEvaluationTests(unittest.TestCase):
    def test_parameterized_suite_has_no_missed_or_false_mid_alerts(self):
        report = run_suite()

        self.assertEqual(report["missed_expected_alerts"], [])
        self.assertEqual(report["false_mid_alerts"], [])

    def test_suite_includes_multiple_motion_and_noise_cases(self):
        report = run_suite()

        self.assertGreaterEqual(report["scenario_count"], 8)
        self.assertGreaterEqual(report["motion_types"], 4)

    def test_threshold_sweep_exposes_false_alert_tradeoff(self):
        sweep = sweep_looming_thresholds([0.02, 0.06])

        self.assertEqual([item["looming_threshold"] for item in sweep], [0.02, 0.06])
        self.assertIn("slow_approach", sweep[0]["false_mid_alerts"])
        self.assertEqual(sweep[1]["false_mid_alerts"], [])

    def test_high_threshold_exposes_missed_alert_tradeoff(self):
        sweep = sweep_looming_thresholds([0.06, 0.10])

        self.assertEqual(sweep[0]["missed_expected_alerts"], [])
        self.assertIn("borderline_approach", sweep[1]["missed_expected_alerts"])


if __name__ == "__main__":
    unittest.main()
