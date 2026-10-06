import unittest

from scripts.trajectory_projection import has_observed_motion, project_contact_motion, track_display_level
from scripts.render_two_wheeler_trajectory_demo_20261004 import _risk_for


def history(points):
    return [{'x': x, 'y': y, 'timestamp_ms': i * 100} for i, (x, y) in enumerate(points)]


class TrajectoryProjectionTest(unittest.TestCase):
    def test_stationary_history_is_not_observed_motion(self):
        self.assertFalse(has_observed_motion(history([(320, 230)] * 6), 640, 360))
        self.assertFalse(has_observed_motion(history([(320 + (-1)**i, 230) for i in range(6)]), 640, 360))

    def test_coherent_history_is_observed_motion(self):
        self.assertTrue(has_observed_motion(history([(320, 200 + i * 6) for i in range(6)]), 640, 360))

    def test_stationary_and_jitter_have_no_forecast(self):
        for points in ([(320, 230)] * 6,
                       [(320 + (-1)**i, 230 + (-1)**i) for i in range(6)]):
            self.assertIsNone(project_contact_motion(history(points), 640, 360, True))

    def test_coherent_compensated_motion_can_be_projected(self):
        result = project_contact_motion(history([(320, 200 + i * 6) for i in range(6)]),
                                        640, 360, True)
        self.assertIsNotNone(result)
        self.assertGreater(result['end'][1], result['start'][1])
        self.assertFalse(result['collision_guarantee'])

    def test_unknown_motion_clipping_and_gaps_have_no_forecast(self):
        points = history([(320, 200 + i * 6) for i in range(6)])
        self.assertIsNone(project_contact_motion(points, 640, 360, False))
        self.assertIsNone(project_contact_motion(points, 640, 360, True, bottom_clipped=True))
        points[-1]['timestamp_ms'] += 1000
        self.assertIsNone(project_contact_motion(points, 640, 360, True))

    def test_scene_danger_does_not_turn_unrelated_tracks_red(self):
        self.assertEqual(track_display_level(0, False, 'DANGER'), 0)
        self.assertEqual(track_display_level(0, True, 'DANGER'), 1)
        self.assertEqual(track_display_level(2, True, 'CAUTION'), 2)

    def test_sparse_old_alert_is_not_permanent_danger(self):
        alerts = {(5, 'track_1'): {'level': 3}}
        self.assertIsNotNone(_risk_for(5, 'track_1', alerts))
        self.assertIsNone(_risk_for(6, 'track_1', alerts))
        self.assertIsNone(_risk_for(5, 'track_2', alerts))
