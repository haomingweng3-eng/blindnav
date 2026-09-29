# 独立测试候选帧复核结果

## 协作元信息

- sender: 标注模块
- receiver: 技术协调者（Codex）
- sent_at: 2026-09-30T18:35:00+08:00
- source: `main` commit `c430e81`; `data/phone_camera_202609_reviewed/`; `data/labels/phone_camera_202609_video_labels.csv`; 两段原始视频及其相邻帧复核
- type: 独立测试候选帧人工复核反馈
- status: ready_for_review
- changed: 新增本反馈文件；未修改原始视频、模型、训练集划分和已有 YOLO 标签
- next: 技术协调者确认后，将类别结论用于独立测试记录；路线冲突/安全事件另行人工确认，不直接从本次类别结论推导

## 复核结论

本次任务的四类输出为：`confirmed_electric_bicycle`、`confirmed_car`、`no_target`、`human_annotation_required`。

| 候选帧 | 相邻帧证据 | 目标类别结论 | 类别置信度 | 路线/事件备注 |
|---|---|---|---|---|
| `data/phone_camera_202609_reviewed/images/test/VID_20260917_153727_frame_000331.jpg` | 回放原视频第 320、331、342 帧：同一目标连续出现在道路中央，能看到骑行者、车把和前篮，目标形态保持一致 | `confirmed_electric_bicycle` | 高 | `data/labels/phone_camera_202609_video_labels.csv` 将该视频记为 `safe`，备注为目标向右侧通过、未进入行走路线；但 `manifest.csv` 将该测试帧写为 `conflict`。这是事件语义冲突，不能改变目标类别结论，路线事件应单独复核 |
| `data/phone_camera_202609_reviewed/images/test/VID_20260922_170525_frame_000001.jpg` | 回放原视频第 0、10、20 帧：同一目标在道路中线附近连续出现并逐步接近，形态为骑行者驾驶小型电动两轮车 | `confirmed_electric_bicycle` | 高 | 视频级标注为 `conflict`，约在 3.0 秒进入受控冲突；第 1 帧属于起始阶段，仅用于确认类别，不单独作为冲突发生帧 |

## 汇总

- `confirmed_electric_bicycle`: 2 帧
- `confirmed_car`: 0 帧
- `no_target`: 0 帧
- `human_annotation_required`: 0 帧（仅就目标类别而言）
- 事件级需要继续人工确认：1 个语义冲突，即 `VID_20260917_153727` 的 `manifest.csv` 与视频级标签对路线事件的描述不一致。

## 对训练和评估的约束

1. 本反馈只确认“画面中是什么目标”，不把 `safe`、`near_miss`、`conflict` 当作目标类别。
2. `VID_20260917_153727_frame_000331.jpg` 不应仅凭 `manifest.csv` 的 `conflict` 字段认定为冲突真值；应根据整段视频的路线关系和人工事件标注单独裁决。
3. `VID_20260922_170525_frame_000001.jpg` 可作为电动车类别的独立测试样本，但不能用该起始帧单独计算冲突召回、预警提前量或 TTC 正确性。
4. 本次未执行训练，未将候选帧自动写入训练集，也未把空的 YOLO 标签文件自动填成伪标签。
