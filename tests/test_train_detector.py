import unittest

from scripts.train_detector import build_train_kwargs


class TrainDetectorTests(unittest.TestCase):
    def test_builds_reproducible_training_configuration(self):
        kwargs = build_train_kwargs(
            data="dataset/data.yaml",
            epochs=40,
            imgsz=640,
            batch=8,
            device="cuda:0",
            project="runs",
            name="local_v1",
            seed=20260926,
        )

        self.assertEqual(kwargs["data"], "dataset/data.yaml")
        self.assertEqual(kwargs["epochs"], 40)
        self.assertEqual(kwargs["imgsz"], 640)
        self.assertEqual(kwargs["batch"], 8)
        self.assertEqual(kwargs["device"], "cuda:0")
        self.assertEqual(kwargs["project"], "runs")
        self.assertEqual(kwargs["name"], "local_v1")
        self.assertEqual(kwargs["seed"], 20260926)

    def test_rejects_invalid_training_values(self):
        with self.assertRaises(ValueError):
            build_train_kwargs(data="dataset/data.yaml", epochs=0)
        with self.assertRaises(ValueError):
            build_train_kwargs(data="dataset/data.yaml", imgsz=0)


if __name__ == "__main__":
    unittest.main()
