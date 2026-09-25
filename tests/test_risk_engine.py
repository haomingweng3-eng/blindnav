import unittest

from scripts.risk_engine import LVL_MID, LVL_NONE, TrackState


def centered_box(side, cx=320.0, cy=300.0):
    half = side / 2.0
    return [cx - half, cy - half, cx + half, cy + half]


class RiskEngineTests(unittest.TestCase):
    def test_gradual_approach_with_small_box_jitter_triggers_warning(self):
        state = TrackState("bike-1", "bicycle")
        sides = [70, 74, 80, 87, 95, 104]
        jitter = [0, 1, -1, 1, 0, -1]

        for side, dx in zip(sides, jitter):
            state.update(centered_box(side, cx=320 + dx))

        level, info = state.assess(frame_idx=6)

        self.assertEqual(level, LVL_MID)
        self.assertGreater(info["looming"], 0.06)

    def test_one_frame_area_spike_is_rejected_as_box_jitter(self):
        state = TrackState("bike-1", "bicycle")
        for side in [80, 80, 80, 240]:
            state.update(centered_box(side))

        level, info = state.assess(frame_idx=4)

        self.assertLess(level, LVL_MID)
        self.assertLessEqual(info["looming"], 0.06)

    def test_remote_target_is_ignored(self):
        state = TrackState("person-1", "person")
        for side in [120, 110, 100, 90, 82, 75]:
            state.update(centered_box(side))

        level, info = state.assess(frame_idx=6)

        self.assertEqual(level, LVL_NONE)
        self.assertLess(info["looming"], 0)

    def test_alert_cooldown_suppresses_repeated_mid_alerts(self):
        state = TrackState("bike-1", "bicycle")
        for side in [70, 76, 83, 91, 100, 110, 121]:
            state.update(centered_box(side))

        first_level, _ = state.assess(frame_idx=7)
        second_level, _ = state.assess(frame_idx=8)

        self.assertEqual(first_level, LVL_MID)
        self.assertEqual(second_level, LVL_NONE)

    def test_looming_is_normalized_by_real_frame_gap(self):
        state = TrackState("bike-1", "bicycle")
        for frame, side in zip([1, 5, 9, 13, 17, 21], [70, 76, 82, 88, 94, 100]):
            state.update(centered_box(side), frame_idx=frame)

        level, info = state.assess(frame_idx=21)

        self.assertEqual(level, LVL_NONE)
        self.assertLess(info["looming"], 0.06)

    def test_looming_threshold_can_be_configured_for_calibration(self):
        default_state = TrackState("bike-default", "bicycle")
        sensitive_state = TrackState(
            "bike-sensitive", "bicycle", looming_threshold=0.02
        )
        boxes = [centered_box(side) for side in [60, 61, 62, 63, 64, 65, 66]]
        for frame_idx, box in enumerate(boxes, start=1):
            default_state.update(box, frame_idx=frame_idx)
            sensitive_state.update(box, frame_idx=frame_idx)

        default_level, _ = default_state.assess(frame_idx=7)
        sensitive_level, _ = sensitive_state.assess(frame_idx=7)

        self.assertEqual(default_level, LVL_NONE)
        self.assertEqual(sensitive_level, LVL_MID)

    def test_small_approach_is_deferred_until_target_is_large_enough(self):
        state = TrackState(
            "bike-small",
            "bicycle",
            looming_threshold=0.02,
            min_approach_area=0.01,
        )
        for side in [50, 51, 52, 53, 54, 55, 56]:
            state.update(centered_box(side))

        level, info = state.assess(frame_idx=7)

        self.assertEqual(level, LVL_NONE)
        self.assertLess(info["area_n"], info["min_approach_area"])

    def test_lateral_drift_is_rate_not_cumulative_displacement(self):
        state = TrackState("person-1", "person")
        centers = [320 - 4 * index for index in range(10)]
        for frame_idx, cx in enumerate(centers, start=1):
            state.update(centered_box(100, cx=cx), frame_idx=frame_idx)

        level, info = state.assess(frame_idx=10)

        self.assertEqual(level, LVL_NONE)
        self.assertLess(abs(info["lateral"]), 0.02)

    def test_fast_lateral_motion_away_from_walking_corridor_is_ignored(self):
        state = TrackState("person-1", "person")
        centers = [520, 550, 580, 610]
        for frame_idx, cx in enumerate(centers, start=1):
            state.update(centered_box(100, cx=cx), frame_idx=frame_idx)

        level, info = state.assess(frame_idx=4)

        self.assertEqual(level, LVL_NONE)
        self.assertFalse(info["path_conflict"])

    def test_fast_approach_outside_walking_corridor_is_ignored(self):
        state = TrackState("car-1", "car")
        for side in [70, 76, 83, 91, 100, 110]:
            state.update(centered_box(side, cx=560))

        level, info = state.assess(frame_idx=6)

        self.assertEqual(level, LVL_NONE)
        self.assertFalse(info["path_conflict"])

    def test_route_center_can_be_shifted_for_camera_mounting_angle(self):
        state = TrackState(
            "car-shifted-route",
            "car",
            corridor_center=0.15,
            corridor_half_width=0.10,
        )
        for side in [70, 76, 83, 91, 100, 110]:
            state.update(centered_box(side, cx=320))

        level, info = state.assess(frame_idx=6)

        self.assertEqual(level, LVL_NONE)
        self.assertFalse(info["path_conflict"])
        self.assertEqual(info["corridor_center"], 0.15)

    def test_reports_when_target_enters_the_walking_corridor(self):
        state = TrackState(
            "person-entering-route",
            "person",
            corridor_half_width=0.12,
        )
        centers = [520, 500, 470, 440, 410, 380, 350]
        for frame_idx, cx in enumerate(centers, start=1):
            state.update(centered_box(100, cx=cx), frame_idx=frame_idx)

        _, info = state.assess(frame_idx=len(centers))

        self.assertTrue(info["route_entry"])
        self.assertTrue(info["path_conflict"])

    def test_target_direction_is_classified_left_front_right(self):
        expected = [(180, "left"), (320, "front"), (500, "right")]
        for cx, direction in expected:
            state = TrackState(f"person-{direction}", "person")
            for frame_idx in range(1, 5):
                state.update(centered_box(100, cx=cx), frame_idx=frame_idx)

            _, info = state.assess(frame_idx=4)

            self.assertEqual(info["direction"], direction)

    def test_same_motion_has_same_looming_at_different_source_fps(self):
        thirty_fps = TrackState(
            "bike-30", "bicycle", fps=30.0, reference_fps=30.0
        )
        fifteen_fps = TrackState(
            "bike-15", "bicycle", fps=15.0, reference_fps=30.0
        )
        side_ratio_30 = 76 / 70
        sides_30 = [70 * side_ratio_30**index for index in range(6)]
        sides_15 = [70 * side_ratio_30 ** (2 * index) for index in range(6)]
        for frame_idx, (side_30, side_15) in enumerate(
            zip(sides_30, sides_15), start=1
        ):
            thirty_fps.update(centered_box(side_30), frame_idx=frame_idx)
            fifteen_fps.update(centered_box(side_15), frame_idx=frame_idx)

        _, info_30 = thirty_fps.assess(frame_idx=6)
        _, info_15 = fifteen_fps.assess(frame_idx=6)

        self.assertAlmostEqual(info_30["looming"], info_15["looming"], places=4)


if __name__ == "__main__":
    unittest.main()
