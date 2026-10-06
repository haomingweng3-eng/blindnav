# Baseline retrain report

日期：2026-10-07

## 训练配置

- 数据：`data/phone_camera_202609_reviewed/data.yaml`
- 初始权重：`models/yolov8n.pt`
- 输出：`runs/train/phone_camera_202609_baseline_retrain_20261007/`
- 轮数：50
- 输入：640
- batch：16
- device：RTX 4060 (`device=0`)
- workers：0
- 未使用候选扫描结果，未修改测试集

## 结果

- 验证集：13 张、38 个框；mAP50 `0.303`，mAP50-95 `0.0859`
- 固定测试集：11 张、31 个框；总体 mAP50 `0.185`，mAP50-95 `0.0464`
- 测试集 electric_bicycle：Precision `0.326`，Recall `0.423`，mAP50 `0.370`
- 测试集 car：当前只有 1 张图、5 个框，未检出

## 数据限制

训练框分布为：train `electric_bicycle=283, person=8, car=5`；val 全部为 `electric_bicycle=38`；test `electric_bicycle=26, car=5`。`bicycle` 和 `motorcycle` 在正式框标注中没有训练样本，不能据此评价这两个类别。

## 文件校验

- `args.yaml`：`runs/train/phone_camera_202609_baseline_retrain_20261007/args.yaml`
- `results.csv`：`runs/train/phone_camera_202609_baseline_retrain_20261007/results.csv`
- `best.pt` SHA256：`E5C35D4EB1418E65EB3892D9645969839286C01BB077887427F41F078C129803`

结论：训练流程成功，但固定测试集表现仍不足以接入手机安全预警；下一步应补充并确认真实手机视角框，尤其是自行车/摩托车和路线冲突样本。
