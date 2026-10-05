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

    def test_missing_mask_uses_conservative_fallback(self):
        labels = np.zeros((20, 20), dtype=np.int64)
        probabilities = np.ones_like(labels, dtype=np.float32)
        region = SegformerWalkableRegionEstimator.mask_to_region(
            labels, probabilities, set()
        )
        self.assertEqual(region.source, "geometry_fallback")
        self.assertLess(region.confidence, 0.35)


if __name__ == "__main__":
    unittest.main()
