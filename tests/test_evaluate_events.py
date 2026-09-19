import unittest

from scripts.evaluate_events import evaluate_event_report


class EvaluateEventsTests(unittest.TestCase):
    def test_matches_alerts_and_calculates_lead_time(self):
        annotation = {
            "video_id": "V01",
            "fps": 10,
            "duration_s": 30,
            "events": [
                {
                    "event_id": "E1",
                    "start_frame": 20,
                    "conflict_frame": 50,
                    "target_class": "bicycle",
                }
            ],
        }
        report = {
            "frame_count": 300,
            "alerts": [
                {"frame": 30, "cls": "bicycle", "track_id": "bike_1"},
                {"frame": 180, "cls": "person", "track_id": "person_1"},
            ],
        }

        result = evaluate_event_report(annotation, report)

        self.assertEqual(result["event_count"], 1)
        self.assertEqual(result["detected_event_count"], 1)
        self.assertEqual(result["event_recall"], 1.0)
        self.assertEqual(result["lead_times_s"], [2.0])
        self.assertEqual(result["false_alert_count"], 1)
        self.assertAlmostEqual(result["false_alerts_per_minute"], 2.0)

    def test_alert_outside_event_window_does_not_match(self):
        annotation = {
            "video_id": "V02",
            "fps": 30,
            "duration_s": 10,
            "events": [
                {
                    "event_id": "E1",
                    "start_frame": 100,
                    "conflict_frame": 150,
                    "target_class": "electric_bicycle",
                }
            ],
        }
        report = {"alerts": [{"frame": 20, "cls": "electric_bicycle"}]}

        result = evaluate_event_report(annotation, report)

        self.assertEqual(result["detected_event_count"], 0)
        self.assertEqual(result["event_recall"], 0.0)
        self.assertEqual(result["false_alert_count"], 1)

    def test_no_events_has_undefined_recall_but_measurable_false_rate(self):
        annotation = {"video_id": "V11", "fps": 20, "duration_s": 60, "events": []}
        result = evaluate_event_report(
            annotation,
            {"alerts": [{"frame": 10, "cls": "person"}, {"frame": 20, "cls": "car"}]},
        )

        self.assertIsNone(result["event_recall"])
        self.assertEqual(result["false_alert_count"], 2)
        self.assertAlmostEqual(result["false_alerts_per_minute"], 2.0)


if __name__ == "__main__":
    unittest.main()
