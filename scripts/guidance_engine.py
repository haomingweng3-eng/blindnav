"""Local walk guidance and route-conflict state machine.

This is the desktop reference implementation for the phone guidance contract.
It intentionally uses a conservative geometric free-space fallback until a
learned walkable-region model is supplied. It does not claim metric distance.
"""

from dataclasses import dataclass


KEEP_STRAIGHT = "KEEP_STRAIGHT"
MOVE_LEFT = "MOVE_LEFT"
MOVE_RIGHT = "MOVE_RIGHT"
STOP = "STOP"
CAUTION = "CAUTION"
DANGER = "DANGER"
UNKNOWN_SLOW_DOWN = "UNKNOWN_SLOW_DOWN"


@dataclass(frozen=True)
class WalkableRegion:
    left: float = 0.32
    right: float = 0.68
    floor_y: float = 0.48
    confidence: float = 0.55
    source: str = "geometry_fallback"

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x <= self.right and y >= self.floor_y


@dataclass(frozen=True)
class GuidanceDecision:
    state: str
    reason: str
    confidence: float
    speech: str


class GuidanceEngine:
    def __init__(self, repeat_frames=75, min_confidence=0.25):
        if repeat_frames < 1:
            raise ValueError("repeat_frames must be positive")
        self.repeat_frames = int(repeat_frames)
        self.min_confidence = float(min_confidence)
        self.last_frame = None
        self.blocking_streak = 0
        self.last_state = None
        self.last_emit_frame = -10**9
        self.history = {}

    def update(self, frame, records, region=None, uncertain=False):
        region = region or WalkableRegion()
        consecutive = self.last_frame is None or frame == self.last_frame + 1
        blockers = []
        for record in records:
            box = record.get("box") or []
            if len(box) != 4 or float(record.get("conf", 0.0)) < self.min_confidence:
                continue
            width = max(float(record.get("width", 1.0)), 1.0)
            height = max(float(record.get("height", 1.0)), 1.0)
            x = (float(box[0]) + float(box[2])) / 2.0 / width
            y = float(box[3]) / height
            area = max(float(box[2]) - float(box[0]), 0.0) * max(float(box[3]) - float(box[1]), 0.0) / (width * height)
            if region.contains(x, y):
                blockers.append((record, x, y, area))
            tid = str(record.get("track_id", "unknown"))
            self.history.setdefault(tid, []).append((frame, area, x, y))
            self.history[tid] = self.history[tid][-6:]

        self.blocking_streak = (
            self.blocking_streak + 1 if blockers and consecutive else 1 if blockers else 0
        )
        self.last_frame = frame
        approaching = any(self._approaching(record) for record, _, _, _ in blockers)
        large = any(area >= 0.06 for _, _, _, area in blockers)
        if uncertain:
            decision = GuidanceDecision(UNKNOWN_SLOW_DOWN, "可行走区域不确定", 0.25, "前方情况不明，请减速")
        elif blockers and self.blocking_streak >= 2 and (approaching or large):
            decision = GuidanceDecision(STOP, "路线内持续接近", 0.9, "停止，前方有危险")
        elif blockers and self.blocking_streak >= 2:
            decision = GuidanceDecision(CAUTION, "目标可能进入行走路线", 0.75, "注意，前方可能有障碍")
        elif blockers:
            direction = self._open_direction(blockers, region)
            if direction == MOVE_LEFT:
                decision = GuidanceDecision(MOVE_LEFT, "右侧空间更受阻", region.confidence, "向左绕行")
            elif direction == MOVE_RIGHT:
                decision = GuidanceDecision(MOVE_RIGHT, "左侧空间更受阻", region.confidence, "向右绕行")
            else:
                decision = GuidanceDecision(CAUTION, "前方目标进入路线", 0.65, "注意，前方目标")
        elif region.confidence < 0.35:
            decision = GuidanceDecision(UNKNOWN_SLOW_DOWN, "可行走区域不确定", region.confidence, "前方情况不明，请减速")
        else:
            decision = GuidanceDecision(KEEP_STRAIGHT, "中央路线可通行", region.confidence, "保持直行")
        return decision

    def should_emit(self, decision, frame):
        if decision.state != self.last_state or frame - self.last_emit_frame >= self.repeat_frames:
            self.last_state = decision.state
            self.last_emit_frame = frame
            return True
        return False

    def _approaching(self, record):
        history = self.history.get(str(record.get("track_id", "unknown")), [])
        if len(history) < 2:
            return False
        return history[-1][1] >= history[-2][1] * 1.04

    @staticmethod
    def _open_direction(blockers, region):
        left_cost = 0.0
        right_cost = 0.0
        for record, x, _, _ in blockers:
            conf = float(record.get("conf", 0.0))
            x1, x2 = x - 0.12, x + 0.12
            left_cost += max(0.0, min(x2, 0.40) - max(x1, 0.12)) * conf
            right_cost += max(0.0, min(x2, 0.88) - max(x1, 0.60)) * conf
        if left_cost + 0.04 < right_cost:
            return MOVE_LEFT
        if right_cost + 0.04 < left_cost:
            return MOVE_RIGHT
        return STOP


def evaluate_guidance_records(records, width, height, uncertain=False):
    """Evaluate frame records and return a serializable guidance trace."""
    engine = GuidanceEngine()
    by_frame = {}
    for record in records:
        item = dict(record)
        item["width"] = width
        item["height"] = height
        by_frame.setdefault(int(record["frame"]), []).append(item)
    trace = []
    counts = {}
    for frame in sorted(by_frame):
        decision = engine.update(frame, by_frame[frame], uncertain=uncertain)
        emitted = engine.should_emit(decision, frame)
        counts[decision.state] = counts.get(decision.state, 0) + 1
        trace.append({
            "frame": frame,
            "state": decision.state,
            "reason": decision.reason,
            "confidence": round(decision.confidence, 3),
            "speech": decision.speech if emitted else None,
        })
    return {"trace": trace, "state_counts": counts}
