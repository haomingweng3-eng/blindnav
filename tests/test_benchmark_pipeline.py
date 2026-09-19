import unittest

from scripts.benchmark_pipeline import summarize_timings


class BenchmarkPipelineTests(unittest.TestCase):
    def test_summarize_timings_reports_latency_and_fps(self):
        report = summarize_timings([20.0, 30.0, 40.0], warmup=5, total_frames=8)

        self.assertEqual(report["measured_frames"], 3)
        self.assertEqual(report["mean_ms"], 30.0)
        self.assertEqual(report["median_ms"], 30.0)
        self.assertEqual(report["p95_ms"], 40.0)
        self.assertEqual(report["steady_fps"], 33.33)
        self.assertTrue(report["meets_25fps"])

    def test_summarize_timings_rejects_empty_measurements(self):
        with self.assertRaises(ValueError):
            summarize_timings([], warmup=5, total_frames=5)


if __name__ == "__main__":
    unittest.main()
