# 事件标注目录

这里保存与风险报告同名的事件标注 JSON。原始视频仍放在 `data/raw/`，不要把没有脱敏或没有授权的原始视频提交到仓库。

## 单段视频标注格式

文件名应与报告同名，例如：

```text
annotations/V01.json
runs/video_reports/V01.json
```

内容示例：

```json
{
  "video_id": "V01",
  "fps": 30,
  "duration_s": 30,
  "events": [
    {
      "event_id": "V01-E01",
      "start_frame": 120,
      "conflict_frame": 240,
      "target_class": "bicycle",
      "notes": "迎面接近，进入中央走廊"
    }
  ]
}
```

字段约定：

- `start_frame`：目标进入评估范围的帧，不是视频第一帧。
- `conflict_frame`：人工判断最晚仍应预警的帧；提前量为 `(conflict_frame - 首个有效告警帧) / fps`。
- `target_class`：使用报告里的类别名；不确定时可写 `null` 或 `any`，但应在 `notes` 说明原因。
- 没有风险事件的视频保留空数组 `"events": []`，不能省略文件。

批量评估：

```bash
python scripts/batch_evaluate_events.py \
  annotations/ runs/video_reports/ \
  -o runs/video_reports/metrics_summary.json
```
