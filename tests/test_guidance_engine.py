import unittest

from scripts.guidance_engine import (
    CAUTION,
    KEEP_STRAIGHT,
    STOP,
    UNKNOWN_SLOW_DOWN,
    GuidanceEngine,
    MOVE_LEFT,
    MOVE_RIGHT,
    WalkableRegion,
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
    def test_empty_frames_do_not_prove_free_space(self):
        result = evaluate_guidance_records([], width=640, height=360)
        self.assertEqual(result["trace"], [])

        engine = GuidanceEngine()
        decision = engine.update(1, [])
        self.assertEqual(decision.state, UNKNOWN_SLOW_DOWN)

    def test_surface_and_motion_evidence_required_for_direction(self):
        engine = GuidanceEngine()
        region = WalkableRegion(confidence=.9, source="segformer_ade20k", surface="road", forward_support=.96)
        self.assertEqual(engine.update(1, [], region=region).state, UNKNOWN_SLOW_DOWN)
        self.assertEqual(engine.update(2, [], region=region, motion_reliable=True).state, UNKNOWN_SLOW_DOWN)
        self.assertEqual(engine.update(3, [], region=region, motion_reliable=True).state, UNKNOWN_SLOW_DOWN)
        self.assertEqual(engine.update(4, [], region=region, motion_reliable=True).state, KEEP_STRAIGHT)
        self.assertEqual(engine.update(5, [], region=region).state, UNKNOWN_SLOW_DOWN)

    def test_confirmed_side_ground_support_enables_detour(self):
        for expected, left, right in ((MOVE_LEFT, .96, .30), (MOVE_RIGHT, .30, .96)):
            engine = GuidanceEngine()
            region = WalkableRegion(confidence=.9, source="segformer_ade20k", surface="road",
                                    left_support=left, right_support=right)
            for frame in (1, 2, 3):
                decision = engine.update(frame, [record(frame, [288, 108, 448, 342])],
                                         region=region, motion_reliable=True)
            self.assertEqual(decision.state, expected)

    def test_asymmetric_detection_with_no_ground_evidence_remains_caution(self):
        engine = GuidanceEngine()
        engine.update(1, [record(1, [288, 108, 448, 342])])
        self.assertEqual(engine.update(2, [record(2, [288, 108, 448, 342])]).state, CAUTION)

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

    def test_area_jitter_without_contact_motion_is_not_approach(self):
        engine = GuidanceEngine()
        frames = [
            record(1, [250, 140, 390, 340]),
            record(2, [240, 100, 400, 340]),
            record(3, [220, 20, 420, 340]),
        ]
        decisions = [engine.update(item["frame"], [item]).state for item in frames]
        self.assertEqual(decisions[-1], CAUTION)
        self.assertNotEqual(decisions[-1], STOP)

    def test_distant_central_detection_does_not_immediately_warn(self):
        engine = GuidanceEngine()
        far = record(1, [300, 80, 340, 170])
        self.assertEqual(engine.update(1, [far]).state, UNKNOWN_SLOW_DOWN)
        self.assertEqual(engine.update(2, [far]).state, UNKNOWN_SLOW_DOWN)

    def test_warning_feedback_has_cooldown_across_state_flap(self):
        engine = GuidanceEngine(repeat_frames=10)
        first = record(1, [250, 80, 390, 260])
        second = record(2, [210, 40, 430, 340])
        self.assertTrue(engine.should_emit(engine.update(1, [first]), 1))
        self.assertTrue(engine.should_emit(engine.update(2, [second]), 2))
        self.assertFalse(engine.should_emit(engine.update(2, [second]), 3))


if __name__ == "__main__":
    unittest.main()
