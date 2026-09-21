# Android 构建证据

最后验证日期：2026-09-21

## 本机结果

在 macOS Apple Silicon 上使用 Homebrew OpenJDK 17 执行：

```bash
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
cd android
./gradlew clean test assembleDebug
```

结果：`BUILD SUCCESSFUL`。

- Android JVM 单元测试：Debug/Release 均通过
- Debug APK：`android/app/build/outputs/apk/debug/app-debug.apk`
- APK 大小：89,527,408 bytes
- APK SHA-256：`6bc11c43de4f2cf8f6d34a43eec11e0677218692851693353c3107052dc54002`
- Android 静态契约检查：通过

构建时有两类非阻断提示：Android SDK XML 版本提示，以及 ONNX Runtime/CameraX 原生库无法 strip、因此按原样打包。这两项没有导致构建失败，也不等于真机性能已验证。

## 尚未完成的验证

当前机器没有连接到可用 Android 真机，因此没有声称 APK 已安装、摄像头权限已授予、CameraX 预览已显示、反馈自检已实际发声/振动、端侧 FPS/延迟已测量或长时间运行稳定。

拿到测试机后，队友应先安装该 APK，再按 [android/README.md](README.md) 的顺序记录：权限、预览、帧回调、ONNX 检测、反馈执行和连续运行温度。
