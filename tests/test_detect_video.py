import unittest

from scripts.detect_video import parse_args


class DetectVideoArgumentTests(unittest.TestCase):
    def test_custom_model_and_device_are_configurable(self):
        args = parse_args(
            [
                "input.mp4",
                "report.json",
                "0.04",
                "--model",
                "runs/scooter.pt",
                "--device",
                "mps",
                "--conf",
                "0.2",
                "--entry-confirm-frames",
                "4",
            ]
        )

        self.assertEqual(args.video, "input.mp4")
        self.assertEqual(args.report, "report.json")
        self.assertEqual(args.looming_threshold, 0.04)
        self.assertEqual(args.model, "runs/scooter.pt")
        self.assertEqual(args.device, "mps")
        self.assertEqual(args.conf, 0.2)
        self.assertEqual(args.min_approach_area, 0.01)
        self.assertEqual(args.entry_confirm_frames, 4)

    def test_old_positional_form_keeps_defaults(self):
        args = parse_args(["input.mp4", "report.json", "0.06"])

        self.assertEqual(args.model, "models/yolov8n.pt")
        self.assertIsNone(args.device)
        self.assertEqual(args.conf, 0.25)
        self.assertEqual(args.min_approach_area, 0.01)
        self.assertEqual(args.entry_confirm_frames, 3)


if __name__ == "__main__":
    unittest.main()
