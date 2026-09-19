import unittest

from scripts.submission_audit import summarize_audit


class SubmissionAuditTests(unittest.TestCase):
    def test_passes_only_when_all_required_gates_pass(self):
        result = summarize_audit(
            tests_ok=True,
            compile_ok=True,
            acceptance_ok=True,
            collection_ready=True,
            git_clean=True,
            collection_errors=[],
            environment_ok=True,
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["blocking_items"], [])

    def test_lists_external_blockers_without_hiding_them(self):
        result = summarize_audit(
            tests_ok=True,
            compile_ok=True,
            acceptance_ok=True,
            collection_ready=False,
            git_clean=False,
            collection_errors=["missing_video:V01"],
            environment_ok=True,
        )
        self.assertFalse(result["passed"])
        self.assertIn("collection_not_ready", result["blocking_items"])
        self.assertIn("git_dirty", result["blocking_items"])
        self.assertEqual(result["collection_errors"], ["missing_video:V01"])

    def test_reports_android_contract_as_a_submission_gate(self):
        result = summarize_audit(
            tests_ok=True,
            compile_ok=True,
            acceptance_ok=True,
            collection_ready=True,
            git_clean=True,
            collection_errors=[],
            environment_ok=True,
            android_contract_ok=False,
        )

        self.assertFalse(result["passed"])
        self.assertIn("android_contract_failed", result["blocking_items"])


if __name__ == "__main__":
    unittest.main()
