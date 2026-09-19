import csv
import tempfile
import unittest
from pathlib import Path

from scripts.validate_collection import inspect_collection


class CollectionValidationTests(unittest.TestCase):
    def _write_manifest(self, root, rows):
        path = root / "manifest.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["video_id", "filename", "scene", "duration_s", "valid_events"],
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_reports_missing_and_present_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "raw"
            raw.mkdir()
            (raw / "v01.mp4").write_bytes(b"not-a-real-video")
            manifest = self._write_manifest(
                root,
                [
                    {"video_id": "V01", "filename": "v01.mp4", "scene": "approach", "duration_s": "20", "valid_events": "2"},
                    {"video_id": "V02", "filename": "v02.mp4", "scene": "crossing", "duration_s": "", "valid_events": ""},
                ],
            )

            report = inspect_collection(manifest, raw)

            self.assertEqual(report["expected_count"], 2)
            self.assertEqual(report["present_count"], 1)
            self.assertEqual(report["missing"], ["V02"])
            self.assertFalse(report["ready"])
            self.assertEqual(report["present"][0]["video_id"], "V01")

    def test_rejects_duplicate_ids_and_filenames(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = self._write_manifest(
                root,
                [
                    {"video_id": "V01", "filename": "same.mp4", "scene": "a", "duration_s": "", "valid_events": ""},
                    {"video_id": "V01", "filename": "same.mp4", "scene": "b", "duration_s": "", "valid_events": ""},
                ],
            )

            report = inspect_collection(manifest, root / "raw")

            self.assertFalse(report["ready"])
            self.assertIn("duplicate_video_id:V01", report["errors"])
            self.assertIn("duplicate_filename:same.mp4", report["errors"])


if __name__ == "__main__":
    unittest.main()
