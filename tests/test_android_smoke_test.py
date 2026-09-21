import unittest

from scripts.android_smoke_test import parse_devices


class AndroidSmokeTestTests(unittest.TestCase):
    def test_parses_ready_and_offline_devices(self):
        output = """List of devices attached
emulator-5554\tdevice product:sdk model:sdk
ZY224JQ\toffline
"""
        self.assertEqual(
            parse_devices(output),
            [("emulator-5554", "device"), ("ZY224JQ", "offline")],
        )

    def test_empty_adb_output_has_no_devices(self):
        self.assertEqual(parse_devices("List of devices attached\n\n"), [])
