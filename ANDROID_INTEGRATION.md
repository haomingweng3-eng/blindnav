# 安卓端接入契约（v0.1）

当前仓库没有 Android Studio 工程，因此本文件先冻结 Python 风险引擎与安卓交互层之间的边界。安卓端可以先用固定 JSON 做 UI、震动器和 TTS 的联调，后续再把真实检测器接入。

当前已导出 `models/yolov8n.onnx` 作为端侧候选模型，并通过 ONNX checker 与 CPU 空白帧推理回归；尚未在 Android Runtime、CameraX 或骁龙真机上验证。

## 1. 数据流

```text
检测器/ByteTrack
        ↓
风险引擎
        ↓
alert.feedback
        ↓
Android FeedbackDispatcher
        ├─ Vibrator
        ├─ Tone player
        └─ TextToSpeech
```

安卓端只消费 `feedback`，不需要重新解释 `looming`、框面积或阈值。`info` 主要用于日志和调参，不应直接拿来播报精确距离。

## 2. 告警对象

每个 `alerts[]` 元素包含以下稳定字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `frame` | integer | 源视频帧号 |
| `track_id` | string | ByteTrack 轨迹 ID |
| `cls` | string | `person`、`bicycle`、`motorcycle` 等 |
| `level` | integer | 0 无、1 低、2 警告、3 危险 |
| `level_name` | string | 中文展示名，仅用于日志/UI |
| `info.direction` | string | `left`、`front`、`right` |
| `info.reason` | string | `快速接近`、`横向切入`、`近距离` 等 |
| `feedback` | object/null | 安卓执行的动作；无风险时为 null |

## 3. feedback 字段

```json
{
  "priority": "warning",
  "vibration_ms": [120, 70, 120],
  "tone": "warning",
  "speech": "注意，前方自行车",
  "speech_delay_ms": 250
}
```

约定：

- `vibration_ms` 是交替的振动/静默时长，单位毫秒；首段为振动，之后交替。
- `tone` 只允许 `null`、`warning`、`danger`。音频资源由安卓端自行映射，不把音频文件绑死在算法仓库。
- `speech` 为 null 时不调用 TTS。
- `speech_delay_ms` 是相对本条告警的最早播报延迟，不是定时保证；安卓端应在更高优先级告警到来时取消低优先级语音。
- 同一 `track_id` 的重复告警应由安卓端做去重/节流，建议相同文本 1 秒内最多播报一次。

## 4. 当前三档策略

| 优先级 | 震动 | 音频 | 语音示例 |
|---|---|---|---|
| `low` | `[80]` | 无 | 无 |
| `warning` | `[120,70,120]` | `warning` | `注意，左侧行人` |
| `urgent` | `[260,80,260]` | `danger` | `危险，前方自行车快速接近` |

方向只承诺左侧/前方/右侧三级。当前算法没有相机标定和可靠深度，因此禁止把面积特征转换成“还有 2 米”之类的精确距离。

## 5. 安卓 Dispatcher 伪代码

```text
onAlert(alert):
    feedback = alert.feedback
    if feedback == null:
        return

    if feedback.priority == "urgent":
        cancelPendingSpeechBelow("urgent")

    vibrator.playAlternating(feedback.vibration_ms)

    if feedback.tone != null:
        tonePlayer.play(feedback.tone)

    if feedback.speech != null:
        speechQueue.enqueue(
            text = feedback.speech,
            delayMs = feedback.speech_delay_ms,
            dedupeKey = alert.track_id + ":" + feedback.speech,
            dedupeWindowMs = 1000
        )
```

## 6. 联调样例

使用仓库现有回放样例生成一条完整告警：

```bash
python scripts/replay_detections.py \
  tests/fixtures/synthetic_approach_detections.json \
  -o /tmp/blindnav-risk-report.json
```

安卓端联调时只需读取输出 JSON 的 `alerts[0].feedback`。这个样例的价值是验证字段和动作时序，不代表真实道路准确率。

## 7. 接入前必须复核的参数

- 振动时长是否适合实际手机/腕带/腰带硬件。
- TTS 是否会被导航播报、来电或系统无障碍服务打断。
- 目标手机上的模型推理 FPS、端到端延迟和持续功耗。
- `--input-fps` 是否与采集链路真实时间戳一致；不能用处理 FPS 替代源视频 FPS。

本契约只解决跨模块接口，不替代真实胸挂视角、电动车场景和安卓硬件验证。
