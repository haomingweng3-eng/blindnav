import unittest

from scripts.android_smoke_test import classify_install_failure, parse_devices


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

    def test_classifies_user_restricted_install_with_actionable_guidance(self):
        result = classify_install_failure(
            "Failure [INSTALL_FAILED_USER_RESTRICTED: Install canceled by user]"
        )
        self.assertEqual(result["reason"], "usb_install_not_allowed")
        self.assertIn("USB 安装", result["action"])

    def test_keeps_unknown_install_failure(self):
        result = classify_install_failure("Failure [INSTALL_PARSE_FAILED_BAD_MANIFEST]")
        self.assertEqual(result["reason"], "install_failed")
