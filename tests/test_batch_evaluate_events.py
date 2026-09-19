import unittest

from scripts.batch_evaluate_events import aggregate_results


class BatchEvaluateEventsTests(unittest.TestCase):
    def test_aggregates_weighted_recall_and_false_rate(self):
        results = [
            {
                "video_id": "V01",
                "duration_s": 60,
                "event_count": 2,
                "detected_event_count": 1,
                "lead_times_s": [1.5],
                "false_alert_count": 2,
            },
            {
                "video_id": "V02",
                "duration_s": 30,
                "event_count": 1,
                "detected_event_count": 1,
                "lead_times_s": [2.5],
                "false_alert_count": 1,
            },
        ]

        summary = aggregate_results(results)

        self.assertEqual(summary["video_count"], 2)
        self.assertEqual(summary["event_count"], 3)
        self.assertEqual(summary["detected_event_count"], 2)
        self.assertAlmostEqual(summary["event_recall"], 2 / 3, places=3)
        self.assertEqual(summary["median_lead_time_s"], 2.0)
        self.assertEqual(summary["false_alert_count"], 3)
        self.assertAlmostEqual(summary["false_alerts_per_minute"], 2.0)

    def test_empty_batch_is_explicitly_undefined(self):
        summary = aggregate_results([])
        self.assertEqual(summary["video_count"], 0)
        self.assertIsNone(summary["event_recall"])
        self.assertIsNone(summary["false_alerts_per_minute"])


if __name__ == "__main__":
    unittest.main()
