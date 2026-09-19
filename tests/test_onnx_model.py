import unittest
from pathlib import Path

import onnx


class OnnxModelTests(unittest.TestCase):
    def test_exported_model_is_a_valid_fixed_640_graph(self):
        path = Path(__file__).parents[1] / "models" / "yolov8n.onnx"
        self.assertTrue(path.is_file())
        model = onnx.load(str(path))
        onnx.checker.check_model(model)
        input_shape = [dim.dim_value for dim in model.graph.input[0].type.tensor_type.shape.dim]
        output_shape = [dim.dim_value for dim in model.graph.output[0].type.tensor_type.shape.dim]
        self.assertEqual(input_shape, [1, 3, 640, 640])
        self.assertEqual(output_shape, [1, 84, 8400])


if __name__ == "__main__":
    unittest.main()
