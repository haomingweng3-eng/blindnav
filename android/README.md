# BlindNav Android 首轮工程

这是 Android 端的第一阶段工程，当前目标是先冻结输入边界并保留可替换的端侧推理入口：

- `PhoneCameraFrameSource`：默认手机 CameraX 摄像头输入；
- `ExternalFrameSource`：胸挂摄像头或其他传感器通过 USB/Wi-Fi 解码后调用 `push()`；
- `FrameSequenceValidator`：统一校验帧号、单调时间戳、尺寸和丢帧字段；
- `Yuv420RgbConverter` + `LetterboxPreprocessor`：将 CameraX 的 YUV 帧复制为自有 RGB 缓冲区，再生成 YOLO 的 CHW float 输入；
- 后续推理层只接收合法帧，不关心输入来自手机还是外接节点。

## 当前限制

仓库已提交 Gradle Wrapper、CameraX 输入、ONNX Runtime 推理和 JVM 单元测试源码；但当前开发机没有可用 JDK，因而本机尚未声称 APK 或 Android 单元测试编译通过。没有 Android SDK/JDK 时，可以先运行仓库根目录的静态检查：

```bash
python scripts/check_android_contract.py
```

拿到 Android 开发机后，在本目录执行：

```bash
./gradlew test
./gradlew assembleDebug
```

第一轮真机验证顺序：手机摄像头权限 → CameraX 预览与帧回调 → 帧号/时间戳日志 → ONNX 推理输出 → 固定 JSON 风险回放 → 震动/提示音。当前 `MainActivity` 已接通预览和检测状态显示，但风险 JSON 的 Vibrator/TTS Dispatcher 尚未接入；外接摄像头必须在手机输入路径稳定后再接入。
