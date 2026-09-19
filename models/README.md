# 模型产物

当前仓库保留两个可追溯的基线模型：

| 文件 | 用途 | SHA-256 |
|---|---|---|
| `yolov8n.pt` | Python/Ultralytics 基线 | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
| `yolov8n.onnx` | Android/跨平台候选导出 | `474e8195a6860681f89df0b6a45a0b881583afb51095469c600eae1379b88311` |

ONNX 导出参数：输入 `640×640`、固定 batch `1`、opset `12`、未启用 simplify。当前已用 ONNX checker 和 Ultralytics + ONNX Runtime CPU 对空白帧做过加载/推理回归；这不等于 Android 真机性能或目标类别召回率验证。

模型来源、许可证和公开发布边界在正式提交前仍需按所使用的 Ultralytics 版本和赛事要求复核；不要把模型文件本身的可加载性表述成已完成产品化授权。
