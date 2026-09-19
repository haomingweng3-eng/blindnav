# 视障出行动态预判与主动导航

当前权威 Git 工作区是 `/Users/mima0000/blindnav`。`/Users/mima0000/Desktop/盲行导航` 只保留了旧版少量脚本和 `data/raw/test_cam.mp4` 测试素材；不要在 Desktop 目录直接运行旧版 `risk_engine.py`，否则不会得到本仓库记录的最新风险引擎和验收结果。

当前代码验证的是“检测/追踪结果 → 风险趋势判断 → 分级告警 → JSON 报告”链路。Android 端规划为手机摄像头默认运行、胸挂式独立摄像头可选增强输入；目前尚未完成 CameraX、外接摄像头传输和安卓真机验证。

没有真实视频时的三分钟演示顺序和统一答辩口径见 [DEMO_RUNBOOK.md](DEMO_RUNBOOK.md)。

提交前的复现、演示和可宣称范围见 [SUBMISSION_CHECKLIST.md](SUBMISSION_CHECKLIST.md)。

提交前可运行单入口只读审计；它会同时检查测试、语法、依赖版本、核心验收、真实采集状态和 Git 工作区：

```bash
python scripts/submission_audit.py
```

未采集真实视频时，审计返回失败是预期结果，并会列出 `collection_not_ready`；不能用强行忽略退出码的方式替代真实证据。

真实视频采集按 [DATA_COLLECTION.md](DATA_COLLECTION.md) 执行，场景记录表在 `data/collection_manifest.csv`。

视频放入 `data/raw/` 后，用 `python scripts/validate_collection.py` 检查采集进度；当前批次的归档说明和 SHA-256 清单见 [VIDEO_ARCHIVE.md](VIDEO_ARCHIVE.md) 与 [`data/raw/manifest.csv`](data/raw/manifest.csv)。

多段视频可以用 `python scripts/batch_detect_videos.py --raw-dir data/raw --output-dir runs/video_reports --device mps` 一次处理。

外部公开数据集的实际抽样结果见 [EXTERNAL_DATASET_TEST.md](EXTERNAL_DATASET_TEST.md)。

视觉、导航、端侧部署和助盲项目的横向对比见 [RELATED_PROJECTS_COMPARISON.md](RELATED_PROJECTS_COMPARISON.md)。

## 环境

项目基线是 Python 3.11、Apple Silicon MPS、YOLOv8n、Ultralytics、OpenCV 和 ByteTrack。

```bash
conda activate pt
python -m pip install -r requirements.txt
```

如果 `conda run -n pt` 没有进入正确解释器，直接使用该环境的 `bin/python`，并确认：

```bash
python --version
python -c "import cv2, torch, ultralytics; print(cv2.__version__, torch.__version__, ultralytics.__version__)"
```

## 测试和仿真

```bash
python -m unittest discover -s tests -v
python scripts/evaluate_risk_engine.py
```

答辩前可用一条命令检查核心链路和反馈输出：

```bash
python scripts/acceptance_check.py -o /tmp/blindnav-acceptance.json
```

如果只想检查已有风险报告是否满足 Android 接口契约：

```bash
python scripts/feedback_contract.py risk_report.json
```

仿真评估包含快速接近、慢速接近、临界接近、远离、静止、横向穿过、单帧框突变、噪声和重复帧，并输出 looming 阈值敏感性扫描。

## 检测记录回放

当只有其他检测器或公开视频的检测框时，输入 JSON：

```json
{
  "width": 1280,
  "height": 720,
  "records": [
    {
      "frame": 1,
      "track_id": "bike_0",
      "cls": "bicycle",
      "conf": 0.9,
      "box": [100, 100, 200, 200]
    }
  ]
}
```

运行回放：

```bash
python scripts/replay_detections.py detections.json -o risk_report.json
python scripts/replay_detections.py detections.json --looming-threshold 0.05
```

## YOLO + ByteTrack 视频

```bash
python scripts/detect_video.py input.mp4 risk_report.json 0.06
```

如果使用自定义微出行模型：

```bash
python scripts/detect_video.py input.mp4 risk_report.json 0.04 \
  --model runs/scooter_yolov8n/weights/best.pt \
  --device mps --conf 0.25
```

旧的三个位置参数仍然兼容；自定义模型的类别名必须使用项目支持的 `scooter`、`electric_bicycle`、`electric_bike` 或 `e-bike` 之一。

第三个参数是 looming 阈值。脚本使用 Ultralytics 官方 ByteTrack，并输出检测类别、轨迹数量、告警帧和风险特征。

