import unittest

from scripts.guidance_engine import (
    CAUTION,
    KEEP_STRAIGHT,
    STOP,
    UNKNOWN_SLOW_DOWN,
    GuidanceEngine,
    evaluate_guidance_records,
)


def record(frame, box, track_id="two-wheeler-1", conf=0.9):
    return {
        "frame": frame,
        "track_id": track_id,
        "cls": "two_wheeler_candidate",
        "conf": conf,
        "box": list(box),
        "width": 640,
        "height": 360,
    }


class GuidanceEngineTests(unittest.TestCase):
    def test_empty_frames_keep_straight(self):
        result = evaluate_guidance_records([], width=640, height=360)
        self.assertEqual(result["trace"], [])

        engine = GuidanceEngine()
        decision = engine.update(1, [])
        self.assertEqual(decision.state, KEEP_STRAIGHT)

    def test_central_approaching_blocker_stops_after_confirmed_close_motion(self):
        engine = GuidanceEngine()
        first = record(1, [250, 80, 390, 260])
        second = record(2, [210, 40, 430, 340])
        third = record(3, [180, 20, 460, 350])
        self.assertEqual(engine.update(1, [first]).state, UNKNOWN_SLOW_DOWN)
        self.assertEqual(engine.update(2, [second]).state, CAUTION)
        self.assertEqual(engine.update(3, [third]).state, STOP)

    def test_guidance_trace_suppresses_repeated_speech(self):
        records = [
            record(1, [250, 80, 390, 260]),
            record(2, [210, 40, 430, 340]),
            record(3, [180, 20, 460, 350]),
        ]
        report = evaluate_guidance_records(records, width=640, height=360)
        speech = [item["speech"] for item in report["trace"]]
        self.assertEqual(speech[0], "前方情况不明，请减速")
        self.assertEqual(speech[1], "注意，前方可能有障碍")
        self.assertEqual(speech[2], "停止，前方有危险")

    def test_large_stationary_blocker_does_not_escalate_to_stop(self):
        engine = GuidanceEngine()
        parked = record(1, [180, 40, 460, 350])
        same = record(2, [180, 40, 460, 350])
        self.assertEqual(engine.update(1, [parked]).state, UNKNOWN_SLOW_DOWN)
        self.assertEqual(engine.update(2, [same]).state, CAUTION)

    def test_warning_feedback_has_cooldown_across_state_flap(self):
        engine = GuidanceEngine(repeat_frames=10)
        first = record(1, [250, 80, 390, 260])
        second = record(2, [210, 40, 430, 340])
        self.assertTrue(engine.should_emit(engine.update(1, [first]), 1))
        self.assertTrue(engine.should_emit(engine.update(2, [second]), 2))
        self.assertFalse(engine.should_emit(engine.update(2, [second]), 3))


if __name__ == "__main__":
    unittest.main()
