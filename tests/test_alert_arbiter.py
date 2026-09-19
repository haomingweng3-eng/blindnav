import unittest

from scripts.alert_arbiter import AlertArbiter


def alert(frame, track_id="car_1", cls="car", level=2, direction="front"):
    return {
        "frame": frame,
        "track_id": track_id,
        "cls": cls,
        "level": level,
        "info": {"direction": direction},
    }


class AlertArbiterTests(unittest.TestCase):
    def test_suppresses_same_track_alerts_inside_cooldown(self):
        arbiter = AlertArbiter(cooldown_frames=30)

        accepted = arbiter.filter(
            [alert(10), alert(20), alert(39), alert(40)]
        )

        self.assertEqual([item["frame"] for item in accepted], [10, 40])

    def test_high_alert_can_interrupt_a_mid_alert(self):
        arbiter = AlertArbiter(cooldown_frames=30)

        accepted = arbiter.filter(
            [alert(10, level=2), alert(15, level=3), alert(20, level=3)]
        )

        self.assertEqual(
            [(item["frame"], item["level"]) for item in accepted],
            [(10, 2), (15, 3)],
        )

    def test_different_targets_are_not_merged(self):
        arbiter = AlertArbiter(cooldown_frames=30)

        accepted = arbiter.filter(
            [alert(10, track_id="car_1"), alert(10, track_id="car_2")]
        )

        self.assertEqual(len(accepted), 2)

    def test_same_channel_mid_alerts_are_merged_across_tracks(self):
        arbiter = AlertArbiter(cooldown_frames=30, channel_cooldown_frames=15)

        accepted = arbiter.filter(
            [
                alert(10, track_id="car_1"),
                alert(15, track_id="car_2"),
                alert(30, track_id="car_3"),
            ]
        )

        self.assertEqual(
            [(item["frame"], item["track_id"]) for item in accepted],
            [(10, "car_1"), (30, "car_3")],
        )


if __name__ == "__main__":
    unittest.main()
