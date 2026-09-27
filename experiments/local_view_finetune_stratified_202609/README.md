# 本地视角微调实验（2026-09-28）

## 目的

验证人工修正的手机视角标注能否让通用 YOLOv8n 适应本项目的电动车画面。该实验只用于判断数据和训练流程，不能作为最终安全模型。

## 数据

- 来源：`runs/annotations_202609.json`
- 图片：84 张，来自 22 段视频
- 类别：`electric_bicycle`、`person`、`bicycle`、`motorcycle`、`car`
- 电动车框：18 个
- 按视频划分，电动车至少出现在 train/val/test 三个 split；实际为 train 9、val 1、test 8 个框
- 数据目录：`runs/manual_dataset_202609_stratified/`

## 配置

- 初始权重：`models/yolov8n.pt`
- 输入尺寸：320×320
- epochs：20
- batch：8
- 设备：Apple MPS
- seed：20260928
- 输出权重：`runs/detect/runs/local_view_finetune_stratified_202609/weights/best.pt`

## 测试结果

在独立 test split（19 张图、22 个标注框）上：

- Precision：0.0144
- Recall：0.3571
- mAP50：0.0291
- mAP50-95：0.0118
- 电动车 mAP50：0（当前样本量下没有稳定命中）

## 对照结果

现有 ScooterDet 四类权重在这批本地人工框上，默认置信度 0.25 时电动车命中为 0/18；说明公开视角与手机胸前视角存在明显域差异。伪标签电动车模型在置信度 0.05 时产生 110 个候选、只命中 1/18，不能直接作为告警模型。

## 结论

当前不能把这次权重接入 Android 或宣称电动车识别完成。下一步必须继续增加本地视角电动车标注，尤其是正面接近、侧向切入、远处小目标、被遮挡后重新出现四类画面；建议至少达到 100 个以上电动车实例，再重新训练并在未参与训练的整段视频上评估轨迹冲突。
