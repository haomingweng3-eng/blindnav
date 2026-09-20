# 本地视角伪标签适配实验

**状态**：实验性候选模型，不是人工标注验收模型。  
**目的**：验证开放词汇教师框能否快速蒸馏成较小的本地电动车检测器，接入现有 ByteTrack 和风险引擎。

## 数据和训练

- 教师：YOLO-World，提示词 `moped`；置信度阈值 `0.70`；
- 候选：95 张图片、95 个框、来自 13 段视频；
- 划分：按视频段拆分，train 61、val 9、test 25；
- 学生：YOLOv8n，单类 `electric_bicycle`；
- 输入：320×320，30 epochs，Apple M1 MPS；
- 权重：`models/electric_bicycle_pseudo_yolov8n_320_v1.pt`；
- SHA-256：`14d97bdee2c26dee28c874e5b75ae5b742555ee6de72d032eaf67eb933980d85`。

伪标签测试集结果为 mAP50=0.914、mAP50-95=0.622。这只表示学生模型拟合了教师框，不能解释为真实数据集准确率。

## 本地视频回归

对 13 段原始视频运行检测、ByteTrack 和风险引擎：

- 13/13 视频处理成功；
- 6 段视频产生 `electric_bicycle` 轨迹，共 6 个轨迹；
- 1 个轨迹触发“快速接近”警告，反馈为“注意，前方电动车”；
- 由于本地视频尚未完成独立人工框和事件标注，不能计算真实 precision、recall、漏报率或误报率。

完整本地视频汇总见 `local_video_summary.json`。训练曲线、混淆矩阵和预测样例也在本目录。

## 教师阈值消融

| 教师 `moped` 阈值 | 候选图片 | 伪标签 test mAP50 | 本地视频轨迹 | 本地告警 |
|---:|---:|---:|---:|---:|
| 0.70 | 95 | 0.914 | 6 | 1 |
| 0.50 | 172 | 0.995 | 16 | 8 |

0.50 模型文件为 `models/electric_bicycle_pseudo05_yolov8n_320_v1.pt`，SHA-256 为 `090b3286a6df558138a18f31191ffd1c17d28d6c470d04777fcc8e5938bb1f27`。告警数量不是准确率；低阈值模型覆盖更高但更可能误报，最终阈值必须用人工事件标注决定。

## 如何复现

```bash
python scripts/open_vocab_detect.py \
  /path/to/local-frames/frames_manifest.csv \
  /tmp/open_vocab_candidates.json \
  --model models/yolov8s-worldv2.pt --device mps --chunk-size 32

python scripts/build_pseudo_labels.py \
  /tmp/open_vocab_candidates.json \
  /tmp/blindnav-pseudo --min-conf 0.70

yolo detect train \
  model=models/yolov8n.pt \
  data=/tmp/blindnav-pseudo/data.yaml \
  imgsz=320 epochs=30 batch=32 device=mps workers=0
```

正式提交前必须用人工框替换伪标签，并在完全未参与标注的本地视频上重新评估。当前模型只适合演示“候选检测到风险反馈”的工程闭环，不应直接作为安全产品模型。
