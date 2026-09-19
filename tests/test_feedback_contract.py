import unittest

from scripts.feedback_contract import validate_report


class FeedbackContractTests(unittest.TestCase):
    def test_accepts_replay_report(self):
        report = {
            "alerts": [
                {
                    "frame": 7,
                    "track_id": "bike_0",
                    "cls": "bicycle",
                    "level": 2,
                    "level_name": "警告",
                    "info": {"direction": "front", "reason": "快速接近"},
                    "feedback": {
                        "priority": "warning",
                        "vibration_ms": [120, 70, 120],
                        "tone": "warning",
                        "speech": "注意，前方自行车",
                        "speech_delay_ms": 250,
                    },
                }
            ]
        }
        self.assertEqual(validate_report(report), [])

    def test_accepts_no_feedback_alert(self):
        report = {"alerts": [{"frame": 1, "track_id": "x", "cls": "person", "level": 0, "feedback": None}]}
        self.assertEqual(validate_report(report), [])

    def test_rejects_unknown_priority_and_bad_timing(self):
        report = {
            "alerts": [
                {
                    "frame": 1,
                    "track_id": "x",
                    "cls": "person",
                    "level": 2,
                    "feedback": {
                        "priority": "critical",
                        "vibration_ms": [120, 0],
                        "tone": "danger",
                        "speech": "危险",
                        "speech_delay_ms": -1,
                    },
                }
            ]
        }
        errors = validate_report(report)
        self.assertTrue(any("priority" in error for error in errors))
        self.assertTrue(any("vibration_ms" in error for error in errors))
        self.assertTrue(any("speech_delay_ms" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
