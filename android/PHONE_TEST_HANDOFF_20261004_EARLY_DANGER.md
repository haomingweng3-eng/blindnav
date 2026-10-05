# 明日手机实测交接：提前危险级别

## 当前 APK

- 文件：`C:/Users/19770/Documents/Codex/blindnav_external/android_candidate_20261004/blindnav-two-wheeler-overlay-early-danger-debug.apk`
- 包名：`com.blindnav.mobile`
- SHA-256：`A25F7840A056C1BB7433DDA49ED5BCFD90B90F5E399AC6DA0AA2B40A4C694C44`
- 本机状态：Gradle clean/test/assembleDebug 成功，Android 静态契约检查通过
- 尚未验证：真机安装、相机预览、端侧 FPS、反馈硬件和长时间运行

## 本次规则

当目标同时满足“骑行者存在、持续接近、路线已确认被占用”，并且预计约 1.2 秒内进入近距离时，提前升级为危险。旧的通用风险引擎默认仍保持保守阈值，只有手机实时应用显式启用该规则。

## 安装与启动

```text
adb install -r blindnav-two-wheeler-overlay-early-danger-debug.apk
adb shell am start -n com.blindnav.mobile/.MainActivity
```

## 实测顺序

1. 允许相机权限，确认 CameraX 预览正常；
2. 点击“反馈自检”，确认震动、提示音和语音均能执行；
3. 先用停放电动车测试：应保持安静，不应触发危险；
4. 再用有人骑行、从远处正面接近的目标测试；
5. 记录首次检测帧、黄色提示帧、红色危险帧、漏检帧和轨迹中断帧；
6. 记录页面显示的 FPS、P95 推理耗时和丢帧数；
7. 手机测试时由旁人观察，暂不在真实交通环境中依赖该预警。

## 关键结果字段

- `notice_frame`：首次确认路线影响；
- `danger_frame`：提前危险升级；
- `fps`、`p95_processing_ms`、`dropped_frames`；
- `false_alert_static`：停放车辆是否误报；
- `track_continuity`：同一目标是否保持同一轨迹。
