import unittest

import numpy as np

from scripts.onnx_inference import decode_yolov8, infer_image, letterbox


class OnnxInferenceTests(unittest.TestCase):
    def test_letterbox_preserves_aspect_ratio_and_returns_model_tensor(self):
        image = np.zeros((480, 640, 3), dtype=np.uint8)
        tensor, ratio, pad = letterbox(image, 640)
        self.assertEqual(tensor.shape, (1, 3, 640, 640))
        self.assertAlmostEqual(ratio, 1.0)
        self.assertEqual(pad, (0.0, 80.0))
        self.assertEqual(tensor.dtype, np.float32)

    def test_onnx_model_runs_through_preprocess_decode_and_nms(self):
        image = np.zeros((640, 640, 3), dtype=np.uint8)
        detections = infer_image(
            image,
            "/Users/mima0000/blindnav/models/yolov8n.onnx",
            conf_threshold=0.25,
        )
        self.assertIsInstance(detections, list)
        self.assertEqual(detections, [])

    def test_decode_maps_letterboxed_boxes_and_suppresses_overlap(self):
        output = np.zeros((1, 84, 3), dtype=np.float32)
        output[0, :4, 0] = [320, 320, 100, 100]
        output[0, :4, 1] = [322, 322, 100, 100]
        output[0, :4, 2] = [500, 500, 40, 40]
        output[0, 4 + 1, 0] = 0.9
        output[0, 4 + 1, 1] = 0.8
        output[0, 4 + 3, 2] = 0.95

        detections = decode_yolov8(
            output,
            original_shape=(640, 640, 3),
            ratio=1.0,
            pad=(0.0, 0.0),
            conf_threshold=0.25,
            iou_threshold=0.5,
        )

        self.assertEqual(len(detections), 2)
        self.assertEqual({item["class_name"] for item in detections}, {"bicycle", "motorcycle"})


if __name__ == "__main__":
    unittest.main()
