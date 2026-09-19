# BlindNav Android 首轮工程

这是 Android 端的第一阶段骨架，当前目标是先冻结输入边界：

- `PhoneCameraFrameSource`：默认手机 CameraX 摄像头输入；
- `ExternalFrameSource`：胸挂摄像头或其他传感器通过 USB/Wi-Fi 解码后调用 `push()`；
- `FrameSequenceValidator`：统一校验帧号、单调时间戳、尺寸和丢帧字段；
- 后续推理层只接收合法帧，不关心输入来自手机还是外接节点。

## 当前限制

本工作区当前没有 JDK、Android SDK 或 Gradle Wrapper，因此尚未声称 APK 编译通过。可以先运行仓库根目录的静态检查：

```bash
python scripts/check_android_contract.py
```

拿到 Android 开发机后，在本目录执行：

```bash
./gradlew test
./gradlew assembleDebug
```

第一轮真机验证顺序：手机摄像头权限 → CameraX 帧回调 → 帧号/时间戳日志 → 固定 JSON 风险回放 → 震动/提示音。外接摄像头必须在手机输入路径稳定后再接入。
