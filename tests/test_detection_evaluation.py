import unittest

from scripts.evaluate_risk_engine import evaluate_detection_records


def centered_box(side, cx=320.0, cy=300.0):
    half = side / 2.0
    return [cx - half, cy - half, cx + half, cy + half]


class DetectionEvaluationTests(unittest.TestCase):
    def test_detection_records_are_evaluated_per_track(self):
        records = [
            {
                "frame": frame,
                "track_id": "bike_0",
                "cls": "bicycle",
                "conf": 0.9,
                "box": centered_box(side),
            }
            for frame, side in enumerate([60, 66, 73, 82, 93, 106, 121], start=1)
        ]

        report = evaluate_detection_records(records, width=640, height=640)

        self.assertEqual(report["detection_stats"], {"bicycle": 7})
        self.assertEqual(report["track_count"], 1)
        self.assertEqual(report["alert_count"], 1)
        self.assertEqual(report["alerts"][0]["track_id"], "bike_0")
        self.assertEqual(report["alerts"][0]["feedback"]["tone"], "warning")

    def test_different_track_ids_do_not_share_area_history(self):
        records = []
        for frame, side in enumerate([60, 66, 73, 82], start=1):
            records.append(
                {
                    "frame": frame,
                    "track_id": "bike_0",
                    "cls": "bicycle",
                    "conf": 0.9,
                    "box": centered_box(side),
                }
            )
            records.append(
                {
                    "frame": frame,
                    "track_id": "person_1",
                    "cls": "person",
                    "conf": 0.9,
                    "box": centered_box(90),
                }
            )

        report = evaluate_detection_records(records, width=640, height=640)

        self.assertEqual(report["track_count"], 2)
        self.assertTrue(all(alert["track_id"] == "bike_0" for alert in report["alerts"]))

    def test_sparse_detection_frames_use_original_frame_numbers(self):
        records = [
            {
                "frame": frame,
                "track_id": "bike_0",
                "cls": "bicycle",
                "conf": 0.9,
                "box": centered_box(side),
            }
            for frame, side in zip([1, 5, 9, 13, 17, 21], [70, 76, 82, 88, 94, 100])
        ]

        report = evaluate_detection_records(records, width=640, height=640)

        self.assertEqual(report["alert_count"], 0)

    def test_custom_micromobility_classes_are_not_filtered(self):
        records = [
            {
                "frame": frame,
                "track_id": "scooter_0",
                "cls": "scooter",
                "conf": 0.95,
                "box": centered_box(side),
            }
            for frame, side in enumerate([60, 70, 82, 96, 114, 136], start=1)
        ]

        report = evaluate_detection_records(records, width=640, height=640)

        self.assertEqual(report["track_count"], 1)
        self.assertGreaterEqual(report["alert_count"], 1)
        self.assertEqual(
            report["alerts"][0]["feedback"]["speech"], "注意，前方电动滑板车"
        )

    def test_route_geometry_is_passed_to_each_track(self):
        records = [
            {
                "frame": frame,
                "track_id": "car_0",
                "cls": "car",
                "conf": 0.9,
                "box": centered_box(side),
            }
            for frame, side in enumerate([70, 76, 83, 91, 100, 110], start=1)
        ]

        report = evaluate_detection_records(
            records,
            width=640,
            height=640,
            corridor_center=0.15,
            corridor_half_width=0.10,
        )

        self.assertEqual(report["alert_count"], 0)
        self.assertEqual(report["corridor_center"], 0.15)
        self.assertEqual(report["corridor_half_width"], 0.10)

    def test_operational_alerts_are_arbited_after_risk_engine_alerts(self):
        records = [
            {
                "frame": frame,
                "track_id": "bike_0",
                "cls": "bicycle",
                "conf": 0.9,
                "box": centered_box(side),
            }
            for frame, side in enumerate(
                [60 * 1.08**index for index in range(35)], start=1
            )
        ]

        report = evaluate_detection_records(records, width=640, height=640)

        self.assertGreater(report["raw_alert_count"], report["alert_count"])
        self.assertEqual(
            report["suppressed_alert_count"],
            report["raw_alert_count"] - report["alert_count"],
        )
        self.assertEqual(report["alert_count"], 2)


if __name__ == "__main__":
    unittest.main()
