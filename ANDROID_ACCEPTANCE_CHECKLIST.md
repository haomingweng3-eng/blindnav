# Android 真机验收清单

这份清单用于把“能编译”与“手机上真的能运行”分开记录。不要把模型级 FPS 当成手机端到端 FPS。

## 1. 安装前检查

- 手机通过 USB 连接，`adb devices` 状态为 `device`；
- 手机开启开发者选项中的 USB 调试；
- 小米/Redmi 设备另外开启“USB 安装/通过 USB 安装”；
- APK：`android/app/build/outputs/apk/debug/app-debug.apk`；
- 当前 APK SHA-256：`7096412a2266c0cee533548b66f4494663a9a5a2cf373c0ef8d0397967aac20a`。

## 2. 构建与安装

```bash
JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home \
  android/gradlew -p android test assembleDebug --no-daemon

python3 scripts/android_smoke_test.py \
  --apk android/app/build/outputs/apk/debug/app-debug.apk
```

如果 ADB 返回 `INSTALL_FAILED_USER_RESTRICTED`，先在手机上允许 USB 安装；不要把这个错误记录成代码构建失败。

## 3. 30 秒运行测试

安装成功后，记录以下内容：

| 项目 | 记录值 |
| --- | --- |
| 手机型号 / Android 版本 | |
| 启动到首帧时间 | |
| 持续运行时长 | |
| 端到端平均 FPS | |
| 端到端 P95 延迟 | |
| 丢帧数 | |
| 发热 / 降频 | |
| 是否出现崩溃或相机中断 | |
| 检测数量是否随画面变化 | |
| 反馈自检：震动 / 音效 / TTS | |

测试顺序：静态物体 → 行人 → 安全距离外电动车 → 受控接近视频。不得在真实车流中制造危险接近，也不能把检测框出现当成安全保证。

## 4. 当前已知基线

- `models/yolov8n.onnx` 模型级基准：平均 38.85 ms，约 25.74 FPS；不包含 CameraX、RGB 转换、风险引擎和反馈执行；
- Android 静态契约检查通过；
- Python 回归测试 120 项通过；
- 当前模型仍是 COCO YOLOv8n，不能宣称已经解决本地电动车识别问题；
- 本地手机视角微调实验暂未达到可部署效果。

## 5. 结果提交

队友完成后提交：手机型号、上述表格、运行截图或录屏、APK 安装结果、`adb logcat` 中的异常（如有），以及是否能稳定显示检测数量。未完成真机测试前，汇报中只能写“APK 构建通过，待真机验证”。
