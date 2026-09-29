# 2026-09 手机视角人工复核数据集

这是第一批人工复核后的训练数据，供 4060 电脑做 YOLO 基线训练。

- 图片：104 张
- 目标框：365 个
- 电动车：347 个
- 汽车：10 个
- 行人：8 个
- 按视频划分 train/val/test，避免同一视频的相邻帧同时泄漏到训练集和测试集

## 使用方式

在仓库根目录运行：

```bash
python -m ultralytics yolo detect train \
  data=data/phone_camera_202609_reviewed/data.yaml \
  model=models/yolov8n.pt \
  imgsz=640 epochs=50 batch=16 device=0 \
  project=runs/train name=phone_camera_202609_baseline
```

如果显存不足，把 `batch=16` 改成 `batch=8` 或 `batch=4`。

## 重要边界

这是检测训练集，不是最终的风险评估集。它只能回答“画面里有没有电动车、框在哪里”，不能单独证明目标会不会进入行走路线或会不会发生冲突。训练完成后必须用 `test` 划分和原始视频回放验证。

路边静止车辆保留在数据中：它们对近距离避障有价值；动态冲突判断由后续的轨迹、路线走廊和接近趋势模块完成。
