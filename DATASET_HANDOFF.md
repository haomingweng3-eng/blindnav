# 数据集与测试交接单

**面向**：负责拍摄、整理、标注、训练和测试的队友  
**仓库**：`https://github.com/haomingweng3-eng/blindnav`  
**当前基线**：13 段安全距离视频，约 107 秒，均已标记为无冲突基线  
**重要限制**：当前数据没有正向危险事件，因此暂时不能报告真实事件召回率、漏报率或预警提前量。

## 现在已经完成

- Python 检测→ByteTrack 追踪→风险趋势→分级告警→JSON 报告链路已经跑通。
- Android CameraX→ONNX→端侧风险引擎→振动/提示音/TTS 链路已经接通；真机长时间稳定性仍需队友验证。
- 13 段本地视频已进入 `data/raw/`，清单在 `data/collection_manifest.csv`。
- 安全基线上的告警抑制已加入：小目标确认门和方向级普通告警预算。
- 公开 ScooterDet 数据已做过横向验证，但不能替代本地胸挂/胸前视角数据。

## 队友必须完成

### A. 补拍视频

最低再补 20 段，推荐 30 段左右；每段 8–20 秒，横屏、1080p/30 FPS、固定胸前或脖子下方视角，不开滤镜和变焦。

必须覆盖：

- 8–12 段受控 near-miss/conflict：目标会进入或预计进入行走路径，但由队友提前刹停、绕行或让拍摄者停步，禁止真实碰撞；
- 8–10 段看起来接近但安全的反例：目标平行通过、远离或横向离开；
- 4–6 段多目标场景：汽车/电动车/行人同时出现；
- 其余覆盖遮挡、转弯、逆光、不同地点和不同目标速度。

危险不是由“画面里看起来多近”单独决定，而是由以下事实决定：如果双方不改变方向，目标将进入拍摄者的行走路径，且拍摄者或目标必须主动避让。不要在开放道路上故意制造危险。

### B. 做风险事件标注

每段视频都要标注，即使没有事件也要保存空事件数组：

```json
{
  "video_id": "V14",
  "annotation_complete": true,
  "fps": 30,
  "duration_s": 12.0,
  "events": [
    {
      "event_id": "V14-E01",
      "event_type": "near_miss",
      "target_class": "electric_bicycle",
      "start_frame": 90,
      "conflict_frame": 180,
      "notes": "目标预计切入中央行走路径，骑行者提前向右绕行"
    }
  ]
}
```

允许的 `event_type`：`safe_pass`、`near_miss`、`conflict`。目标接近但最后避开，必须标 `near_miss`，不能当作无事件。

生成模板和评估命令：

```bash
python scripts/prepare_annotations.py runs/video_reports/ annotations/
python scripts/batch_evaluate_events.py annotations/ runs/video_reports/ \
  -o runs/video_reports/metrics_summary.json \
  --csv-output runs/video_reports/metrics_summary.csv
```

### C. 建立检测训练集

训练 YOLO 需要给抽取帧画矩形框，类别固定为：

```text
electric_bicycle, person, bicycle, motorcycle
```

推荐抽帧 2–5 FPS，并对接近、横穿、遮挡片段加密抽帧；连续相似帧要去重。模型候选框、伪标签和开放词汇结果只能作为审核建议，不能直接当真值。

训练/验证/测试按视频段划分：

```text
train 60%  | 公开数据 + 一部分本地视频
val   20%  | 完整独立视频，用于调置信度和阈值
test  20%  | 完全不参与训练和调参的本地视频
```

禁止把同一视频的相邻帧拆到 train 和 test，否则结果会虚高。

## 当前风险引擎到底做了什么

当前不是完整的三维轨迹预测。它使用 ByteTrack 轨迹 ID，统计连续检测框的面积增长 `looming`，并把横向速度向前外推约 5 帧，判断是否切入中央图像走廊。它是图像坐标中的短时趋势判断，不是经过相机标定的米制距离、TTC 或地面轨迹预测。

因此，队友不要把 `looming > 0.06` 或框面积 `0.06` 写成现实世界的“几米危险线”。这些是待用正向事件校准的工程初值。

## 验收交付物

队友提交以下内容后才算完成：

1. 新视频和 `data/collection_manifest.csv` 更新；
2. 每段视频对应的事件标注 JSON；
3. 检测框数据集的类别映射和 train/val/test 清单；
4. 训练日志、`best.pt`、权重 SHA-256；
5. 每类 precision、recall、mAP50、mAP50-95；
6. 测试视频预测可视化；
7. 风险评估表：事件召回率、误报告警/分钟、中位/P10 预警提前量；
8. 失败样例和下一步建议；
9. 数据来源、许可和隐私处理说明。

不能用以下内容替代验收：

- 只有视频、没有事件标注；
- 只有伪标签、没有人工抽检；
- 只有训练集 mAP；
- 只展示检测数量增加；
- 把安全视频上的 0 个真实事件误写成 0% 漏报；
- 把公开数据集 benchmark 当成本项目真实道路效果。

## 推荐执行顺序

```text
补拍 near-miss/安全反例
→ 更新 manifest 和事件标注
→ 跑现有 YOLO + ByteTrack 回放
→ 计算误报/召回/提前量
→ 再抽帧画框
→ 公开数据基线微调
→ 本地胸前视角微调
→ 测试集冻结后出最终对比表
```

大视频不要直接反复提交到普通 Git 历史。优先使用 Git LFS 或外部存储，仓库提交清单、哈希、标注、脚本和实验报告。
