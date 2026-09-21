# Android 端交接文档

**阶段**：本地模型接入完成，待真机验证  
**工作区**：`/Users/mima0000/blindnav`  
**最近提交**：见 `git log -3 --oneline`

## 当前已经完成

Android 端目前具备以下链路：

```text
CameraX 手机摄像头
  → YUV_420_888 转 RGB
  → letterbox / CHW / 归一化
  → ONNX Runtime
  → YOLOv8 [1,84,8400] 解码与按类别 NMS
  → Detection 列表
  → 页面状态显示检测数量
```

外接摄像头走同一个 `FrameSource` 接口，但 USB/Wi-Fi 传输层还没有实现；当前 `ExternalFrameSource.push()` 是给后续传输适配器使用的边界。

## 关键文件

- `android/app/src/main/java/com/blindnav/mobile/sensing/PhoneCameraFrameSource.kt`：手机 CameraX 输入、帧生命周期和 RGB 拷贝。
- `android/app/src/main/java/com/blindnav/mobile/inference/Yuv420RgbConverter.kt`：YUV 平面和 stride 处理。
- `android/app/src/main/java/com/blindnav/mobile/inference/LetterboxPreprocessor.kt`：640×640 输入预处理。
- `android/app/src/main/java/com/blindnav/mobile/inference/OnnxYoloDetector.kt`：模型加载和 ONNX Runtime 推理。
- `android/app/src/main/java/com/blindnav/mobile/inference/YoloOutputDecoder.kt`：YOLO 输出解码、坐标还原和 NMS。
- `android/app/src/main/java/com/blindnav/mobile/inference/InferencePipeline.kt`：帧到检测结果的接线。
- `android/app/src/main/assets/yolov8n.onnx`：随 APK 打包的模型，SHA-256 应与 `models/yolov8n.onnx` 相同。

## 构建和验证

在安装 JDK 17、Android SDK API 35 的机器上：

```bash
cd /Users/mima0000/blindnav
JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
  android/gradlew -p android test assembleDebug --no-daemon
```

只做仓库级静态检查：

```bash
python3 scripts/check_android_contract.py
python3 scripts/submission_audit.py
```

APK 输出：`android/app/build/outputs/apk/debug/app-debug.apk`。

## 真机接手顺序

1. 安装 Debug APK，授予相机权限。
2. 确认页面出现“运行中”，观察帧号是否递增。
3. 用静态物体和行人测试检测数量变化；不要把检测结果当成安全保证。
4. 记录启动耗时、端到端帧率、发热、丢帧和模型推理异常。
5. 点击“反馈自检”确认震动、提示音和 TTS，再把 `FrameDetections` 接到风险生产者并调用现有 `FeedbackDispatcher`。

## 尚未完成，不能对外宣称

- 尚未在真实 Android 手机上完成 CameraX 权限、持续运行和功耗验证。
- 当前页面只显示检测数量，还没有接入 Python 风险引擎的 `looming`、轨迹和分级反馈。
- 尚未实现外接摄像头的 USB/Wi-Fi 协议和断连恢复。
- Android 已实现反馈 JSON 解析和震动/提示音/TTS 执行层，但尚未完成 ByteTrack、风险仲裁到 Dispatcher 的实时闭环和真机验证。
- 当前模型仍是 YOLOv8n COCO 模型，不能宣称已经解决国内电动车类别识别问题。
- 模型许可和比赛公开展示、后续闭源产品化需要分别复核；不要把 APK 构建成功表述为许可已解决。

## 交接给队友的最小任务

优先完成一台 Android 真机上的：

```text
启动 → 相机权限 → 30 秒持续推理 → 记录 FPS/延迟/温度 → 正常停止
```

如果这一步稳定，再实现 `FrameDetections → 风险生产者 → FeedbackDispatcher`；JSON 解析器和 Dispatcher 已在仓库中，不要重复开发。不要先做地图、双摄、SLAM 或云端多模态功能。
