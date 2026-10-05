# 手机实时线路预览交接

## 当前候选 APK

- 文件：`C:/Users/19770/Documents/Codex/blindnav_external/android_candidate_20261004/blindnav-two-wheeler-overlay-debug.apk`
- 包名：`com.blindnav.mobile`
- 版本：`0.1.0 (1)`
- SHA-256：`6174e48dc7ff30ea7f45df880faba75a7326279fd0d97e7093021213c2e426d1`

该版本在手机相机预览上绘制两轮车框、青色历史接地点轨迹和紫色短时路面预测线，并保留震动、提示音和语音反馈。

## 连接手机后

```text
adb install -r blindnav-two-wheeler-overlay-debug.apk
adb shell am start -n com.blindnav.mobile/.MainActivity
```

## 先观察

1. 允许相机权限，确认相机画面出现；
2. 让一辆两轮车从远处连续进入画面；
3. 确认车框连续、青色轨迹跟随车轮接地点；
4. 确认紫色线路沿道路方向向前延伸；
5. 接近时观察黄框/红框与语音、震动是否同步；
6. 记录 FPS、P95 推理耗时、丢帧、漏检和误报。

紫色线路是图像平面短时外推，用于实时观察和初步预警，尚未标定为实际米数或碰撞保证。