告警 JSON 还包含平台无关的 `feedback` 字段：低风险短震动，警告级提示音加延后语音，危险级优先强震动和危险音。语音使用左侧/前方/右侧三级方向词，不播报未经标定的精确距离。具体 Android 振动器、TTS 和音频 API 尚未接入。安卓端接入边界和字段约定见 [ANDROID_INTEGRATION.md](ANDROID_INTEGRATION.md)；当前仓库没有 Android Studio 工程，先用回放 JSON 做跨模块联调。

检测报告会保留原始 `records`，因此可在不重复运行 YOLO 的情况下扫描阈值：

```bash
python scripts/calibrate_reports.py risk_report.json \
  --thresholds 0.02 0.03 0.04 0.05 0.06 0.08 0.10 \
  -o threshold_report.json
```

阈值扫描只能提供告警数量和首帧的调参证据；真实误报/漏报仍需人工查看视频或标注事件。

## 真实事件指标

检测报告生成后，先自动创建待填写的事件标注模板：

```bash
python scripts/prepare_annotations.py \
  runs/video_reports/ annotations/
```

模板默认标记 `annotation_complete: false`，在人工填写 `events` 并确认后改为 `true`；评估器会拒绝未完成模板，避免把空事件误当成无风险视频。

视频检测完成后，用一个轻量 JSON 记录每个有效事件的开始帧和冲突帧：

```json
{
  "video_id": "V01",
  "annotation_complete": true,
  "fps": 30,
  "duration_s": 30,
  "events": [
    {
      "event_id": "V01-E01",
      "start_frame": 120,
      "conflict_frame": 240,
      "target_class": "electric_bicycle"
    }
  ]
}
```

再运行：

```bash
python scripts/evaluate_events.py \
  annotations/V01.json runs/video_reports/<同名报告>.json \
  -o runs/video_reports/V01_metrics.json
```

输出包括事件召回率、首个告警到冲突帧的中位/P10提前量，以及每分钟误报告警数。事件窗口是人工定义的评估范围，不是自动生成的“真值”；没有标注就不能宣称真实准确率。

12 段视频都完成标注和检测后，可批量汇总：

```bash
python scripts/batch_evaluate_events.py \
  annotations/ runs/video_reports/ \
  -o runs/video_reports/metrics_summary.json \
  --csv-output runs/video_reports/metrics_summary.csv
```

CSV 同时包含逐视频行和 `TOTAL` 总计行，可直接导入 Excel 或作为答辩实验表的数据源。

## 实时 rawvideo 回归

```bash
ffmpeg -i input.mp4 -f rawvideo -pix_fmt bgr24 - | \
python scripts/live_demo.py \
  --width 640 --height 640 \
  --headless --max-frames 45 \
  --device mps \
  --report live_report.json
```

实时报告包含处理帧数、最后源帧号、轨迹数、告警数、最近处理 FPS、设备、模型和阈值。实时脚本里的 FPS 用于运行监控；正式性能结论应使用 `benchmark_pipeline.py`。

looming 和横向速度统一换算到 30 FPS 参考单位；离线视频从容器读取源 FPS，rawvideo 回归需要显式传入 `--input-fps`。

## 性能基准

```bash
python scripts/benchmark_pipeline.py input.mp4 --device mps -o benchmark.json
```

性能结果必须注明设备、模型、分辨率、视频帧率和是否排除预热帧；基准同时输出 P95 逐帧延迟及是否达到 200ms 工程门槛。当前 Mac 合成视频测得约 30 FPS，不能外推到安卓骁龙设备。

ONNX 候选模型可单独测量推理层：

```bash
python scripts/benchmark_onnx.py models/yolov8n.onnx \
  --frames 30 --warmup 5 -o runs/onnx_benchmark.json
```

该结果只覆盖 ONNX Runtime 模型推理，不包含 CameraX、ByteTrack、风险引擎或系统反馈延迟。

## 当前边界

- 阈值扫描结果来自参数化仿真，不是真实道路准确率。
- 横向告警还会检查目标预测轨迹是否切入简化的图像行走走廊；走廊宽度和预测帧数是工程参数，不等同于完成了相机标定或真实地面路径交点预测。
- 合成缩放视频只用于验证软件链路，不代表电动车场景。
- 真实胸挂视角电动车数据、误报/漏报、预警提前量和安卓性能仍待验证。
- 不应对外宣称精确距离、精确碰撞时间、100% 避障或替代导盲杖/导盲犬。
