import unittest

from scripts.feedback_policy import feedback_for
from scripts.risk_engine import LVL_HIGH, LVL_LOW, LVL_MID, LVL_NONE


class FeedbackPolicyTests(unittest.TestCase):
    def test_none_level_has_no_feedback_action(self):
        self.assertEqual(feedback_for(LVL_NONE, "person", {}), None)

    def test_low_level_is_a_short_nonverbal_prompt(self):
        feedback = feedback_for(LVL_LOW, "person", {})

        self.assertEqual(feedback["priority"], "low")
        self.assertEqual(feedback["speech"], None)
        self.assertEqual(feedback["tone"], None)
        self.assertGreater(len(feedback["vibration_ms"]), 0)

    def test_mid_level_prefers_warning_tone_before_speech(self):
        feedback = feedback_for(
            LVL_MID,
            "bicycle",
            {"reason": "横向穿过", "direction": "left"},
        )

        self.assertEqual(feedback["priority"], "warning")
        self.assertEqual(feedback["tone"], "warning")
        self.assertEqual(feedback["speech"], "注意，左侧自行车")

    def test_scooter_has_explicit_feedback_name(self):
        feedback = feedback_for(LVL_MID, "scooter", {"direction": "front"})

        self.assertEqual(feedback["speech"], "注意，前方电动滑板车")

    def test_high_level_is_urgent_and_names_fast_approach(self):
        feedback = feedback_for(
            LVL_HIGH,
            "motorcycle",
            {"reason": "快速接近且近距离", "direction": "right"},
        )

        self.assertEqual(feedback["priority"], "urgent")
        self.assertEqual(feedback["tone"], "danger")
        self.assertEqual(feedback["speech"], "危险，右侧摩托车快速接近")


if __name__ == "__main__":
    unittest.main()
