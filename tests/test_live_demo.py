import unittest

from scripts.live_demo import parse_args


class LiveDemoArgumentTests(unittest.TestCase):
    def test_headless_mode_and_frame_limit_are_available(self):
        args = parse_args(
            [
                "--headless",
                "--max-frames",
                "45",
                "--device",
                "cpu",
                "--report",
                "live.json",
            ]
        )

        self.assertTrue(args.headless)
        self.assertEqual(args.max_frames, 45)
        self.assertEqual(args.device, "cpu")
        self.assertEqual(args.report, "live.json")

    def test_default_dimensions_match_capture_contract(self):
        args = parse_args([])

        self.assertEqual((args.width, args.height), (1280, 720))
        self.assertFalse(args.headless)
        self.assertIsNone(args.max_frames)


if __name__ == "__main__":
    unittest.main()
