# 手机实测交接

当前候选 APK 已在本机重新构建：

- APK：`C:/Users/19770/Documents/Codex/blindnav_external/android_candidate_20261003/blindnav-two-wheeler-candidate-debug.apk`
- 包名：`com.blindnav.mobile`
- 版本：`0.1.0 (1)`
- SHA-256：`9e5cd5005c1eeab86ac55161ef1bb3933eaf7fc36621ac930e4dba90aa2ea68`
- 已确认 APK 内含：`two_wheeler_candidate.onnx`、`yolov8n.onnx`

## 安装与启动

在安装 Android SDK platform-tools 的电脑上，连接一台开启 USB 调试的手机，确认设备状态为 `device` 后执行：

```text
adb install -r blindnav-two-wheeler-candidate-debug.apk
adb shell am start -n com.blindnav.mobile/.MainActivity
```

如果系统要求相机权限，允许后观察预览和状态栏中的检测数量、FPS、推理耗时及丢帧数。

## 第一轮验收

1. 点击“反馈自检”，确认震动、提示音和语音都能执行。
2. 用一段迎面接近视频或实际走动场景，确认同一目标连续出现。
3. 目标框面积持续变大、底部下移且位于中央路线时，应先播“注意”。
4. 继续接近并达到近距离阈值时，应升级为“危险”。
5. 停放车辆、目标向路线外离开时，不应持续升级告警。
6. 记录页面 FPS、P95 推理耗时、丢帧数和误报/漏报，不把结果当作安全保证。

当前 APK 仍是候选验证版本，未接入正式安全预警。
