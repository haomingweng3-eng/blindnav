"""把风险等级转换成平台无关的震动、提示音和语音动作。"""

try:
    from .risk_engine import LVL_HIGH, LVL_LOW, LVL_MID, LVL_NONE
except ImportError:  # 支持直接用 PYTHONPATH=scripts 执行
    from risk_engine import LVL_HIGH, LVL_LOW, LVL_MID, LVL_NONE


CLASS_NAMES = {
    "person": "行人",
    "bicycle": "自行车",
    "scooter": "电动滑板车",
    "electric_bicycle": "电动车",
    "electric_bike": "电动车",
    "e-bike": "电动车",
    "electric bicycle": "电动车",
    "motorcycle": "摩托车",
    "car": "汽车",
    "bus": "公交车",
    "truck": "卡车",
}

DIRECTION_NAMES = {"left": "左侧", "front": "前方", "right": "右侧"}


def feedback_for(level, cls, info):
    """返回 Android 等上层交互可消费的反馈描述；无风险返回 None。"""
    if level == LVL_NONE:
        return None

    target = CLASS_NAMES.get(cls, cls)
    target_phrase = f"{DIRECTION_NAMES.get(info.get('direction'), '')}{target}"
    reason = info.get("reason", "")
    if level == LVL_LOW:
        return {
            "priority": "low",
            "vibration_ms": [80],
            "tone": None,
            "speech": None,
            "speech_delay_ms": None,
        }

    if level == LVL_MID:
        return {
            "priority": "warning",
            "vibration_ms": [120, 70, 120],
            "tone": "warning",
            "speech": f"注意，{target_phrase}",
            "speech_delay_ms": 250,
        }

    if level == LVL_HIGH:
        approach = "快速接近" if "快速接近" in reason else "近距离高风险"
        return {
            "priority": "urgent",
            "vibration_ms": [260, 80, 260],
            "tone": "danger",
            "speech": f"危险，{target_phrase}{approach}",
            "speech_delay_ms": 100,
        }

    raise ValueError(f"unknown risk level: {level}")
