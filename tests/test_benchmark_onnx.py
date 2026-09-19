import unittest

from scripts.benchmark_onnx import summarize_onnx_timings


class BenchmarkOnnxTests(unittest.TestCase):
    def test_summarizes_inference_timings(self):
        result = summarize_onnx_timings([10.0, 20.0, 30.0], warmup=2, total_frames=5)
        self.assertEqual(result["measured_frames"], 3)
        self.assertEqual(result["mean_ms"], 20.0)
        self.assertEqual(result["median_ms"], 20.0)
        self.assertEqual(result["p95_ms"], 30.0)
        self.assertEqual(result["steady_fps"], 50.0)

    def test_rejects_empty_timings(self):
        with self.assertRaises(ValueError):
            summarize_onnx_timings([], warmup=2, total_frames=2)


if __name__ == "__main__":
    unittest.main()
