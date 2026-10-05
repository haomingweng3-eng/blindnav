# BlindNav Android 首轮工程

这是 Android 端的第一阶段工程，当前目标是先冻结输入边界并保留可替换的端侧推理入口：

- `PhoneCameraFrameSource`：默认手机 CameraX 摄像头输入；
- `ExternalFrameSource`：胸挂摄像头或其他传感器通过 USB/Wi-Fi 解码后调用 `push()`；
- `FrameSequenceValidator`：统一校验帧号、单调时间戳、尺寸和丢帧字段；
- `Yuv420RgbConverter` + `RgbFrameRotator` + `LetterboxPreprocessor`：将 CameraX 的 YUV 帧复制为自有 RGB 缓冲区，按传感器旋转角校正，再生成 YOLO 的 CHW float 输入；
- 后续推理层只接收合法帧，不关心输入来自手机还是外接节点。

当前手机预警候选：`app/src/main/assets/two_wheeler_candidate_320.onnx`。它是
同一混合交通模型的 320 输入 ONNX 导出，class 1 统一作为“两轮车候选”，用于
迎面接近预警。原 640 输入模型仍保留作对照。实时路径只运行这一套模型，停放目标由连续轨迹、中央路线走廊、面积
增长和接近趋势过滤；`yolov8n.onnx` 与 `RiderGateDetector` 仍保留作离线
对照，不再进入手机实时路径。ONNX Runtime 会按 NNAPI、XNNPACK、CPU 顺序
回退，并在状态栏显示当前后端。端侧风险判断仍是近似规则，需在真实手机上
测量速度和误报后再决定是否用于安全场景。当前候选构建还在相机预览层显示
检测框和青色已观测接地点轨迹；当前实时路径不绘制未经验证的未来外推线。

CameraX 分析流先限制到约 640x360，再进入 320 模型，避免对 1080p 原始帧做
完整的颜色转换和旋转；`KEEP_ONLY_LATEST` 继续保留，推理跟不上时优先保持低延迟。

## 当前限制

仓库已提交 Gradle Wrapper、CameraX 输入、ONNX Runtime 推理、反馈执行层和 JVM 单元测试源码。当前两轮车模型、骑行者过滤和路线预测改动已在本机重新构建，证据见 [BUILD_REPORT.md](BUILD_REPORT.md)；真机安装、摄像头和端到端延迟仍待验证。没有 Android SDK/JDK 时，可以先运行仓库根目录的静态检查：

```bash
python scripts/check_android_contract.py
```

拿到 Android 开发机后，在本目录执行：

```bash
./gradlew test
./gradlew assembleDebug
```

拿到手机并开启 USB 调试后，在仓库根目录执行一键安装/启动检查：

```bash
python scripts/android_smoke_test.py
```

脚本要求恰好连接一台状态为 `device` 的 Android 设备；没有设备时会返回 `no_device`，不会把构建成功误报为真机成功。

第一轮真机验证顺序：手机摄像头权限 → 点击“反馈自检”确认震动/提示音/TTS → CameraX 预览与帧回调 → 帧号/时间戳日志 → ONNX 推理输出 → `TemporalRiskEngine` 两级风险判断 → 固定 JSON 风险回放。`FeedbackReportParser` 和 `FeedbackDispatcher` 已实现报告解析及硬件执行，`MainActivity` 已接入单模型实时路径；轻量背景运动补偿已接入，但仍需在手机上测量速度、功耗和误报。外接摄像头必须在手机输入路径稳定后再接入。

手机主循环同时接入 `GuidanceEngine` 和 `GeometryWalkableRegionEstimator`，输出保持直行、左右绕行、注意、停止和不确定减速状态。几何估计器是可替换的保守回退，不能替代经过验证的可行走区域分割模型。

也可以不依赖实时摄像头，直接回放 Python 风险报告验证 Android 反馈链路：

```bash
adb shell am start -n com.blindnav.mobile/.MainActivity \
  --es blindnav.risk_report_json '{"alerts":[{"frame":1,"track_id":"demo-1","cls":"bicycle","level":2,"feedback":{"priority":"warning","vibration_ms":[120,70,120],"tone":"warning","speech":"注意，前方自行车","speech_delay_ms":250}}]}'
```

页面应显示“风险报告回放：执行 1 条反馈”，设备应执行对应震动、提示音和语音。该命令只验证跨模块契约，不代表真实道路准确率。
