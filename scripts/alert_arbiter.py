"""将风险引擎告警转换为可播放的、低打扰反馈事件。"""


class AlertArbiter:
    """按目标、类别和方向合并重复告警，同时允许风险升级打断冷却。"""

    def __init__(self, cooldown_frames=30, channel_cooldown_frames=15):
        if not isinstance(cooldown_frames, int) or cooldown_frames < 0:
            raise ValueError("cooldown_frames must be a non-negative integer")
        if (
            not isinstance(channel_cooldown_frames, int)
            or channel_cooldown_frames < 0
        ):
            raise ValueError("channel_cooldown_frames must be a non-negative integer")
        self.cooldown_frames = cooldown_frames
        self.channel_cooldown_frames = channel_cooldown_frames
        self._last_accepted = {}
        self._last_channel_accepted = {}

    @staticmethod
    def _key(alert):
        info = alert.get("info") or {}
        direction = alert.get("direction", info.get("direction", "front"))
        return (
            str(alert.get("track_id", "unknown")),
            str(alert.get("cls", "unknown")),
            str(direction),
        )

    def accept(self, alert):
        """返回是否应将一条风险告警交给反馈层。"""
        frame = alert.get("frame")
        level = alert.get("level", 0)
        if not isinstance(frame, int) or not isinstance(level, int):
            raise ValueError("alert frame and level must be integers")

        key = self._key(alert)
        previous = self._last_accepted.get(key)
        if previous is not None:
            previous_frame, previous_level = previous
            upgraded = level > previous_level
            within_cooldown = frame - previous_frame < self.cooldown_frames
            if within_cooldown and not upgraded:
                return False

        info = alert.get("info") or {}
        direction = alert.get("direction", info.get("direction", "front"))
        channel_key = (str(alert.get("cls", "unknown")), str(direction), level)
        # 同一帧可能确实存在多个目标；只合并后续帧的普通警告。
        if level < 3:
            previous_channel_frame = self._last_channel_accepted.get(channel_key)
            if (
                previous_channel_frame is not None
                and frame != previous_channel_frame
                and frame - previous_channel_frame < self.channel_cooldown_frames
            ):
                return False

        self._last_accepted[key] = (frame, level)
        if level < 3:
            self._last_channel_accepted[channel_key] = frame
        return True

    def filter(self, alerts):
        """按帧顺序筛选告警，返回新列表，不修改输入。"""
        accepted = []
        for alert in sorted(alerts, key=lambda item: item.get("frame", 0)):
            if self.accept(alert):
                accepted.append(alert)
        return accepted
