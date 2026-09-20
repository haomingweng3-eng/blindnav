# 主线模型训练交接文档

**交接对象**：负责数据整理、标注、训练和评估的队友  
**项目工作区**：`/Users/mima0000/blindnav`  
**主线目标**：胸前/胸挂视角下，识别电动车等动态目标，并为后续追踪和风险预警提供稳定检测框。  
**当前原则**：先把“检测模型”做可信，再接 Android；不要先做地图、SLAM、云端大模型或复杂硬件。

## 1. 先理解当前状态

当前仓库里的 `models/yolov8n.pt` 是 COCO 通用预训练模型，不是本项目训练出的电动车模型。它可以检测 `bicycle`、`motorcycle`、`person` 等通用类别，但不能直接证明它能识别中国道路上的电动车。

目前已有 13 段用户视频，均已保存到 `data/raw/`。这些视频不能简单全部标记为“无风险”：其中可能包含“目标接近但最后避开”的近失事件。需要重新人工复核并区分：

- `safe_pass`：目标出现，但没有进入用户前方风险路径；
- `near_miss`：目标明显接近、横穿或擦身而过，但最后避开；
- `conflict`：目标进入或预计进入用户行走路径，需要预警。

注意：视频事件标注不等于目标检测训练标注。训练 YOLO 仍然需要给目标画矩形框。

## 2. 公开数据和开源项目

### 优先使用：ScooterDet

