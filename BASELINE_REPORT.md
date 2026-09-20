# BlindNav ScooterDet YOLOv8n 可复现基线报告

**日期**：2026-09-20  
**状态**：公开数据训练流程已完成；模型不可用于真实安全告警  
**实验目录**：`experiments/scooterdet_yolov8n_320_v1/`

## 目标

使用公开 ScooterDet 数据验证四类标签转换、连续帧无泄漏划分、YOLOv8n 微调和独立测试的完整流程。四类为：

```text
electric_bicycle
person
bicycle
motorcycle
```

本实验是公开数据基线，不代表中国道路、胸前视角或近失事件效果。

## 数据来源和许可

- 数据：[Zenodo - Object Detection for E-scooters](https://zenodo.org/records/10578641)
- 代码参考：[DongChen06/ScooterDet](https://github.com/DongChen06/ScooterDet)
- Zenodo 记录的许可：CC BY 4.0
- 原始文件：2013 张 JPG、2013 个 LabelMe JSON
- 原始压缩包约 1.0GB，不进入本仓库

仓库脚本 `scripts/prepare_scooterdet.py` 将 `scooter` 映射为 `electric_bicycle`，保留 `person`、`bicycle`、`motorcycle`，其他类别作为无目标背景。连续数字帧间隔不超过 10 的图片视为同一帧组，同组不会跨 train/val/test。

## 划分结果

| split | 图片 | electric_bicycle | person | bicycle | motorcycle |
|---|---:|---:|---:|---:|---:|
| train | 1611 | 37 | 981 | 83 | 7 |
| val | 201 | 6 | 157 | 13 | 0 |
| test | 201 | 6 | 134 | 2 | 29 |
| 合计 | 2013 | 49 | 1272 | 98 | 36 |

共 79 个连续帧组。划分检查显示 0 个组跨 split。最大的电动车连续组保留在训练集，val/test 各保留独立电动车组。完整清单见 `experiments/scooterdet_yolov8n_320_v1/split_manifest.csv`。

## 训练配置

- 初始权重：`models/yolov8n.pt`
- 输入：320×320
- epochs：30
- batch：32
- 设备：Apple M1 MPS
- Ultralytics：8.4.152
- seed：20260919
- `deterministic=True`，但 PyTorch 明确警告部分 MPS 算子没有确定性实现，因此不能宣称跨设备逐位复现
- 训练耗时：0.431 小时
- 最佳 epoch：30（按验证集 mAP50-95）

最初尝试 640×640、batch 16，实测单个 epoch 预计约 4 分钟，已中止且不作为结果。320×320 是本机可完成的流程基线，不是最终部署分辨率选择。

## 验证集结果

最佳权重在 val 上：

- Precision：0.172
- Recall：0.102
- mAP50：0.130
- mAP50-95：0.046

## 独立测试集结果

| 类别 | Precision | Recall | mAP50 | mAP50-95 |
|---|---:|---:|---:|---:|
| 全部 | 0.6553 | 0.0728 | 0.0920 | 0.0330 |
| electric_bicycle | 1.0000* | 0.0000 | 0.0075 | 0.0023 |
| person | 0.6213 | 0.2910 | 0.3305 | 0.1244 |
| bicycle | 0.0000 | 0.0000 | 0.0038 | 0.0004 |
| motorcycle | 1.0000* | 0.0000 | 0.0261 | 0.0052 |

`*`：当默认评估阈值下没有有效预测时，Ultralytics 返回的插值 precision 可能显示为 1.0；必须结合 Recall=0 和预测数量理解，不能解释为类别识别正确。

测试集共有 171 个四类真值框，其中电动车 6 个。电动车 Recall=0，因此本模型不能进入风险告警主链。

## 阈值检查

在 201 张 test 图片上：

- `conf=0.25`：person 52 框、bicycle 1 框；electric_bicycle 和 motorcycle 为 0；
- `conf=0.05`：electric_bicycle 8 框、person 211 框、bicycle 20 框；
- `conf=0.05` 的电动车预测出现在 6 张图片中，与 5 张含电动车真值的图片交集为 0。

因此降低置信度只增加了电动车误报，没有解决真实电动车漏检。

## 模型产物

- 文件：`models/scooterdet_yolov8n_320_v1.pt`
- SHA-256：`0ee4a96a0752f3351239dc7d98ada4186261a5dcbfff4e59a822420851394e60`
- 作用：训练管线基线和后续微调起点
- 禁止表述：不能称为“电动车检测模型已完成”或“可用于安全预警”

训练曲线、混淆矩阵、测试预测样例和原始 `results.csv` 已放在实验目录。模型继承 Ultralytics 权重和代码许可风险，公开、比赛和产品化仍需分别复核。

## 本地视频进度

仓库 13 段视频已按每 5 帧抽取 1 帧，共得到 658 张待标注图片，临时目录为 `/tmp/blindnav-external/local-frames/`。抽帧工具是 `scripts/extract_video_frames.py`。

这些帧目前状态是 `unlabeled`，不能直接加入检测训练。下一步必须人工画框，并重新复核 `safe_pass`、`near_miss`、`conflict` 事件；“接近但最后避开”应标为 `near_miss`。

## 结论

已经完成并验证：公开数据下载、四类转换、连续帧组划分、训练、独立测试、阈值检查、权重和可视化归档。

尚未完成且不能绕过：本地胸前视角目标框标注。公开集总共只有 49 个电动车框，无法支撑可靠检测；继续增加公开集 epochs 的收益有限。真实主线下一步是给 658 张候选帧筛选并标注电动车/人/自行车/摩托车，再以本模型作为微调起点，并在整段未参与训练的本地视频上复测。
