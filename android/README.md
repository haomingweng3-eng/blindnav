# BlindNav Android 首轮工程

这是 Android 端的第一阶段工程，当前目标是先冻结输入边界并保留可替换的端侧推理入口：

- `PhoneCameraFrameSource`：默认手机 CameraX 摄像头输入；
- `ExternalFrameSource`：胸挂摄像头或其他传感器通过 USB/Wi-Fi 解码后调用 `push()`；
- `FrameSequenceValidator`：统一校验帧号、单调时间戳、尺寸和丢帧字段；
- `Yuv420RgbConverter` + `RgbFrameRotator` + `LetterboxPreprocessor`：将 CameraX 的 YUV 帧复制为自有 RGB 缓冲区，按传感器旋转角校正，再生成 YOLO 的 CHW float 输入；
- 后续推理层只接收合法帧，不关心输入来自手机还是外接节点。

## 当前限制

仓库已提交 Gradle Wrapper、CameraX 输入、ONNX Runtime 推理、反馈执行层和 JVM 单元测试源码。当前已在 OpenJDK 17 下完成 `clean test assembleDebug`，构建证据见 [BUILD_REPORT.md](BUILD_REPORT.md)；真机安装、摄像头和端到端延迟仍待验证。没有 Android SDK/JDK 时，可以先运行仓库根目录的静态检查：

```bash
python scripts/check_android_contract.py
```

拿到 Android 开发机后，在本目录执行：

```bash
./gradlew test
./gradlew assembleDebug
```

第一轮真机验证顺序：手机摄像头权限 → 点击“反馈自检”确认震动/提示音/TTS → CameraX 预览与帧回调 → 帧号/时间戳日志 → ONNX 推理输出 → `TemporalRiskEngine` MVP → 固定 JSON 风险回放。`FeedbackReportParser` 和 `FeedbackDispatcher` 已实现报告解析及硬件执行，`MainActivity` 已接入自检和端侧 MVP；正式 ByteTrack/风险仲裁仍需标定。外接摄像头必须在手机输入路径稳定后再接入。

也可以不依赖实时摄像头，直接回放 Python 风险报告验证 Android 反馈链路：

```bash
adb shell am start -n com.blindnav.mobile/.MainActivity \
  --es blindnav.risk_report_json '{"alerts":[{"frame":1,"track_id":"demo-1","cls":"bicycle","level":2,"feedback":{"priority":"warning","vibration_ms":[120,70,120],"tone":"warning","speech":"注意，前方自行车","speech_delay_ms":250}}]}'
```

页面应显示“风险报告回放：执行 1 条反馈”，设备应执行对应震动、提示音和语音。该命令只验证跨模块契约，不代表真实道路准确率。