- 代码仓库：[DongChen06/ScooterDet](https://github.com/DongChen06/ScooterDet)
- 数据集：[Zenodo - Object Detection for E-scooters](https://zenodo.org/records/10578641)
- 许可：下载页面/记录显示为 CC BY 4.0，提交前保留来源和许可证说明。
- 特点：包含 e-scooter 等交通目标，数据来自移动/穿戴式视角，比固定监控和车载视角更接近本项目。
- 限制：不是中国电动车数据，也不是胸挂视角；只能作为公开基础数据，不能替代本地测试。
- 当前测试结论：原生 COCO YOLOv8n 在抽样 ScooterDet 图片上没有稳定识别出 scooter，说明需要微调，不能直接拿原模型做告警。

完整压缩包约 1.1GB，不要提交到 Git 仓库。下载到临时目录后解压，训练产物只保留必要的配置、指标和最终权重。

### 可申请使用：MicroVision

- 项目主页：[MicroVision Dataset](https://microlab-chalmers.github.io/microvision-dataset/)
- 数据访问入口：[Swedish National Data Service](https://researchdata.se/)
- 代码/模型入口：项目主页中的 Code、Hugging Face 和 Dataset 链接。
- 特点：包含 pedestrian、bicycle、cyclist、e-scooter、e-scooterist，面向 VRU/微出行场景。
- 限制：数据需要申请访问；不要把“页面上的 benchmark mAP”写成我们模型的效果，也不要在未确认许可前把数据放进公开仓库。

### 训练框架和标注工具

- Ultralytics 训练文档：[Ultralytics Train Mode](https://docs.ultralytics.com/modes/train/)
- Ultralytics 源码：[ultralytics/ultralytics](https://github.com/ultralytics/ultralytics)
- CVAT 标注工具：[cvat-ai/cvat](https://github.com/cvat-ai/cvat)
- Label Studio 备选：[HumanSignal/label-studio](https://github.com/HumanSignal/label-studio)
- 后续跟踪参考：[ifzhang/ByteTrack](https://github.com/ifzhang/ByteTrack)

训练阶段优先使用 Ultralytics YOLO，原因是当前 Python 检测和 Android ONNX 链路已经以 YOLO 输出为接口。不要同时更换检测框架、类别体系和风险引擎。

## 3. 统一类别定义

第一版只训练 4 类，不要扩展到几十类：

```text
0 electric_bicycle
1 person
2 bicycle
3 motorcycle
```

标注规则：

- `electric_bicycle`：电动自行车、电动车、外卖电动车、带骑手的电动两轮车；
- `bicycle`：明显的人力自行车；
- `motorcycle`：摩托车；
- `person`：行人，以及骑行目标中的人体；如果同一目标同时能清楚看到车和人，两者都标注；
- 被严重遮挡但仍能判断目标存在时，标注可见部分并保持类别一致；
- 不要把“道路”“阴影”“车灯”“树枝”伪装成电动车框；未知障碍物先进入事件/自由空间研究，不混入这版检测器类别。

公开数据类别需要映射到上述四类。无法可靠映射的类别直接丢弃，并在转换日志中记录数量。

## 4. 本地视频如何使用

### 4.1 抽帧

不要把每一帧都拿去训练。建议：

- 普通片段：每 5–10 帧抽 1 帧；
- 目标快速接近、横穿、遮挡和最近距离片段：每 2–5 帧抽 1 帧；
- 连续相似帧去重，避免同一画面重复几百次。

建议保留原始视频，不把抽出的图片和原始视频混合提交到仓库。可以放在本地或外部硬盘，并在仓库提交 `manifest.csv`、类别统计和哈希。

### 4.2 事件复核

每段视频需要填写：

```json
{
  "video_id": "V01",
  "event_id": "V01-E01",
  "event_type": "near_miss",
  "outcome": "avoided",
  "target_class": "electric_bicycle",
  "start_frame": 120,
  "closest_frame": 190,
  "end_frame": 230,
  "path_relation": "crossing"
}
```

`event_type` 只能使用 `safe_pass`、`near_miss`、`conflict`。如果目标接近但最终避开，必须标为 `near_miss`，不能填写空事件。

### 4.3 数据集划分

必须按“视频段”划分，不得按单张图片随机划分：

- `train`：公开数据 + 部分本地视频帧；
- `val`：另一部分完整视频；
- `test`：完全没有参与训练的本地视频，优先放近失事件和复杂视角。

同一个视频的相邻帧不能同时出现在 train 和 test，否则 mAP 会虚高，无法说明胸前视角泛化能力。

## 5. 推荐训练顺序

### 阶段 A：公开数据基线

1. 下载并转换 ScooterDet 为 YOLO 格式。
2. 把类别映射到项目四类；无法映射的类别剔除。
3. 用 `models/yolov8n.pt` 做第一版微调。
4. 保留训练日志、数据集版本、配置、权重 SHA-256。
5. 在 ScooterDet 自己的验证集上输出 precision、recall、mAP50、mAP50-95 和每类指标。

这一步的作用是验证训练流程，不是证明本项目真实场景效果。

仓库已经提供可复现转换器。解压数据后执行：

```bash
python scripts/prepare_scooterdet.py \
  /path/to/Mixed \
  /path/to/prepared-scooterdet \
  --max-gap 10 --seed 20260919
```

脚本会生成 `data.yaml`、`split_manifest.csv` 和 `summary.json`。划分单位是连续帧组，而不是单张图片；最大的电动车连续组保留在训练集，验证集和测试集各保留独立电动车组。

### 阶段 B：加入本地胸前视角

1. 从本地视频抽帧并人工画框。
2. 公开数据和本地数据保持同一类别定义。
3. 先使用公开数据训练出的权重，再用本地训练集微调。
4. 用本地验证集调置信度阈值，不要用测试集调参。
5. 最后只在本地测试视频上评估。

本地视频可以先按固定间隔抽成待标注帧：

```bash
python scripts/extract_video_frames.py \
  data/raw /path/to/local-frames --stride 5
```

输出的 `frames_manifest.csv` 中所有图片初始状态都是 `unlabeled`。只有完成人工框标注后才能加入检测训练集；抽帧工具不会生成伪标签。

如果人工筛选量较大，可以用开放词汇模型先生成待审核候选框：

```bash
python scripts/open_vocab_detect.py \
  /path/to/local-frames/frames_manifest.csv \
  /path/to/local-frames/open_vocab_candidates.json \
  --model models/yolov8s-worldv2.pt \
  --device mps --chunk-size 32 \
  --classes moped electric\ bicycle electric\ scooter
```

输出中的 `candidate_review` 只是候选状态，不能直接转成 YOLO 标签；需要人工确认类别和矩形框后再进入训练集。开放词汇模型只作为标注加速器和横向对照，不作为当前 Android 安全告警模型。

如果需要先验证本地视角适配流程，可以运行 `scripts/build_pseudo_labels.py` 生成明确标记为 `pseudo_candidate_review_required` 的单类实验集，再训练 `models/electric_bicycle_pseudo_yolov8n_320_v1.pt` 的同类学生模型。该实验已归档在 `experiments/pseudo_moped_adaptation/`，只能证明蒸馏流程和工程闭环，不能替代人工标注验收。

### 4.4 本地人工审核页面

仓库提供零依赖的浏览器审核工具。它会显示模型候选框，允许人工补框、选择类别和填写事件类型，并把结果保存为 JSON：

```bash
python scripts/label_review_server.py \
  /path/to/local-frames/frames_manifest.csv \
  --frames-root /path/to/local-frames \
  --candidates /path/to/open_vocab_candidates.json \
  --only-candidates \
  --output /path/to/local-frames/local_review.json
```

浏览器打开 `http://127.0.0.1:8765/`。黄色框是候选框，红色框是人工框；右键可清空当前人工框。`near_miss` 表示接近但最后避开，`conflict` 表示进入或预计进入行走路径。只有审核完成后，才能把人工框转换为正式 YOLO 标签；`candidate_review` 和伪标签都不能直接当真值。

审核完成后转换为四类 YOLO 数据集：

```bash
python scripts/review_to_yolo.py \
  /path/to/local-frames/local_review.json \
  /path/to/local-reviewed-yolo
```

转换器会按视频段重新划分 train/val/test，避免相邻视频帧泄漏，并保留事件类型到 `manifest.csv`。

为了先快速建立人工复核集，可从 13 段视频各均匀抽取 20 帧：

```bash
python scripts/select_review_frames.py \
  /path/to/local-frames/frames_manifest.csv \
  /path/to/local-frames/review_manifest.csv \
  --max-per-video 20
```

这只生成审核清单，不生成标签。审核人必须在 `review_manifest.csv` 对应图片上补充目标框，并另行填写事件 JSON；均匀抽样不能替代对接近、横穿和遮挡片段的加密抽帧。

### 阶段 C：与风险引擎联调

训练模型只负责输出稳定检测框。不要在训练阶段修改 `scripts/risk_engine.py` 的阈值来掩盖漏检。

联调顺序：

```text
检测框 → ByteTrack → looming/横向趋势 → near_miss 事件评估 → 分级告警
```

如果模型没有输出目标框，应该记为检测漏检；不能通过给风险引擎手工喂框来宣称模型识别成功。

## 6. 推荐命令和交付物

训练命令以实际转换后的 `data.yaml` 为准，示例：

```bash
cd /Users/mima0000/blindnav
conda activate pt

yolo detect train \
  model=models/yolov8n.pt \
  data=/path/to/electric_bicycle.yaml \
  imgsz=640 \
  epochs=80 \
  batch=-1 \
  device=mps \
  project=runs \
  name=electric_bicycle_yolov8n_v1
```

若显存、内存或训练时间不足，先把 `epochs` 改为 30 做流程验证，不要把流程验证结果当最终效果。

队友必须交付：

1. 数据转换脚本或可复现转换步骤；
2. `data.yaml` 和类别映射表；
3. 训练/验证/测试视频清单；
4. 数据量统计：图片数、每类框数、每段视频事件数；
5. `results.csv` 或等价训练日志；
6. `best.pt` 和 SHA-256；
7. 测试集预测可视化；
8. 测试报告：每类 precision、recall、mAP，以及近失事件的首个告警帧和提前量；
9. 对当前 `yolov8n.pt` 和新模型的对比表；
10. 许可和数据来源说明。

## 7. 验收标准

第一阶段不设虚假的“准确率必须 95%”。先满足可复现性：

- 能从干净环境重新生成数据集配置；
- 训练命令可以运行并保存权重；
- 测试集与训练视频完全隔离；
- 每一类至少有明确的样本数和指标；
- 对本地胸前视角测试视频能输出预测可视化；
- 能分别报告“检测漏检”和“风险引擎未升级”；
- 不能把公开数据集指标写成中国道路真实效果；
- 不能把用户确认“避开”的视频标成无事件后再宣称零漏报。

建议的最低工程门槛是：本地测试集上电动车目标能够稳定输出检测框，并且比原始 COCO YOLOv8n 在同一测试集上有明确改善。若没有改善，应保留失败报告，不要覆盖基线模型。

## 8. 当前不要做的事

- 不要覆盖 `models/yolov8n.pt`；
- 不要把训练权重直接放进 Android，除非通过桌面端测试和 ONNX 导出验证；
- 不要把相邻视频帧随机拆到 train/test；
- 不要把未画框的视频帧直接当检测训练数据；
- 不要为了提高指标删除困难样本；
- 不要在没有许可核验时提交公开数据原图；
- 不要把“模型检测数量增加”当成“安全性提高”。

## 9. 本项目现有相关文件

- `PROJECT_STATUS.md`：项目总状态和当前证据边界；
- `EXTERNAL_DATASET_TEST.md`：此前 ScooterDet 抽样和小样本微调失败记录；
- `DATA_COLLECTION.md`：视频采集规范；
- `VIDEO_ARCHIVE.md`：已归档视频和哈希；
- `scripts/detect_video.py`：视频检测、ByteTrack 和风险报告；
- `scripts/prepare_annotations.py`：生成事件标注模板；
- `scripts/evaluate_events.py`：事件召回率、误报和提前量评估；
- `scripts/batch_evaluate_events.py`：批量汇总；
- `models/README.md`：当前基线模型和许可提醒。

队友完成训练后，应把结果路径、指标、失败原因和下一步建议补充到本文件末尾或新建 `runs/<experiment>/README.md`，不要只发送一个没有说明的 `best.pt`。
