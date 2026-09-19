# 模型产物

当前仓库保留两个可追溯的基线模型：

| 文件 | 用途 | SHA-256 |
|---|---|---|
| `yolov8n.pt` | Python/Ultralytics 基线 | `f59b3d833e2ff32e194b5bb8e08d211dc7c5bdf144b90d2c8412c47ccfc83b36` |
| `yolov8n.onnx` | Android/跨平台候选导出 | `474e8195a6860681f89df0b6a45a0b881583afb51095469c600eae1379b88311` |

ONNX 导出参数：输入 `640×640`、固定 batch `1`、opset `12`、未启用 simplify。当前已用 ONNX checker 和 Ultralytics + ONNX Runtime CPU 对空白帧做过加载/推理回归；这不等于 Android 真机性能或目标类别召回率验证。

参考基准命令：`python scripts/benchmark_onnx.py models/yolov8n.onnx --frames 30 --warmup 5`。任何性能数字都必须同时记录 CPU/设备、预热帧数和是否只测模型推理。

Ultralytics 当前官方许可说明见：[Ultralytics License](https://www.ultralytics.com/license)。页面将 AGPL-3.0 作为开源路径，并说明不希望公开完整项目、或要做闭源/嵌入式产品时需要另行确认 Enterprise License。这里仅记录许可风险，不构成法律意见；比赛提交、公开仓库和未来产品化应分别复核适用条款。不要把模型文件本身的可加载性表述成已完成产品化授权。
