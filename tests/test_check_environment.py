import unittest

from scripts.check_environment import check_requirements


class CheckEnvironmentTests(unittest.TestCase):
    def test_accepts_exact_and_minimum_versions(self):
        result = check_requirements(
            ["torch==2.14.0", "lap>=0.5.12"],
            {"torch": "2.14.0", "lap": "0.5.13"},
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["missing"], [])
        self.assertEqual(result["incompatible"], [])

    def test_reports_missing_and_incompatible_packages(self):
        result = check_requirements(
            ["torch==2.14.0", "ultralytics>=8.4.0", "onnx==1.22.0"],
            {"torch": "2.13.0", "ultralytics": "8.4.152"},
        )
        self.assertFalse(result["passed"])
        self.assertIn("onnx", result["missing"])
        self.assertEqual(result["incompatible"][0]["package"], "torch")


if __name__ == "__main__":
    unittest.main()
