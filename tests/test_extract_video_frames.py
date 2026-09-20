import unittest

from scripts.extract_video_frames import sample_frame_indices


class FrameSamplingTests(unittest.TestCase):
    def test_samples_one_based_frames_at_fixed_stride_and_includes_last(self):
        self.assertEqual(sample_frame_indices(11, 4), [1, 5, 9, 11])

    def test_rejects_invalid_inputs(self):
        with self.assertRaises(ValueError):
            sample_frame_indices(0, 4)
        with self.assertRaises(ValueError):
            sample_frame_indices(10, 0)


if __name__ == "__main__":
    unittest.main()
