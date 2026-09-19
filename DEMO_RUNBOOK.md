# 现场演示脚本

这份脚本用于没有真实电动车视频时的答辩演示。它展示的是软件链路和交互输出，不把合成数据冒充真实道路效果。

## 演示顺序（约 3 分钟）

开始前先跑一次总验收：

```bash
python scripts/acceptance_check.py -o /tmp/blindnav-acceptance.json
```

看到 `"passed": true` 后再进入下面的展示步骤。它会同时检查参数化风险场景和安卓反馈回放。

### 1. 先展示风险引擎的可解释性

```bash
python scripts/evaluate_risk_engine.py
```

重点指出：输入是连续检测框，输出包含 `looming`、横向趋势、方向、路径冲突、风险等级和反馈动作；阈值扫描用于展示工程取舍，不是道路准确率。

### 2. 回放一条确定会触发的接近场景

```bash
python scripts/replay_detections.py \
  tests/fixtures/synthetic_approach_detections.json \
  -o /tmp/blindnav-risk-report.json
```

打开报告中的 `alerts[0]`，展示：

```text
level_name: 警告
direction: front
reason: 快速接近
feedback.tone: warning
feedback.vibration_ms: [120, 70, 120]
feedback.speech: 注意，前方自行车
```

这一步可以直接交给安卓端或模拟器消费，不依赖 YOLO 和摄像头权限。

### 3. 展示实时管线的无摄像头回归

如果已经准备好合成视频 `input.mp4`：

```bash
ffmpeg -i input.mp4 -f rawvideo -pix_fmt bgr24 - | \
python scripts/live_demo.py \
  --width 640 --height 640 \
  --input-fps 15 \
  --headless --max-frames 45 \
  --device mps \
  --report /tmp/blindnav-live-report.json
```

若有自定义微出行模型，离线检测命令改为：

```bash
python scripts/detect_video.py input.mp4 risk_report.json 0.04 \
  --model runs/scooter_yolov8n/weights/best.pt \
  --device mps --conf 0.25
```

现场只展示报告里的处理帧数、源帧号、轨迹数、告警数和最近 FPS。正式性能数字以基准脚本的预热后统计为准，不用运行监控 FPS 冒充安卓性能。

### 4. 最后展示性能证据和边界

```bash
python scripts/benchmark_pipeline.py input.mp4 --device mps \
  -o /tmp/blindnav-benchmark.json
```

必须同时说清楚：当前约 30 FPS 的数据来自 Apple Silicon MPS；真实电动车场景、安卓骁龙性能、视障用户反馈仍未验证。

## 评委追问时的统一口径

- **为什么没有真实视频？** 当前阶段先完成了检测结果到风险判断再到主动反馈的可复现闭环；真实胸挂视角采集和用户验证是下一阶段验证，不把合成数据包装成真实准确率。
- **这是碰撞预测吗？** 当前是基于连续框面积增长、横向运动和简化图像走廊的风险预警原型，不宣称精确碰撞时间或精确距离。
- **怎么接入手机？** 安卓端只消费 `feedback`，协议和 Dispatcher 约定见 [ANDROID_INTEGRATION.md](ANDROID_INTEGRATION.md)。
- **阈值怎么定？** 当前用参数化场景做敏感性扫描；真实阈值要在目标视角和设备上重新标定。
- **最短下一步是什么？** 用少量代表性电动车片段或检测框记录先做离线回放，再在安卓真机测端到端延迟、功耗和提示打断。

## 不应展示或宣称

- 不把 `/tmp` 下的合成视频称为真实电动车数据。
- 不报“准确率、召回率、提前几秒”这类尚无真实标注支持的数字。
- 不把 `area_n` 直接换算为米数、碰撞时间或安全距离。
- 不把当前 Mac 的性能结果外推为安卓骁龙 7/8 系列性能。
