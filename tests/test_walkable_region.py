import unittest

import numpy as np

from scripts.walkable_region import SegformerWalkableRegionEstimator


class WalkableRegionTests(unittest.TestCase):
    def test_bottom_connected_road_component_becomes_region(self):
        labels = np.zeros((100, 160), dtype=np.int64)
        labels[45:, 25:135] = 6
        probabilities = np.ones_like(labels, dtype=np.float32)
        region = SegformerWalkableRegionEstimator.mask_to_region(
            labels, probabilities, {6}
        )
        self.assertEqual(region.source, "segformer_ade20k")
        self.assertEqual(region.surface, "road")
        self.assertLess(region.left, 0.25)
        self.assertGreater(region.right, 0.75)
        self.assertTrue(region.contains(0.5, 0.8))
        self.assertFalse(region.contains(0.8, 0.8))
        self.assertTrue(region.contains(0.5, 0.5))

    def test_bottom_occlusion_does_not_turn_central_contact_safe(self):
        labels = np.zeros((100, 160), dtype=np.int64)
        labels[30:, 5:70] = 6
        region = SegformerWalkableRegionEstimator.mask_to_region(
            labels, np.ones_like(labels, dtype=np.float32), {6}
        )
        self.assertTrue(region.contains(0.5, 0.95))

    def test_road_in_background_without_bottom_connection_is_unknown(self):
        labels = np.zeros((100, 160), dtype=np.int64)
        labels[20:60, 25:135] = 6
        region = SegformerWalkableRegionEstimator.mask_to_region(
            labels, np.ones_like(labels, dtype=np.float32), {6}
        )
        self.assertEqual(region.source, "geometry_fallback")

    def test_contact_must_be_within_local_road_bounds(self):
        labels = np.zeros((100, 160), dtype=np.int64)
        for y in range(35, 100):
            half = 12 + (y - 35)
            labels[y, max(0, 80-half):min(160, 80+half)] = 6
        region = SegformerWalkableRegionEstimator.mask_to_region(
            labels, np.ones_like(labels, dtype=np.float32), {6}
        )
        self.assertTrue(region.contains(0.5, 0.40))
        self.assertFalse(region.contains(0.33, 0.40))

    def test_missing_mask_uses_conservative_fallback(self):
        labels = np.zeros((20, 20), dtype=np.int64)
        probabilities = np.ones_like(labels, dtype=np.float32)
        region = SegformerWalkableRegionEstimator.mask_to_region(
            labels, probabilities, set()
        )
        self.assertEqual(region.source, "geometry_fallback")
        self.assertLess(region.confidence, 0.35)

    def test_unknown_hole_is_not_filled_by_region_outline(self):
        labels = np.full((100, 160), 6, dtype=np.int64)
        labels[70:75, 25:60] = 0
        region = SegformerWalkableRegionEstimator.mask_to_region(labels, np.ones_like(labels, dtype=np.float32), {6})
        self.assertLess(region.left_support, .90)
        self.assertGreater(region.right_support, .90)

    def test_detected_box_excluded_from_direction_evidence(self):
        labels = np.full((100, 160), 6, dtype=np.int64)
        region = SegformerWalkableRegionEstimator.mask_to_region(labels, np.ones_like(labels, dtype=np.float32), {6},
            detections=[{"box": [20, 60, 65, 85]}])
        self.assertLess(region.left_support, .90)

    def test_low_probability_ground_does_not_authorize_direction(self):
        labels = np.full((100, 160), 6, dtype=np.int64)
        region = SegformerWalkableRegionEstimator.mask_to_region(labels, np.full(labels.shape, .4, dtype=np.float32), {6})
        self.assertEqual(region.forward_support, 0)
        self.assertEqual(region.left_support, 0)
        self.assertEqual(region.right_support, 0)


if __name__ == "__main__":
    unittest.main()
