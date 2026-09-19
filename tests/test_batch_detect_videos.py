import tempfile
import unittest
from pathlib import Path

from scripts.batch_detect_videos import discover_videos, report_name


class BatchDetectVideoTests(unittest.TestCase):
    def test_discovers_supported_video_extensions_sorted(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "V02.MP4").write_bytes(b"x")
            (root / "V01.mp4").write_bytes(b"x")
            (root / "notes.txt").write_text("ignore", encoding="utf-8")

            self.assertEqual(
                [p.name for p in discover_videos(root)], ["V01.mp4", "V02.MP4"]
            )

    def test_report_name_is_stable_and_json(self):
        self.assertEqual(report_name(Path("20260916_V04_crossing.MOV")), "20260916_V04_crossing.json")


if __name__ == "__main__":
    unittest.main()
