# 安卓端接入契约（v0.1）

当前仓库没有 Android Studio 工程，因此本文件先冻结 Python 风险引擎与安卓交互层之间的边界。安卓端可以先用固定 JSON 做 UI、震动器和 TTS 的联调，后续再把真实检测器接入。

当前已导出 `models/yolov8n.onnx` 作为端侧候选模型，并通过 ONNX checker 与 CPU 空白帧推理回归；尚未在 Android Runtime、CameraX 或骁龙真机上验证。

Python 参考适配器位于 `scripts/onnx_inference.py`，冻结了 letterbox、RGB/CHW/归一化、YOLOv8 输出解码和按类别 NMS 的行为。Android 端移植时应先用同一张输入图对比框坐标和类别，再接入风险引擎；该适配器不是 Android API 实现。

模型推理层基准命令为 `python scripts/benchmark_onnx.py models/yolov8n.onnx`。它只测 ONNX Runtime，不代表 CameraX→检测→追踪→反馈的端到端延迟。

## 1. 设备形态与降级原则

本项目允许两种输入形态，但作品主体始终是 Android 端侧软件：

1. **默认形态**：Android 手机摄像头直接采集并在本机推理，现场无需外接硬件即可演示。
2. **增强形态**：胸挂式独立摄像头作为可选视觉传感器节点，把带时间戳的视频帧传给手机；节点不承担主要风险判断，也不依赖云端。

外接摄像头断连、延迟异常或丢帧时，系统必须能回退到手机摄像头或明确进入“感知不可用”状态，不能继续输出看似正常的安全告警。这样既保留胸挂视角的产品价值，也不会把作品变成只有硬件才能运行的装置。

## 2. 数据流

```text
手机摄像头 或 胸挂传感器节点
        ↓ 帧号/时间戳/图像
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

### 2.1 传感器节点最小数据契约

传感器节点第一版只需要传输视频，不在节点上实现检测或风险决策。每帧至少记录：

| 字段 | 类型 | 说明 |
|---|---|---|
| `source` | string | `phone_camera` 或 `external_camera` |
| `source_frame` | integer | 传感器原始帧号，不能用处理序号代替 |
| `capture_ts_ms` | integer | 采集时间戳，单调递增 |
| `width` / `height` | integer | 原始图像尺寸 |
| `transport` | string | `camera2`、`usb`、`wifi` 等 |
| `dropped_since_last` | integer | 自上帧以来丢失的帧数 |

约束：

- 风险引擎使用 `capture_ts_ms` 或源帧率计算时间间隔，不能使用手机处理 FPS。
- 时间戳倒退、帧号倒退或连续丢帧超过阈值时，清空旧轨迹并记录 `sensor_degraded`。
- 外接节点只提供感知输入，不输出“安全”“可过街”等结论。
- 传输链路先做可替换接口，USB/Wi-Fi 的选择不写死在风险引擎里。

## 3. 告警对象

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

## 4. feedback 字段

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

## 5. 当前三档策略

| 优先级 | 震动 | 音频 | 语音示例 |
|---|---|---|---|
| `low` | `[80]` | 无 | 无 |
| `warning` | `[120,70,120]` | `warning` | `注意，左侧行人` |
| `urgent` | `[260,80,260]` | `danger` | `危险，前方自行车快速接近` |

方向只承诺左侧/前方/右侧三级。当前算法没有相机标定和可靠深度，因此禁止把面积特征转换成“还有 2 米”之类的精确距离。

## 6. 安卓 Dispatcher 伪代码

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

## 7. 联调样例

使用仓库现有回放样例生成一条完整告警：

```bash
python scripts/replay_detections.py \
  tests/fixtures/synthetic_approach_detections.json \
  -o /tmp/blindnav-risk-report.json
```

安卓端联调时只需读取输出 JSON 的 `alerts[0].feedback`。这个样例的价值是验证字段和动作时序，不代表真实道路准确率。

## 8. 接入前必须复核的参数

- 振动时长是否适合实际手机/腕带/腰带硬件。
- TTS 是否会被导航播报、来电或系统无障碍服务打断。
- 目标手机上的模型推理 FPS、端到端延迟和持续功耗。
- `--input-fps` 是否与采集链路真实时间戳一致；不能用处理 FPS 替代源视频 FPS。

本契约只解决跨模块接口，不替代真实胸挂视角、电动车场景和安卓硬件验证。
