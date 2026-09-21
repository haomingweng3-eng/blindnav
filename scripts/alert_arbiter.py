"""将风险引擎告警转换为可播放的、低打扰反馈事件。"""


class AlertArbiter:
    """按目标和方向合并重复告警，同时允许风险升级打断冷却。

    普通告警使用“方向通道”而不是“类别+方向通道”：同一方向在短窗口内只播
    一次普通提示，避免远处多目标在连续帧中造成语音/震动刷屏。紧急告警不走
    方向合并，仍可立即抢占普通告警。
    """

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
        # 反馈预算按方向分配，而不是按类别分配。这样同一方向上的汽车、
        # 行人和两轮车不会各自占用一个播报通道。仍保留同一帧的多个目标，
        # 因为它们可能代表真实的并行风险；只合并后续帧的普通警告。
        channel_key = (str(direction), level)
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
