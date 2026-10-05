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
CLOSE_ROUTE_AREA = 0.04


@dataclass(frozen=True)
class WalkableRegion:
    left: float = 0.36
    right: float = 0.64
    floor_y: float = 0.48
    confidence: float = 0.55
    source: str = "geometry_fallback"
    surface: str = "unknown"

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
        self.last_warning_emit_frame = -10**9
        self.last_warning_rank = 0
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
        close_blocker = any(area >= CLOSE_ROUTE_AREA for _, _, _, area in blockers)
        if uncertain:
            decision = GuidanceDecision(UNKNOWN_SLOW_DOWN, "可行走区域不确定", 0.25, "前方情况不明，请减速")
        # A large box alone is not evidence of an incoming collision: a
        # parked vehicle can remain large for the whole clip.  STOP requires
        # temporal approach evidence (or the Android risk engine's urgent
        # alert, which is handled by the phone-side GuidanceEngine).
        elif blockers and self.blocking_streak >= 2 and approaching and close_blocker:
            decision = GuidanceDecision(STOP, "路线内持续接近", 0.9, "停止，前方有危险")
        elif blockers and self.blocking_streak >= 2:
            decision = GuidanceDecision(CAUTION, "目标可能进入行走路线", 0.75, "注意，前方可能有障碍")
        elif blockers:
            decision = GuidanceDecision(
                UNKNOWN_SLOW_DOWN, "等待连续帧确认", 0.25, "前方情况不明，请减速"
            )
        elif region.confidence < 0.35:
            decision = GuidanceDecision(UNKNOWN_SLOW_DOWN, "可行走区域不确定", region.confidence, "前方情况不明，请减速")
        else:
            decision = GuidanceDecision(KEEP_STRAIGHT, "中央路线可通行", region.confidence, "保持直行")
        return decision

    def should_emit(self, decision, frame):
        rank = self._warning_rank(decision.state)
        if (rank and frame - self.last_warning_emit_frame < self.repeat_frames and
                rank <= self.last_warning_rank):
            self.last_state = decision.state
            return False
        if decision.state != self.last_state or frame - self.last_emit_frame >= self.repeat_frames:
            self.last_state = decision.state
            self.last_emit_frame = frame
            if rank:
                self.last_warning_emit_frame = frame
                self.last_warning_rank = rank
            return True
        return False

    @staticmethod
    def _warning_rank(state):
        return {
            UNKNOWN_SLOW_DOWN: 1,
            CAUTION: 2,
            DANGER: 3,
            STOP: 3,
        }.get(state, 0)

    def _approaching(self, record):
        history = self.history.get(str(record.get("track_id", "unknown")), [])
        if len(history) < 3:
            return False
        recent = history[-3:]
        growth = [recent[index][1] / max(recent[index - 1][1], 1e-6) - 1.0
                  for index in range(1, len(recent))]
        return min(growth) >= 0.04 and sum(growth) / len(growth) >= 0.08

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


def evaluate_guidance_records(records, width, height, uncertain=False, regions=None):
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
    for frame in sorted(set(by_frame) | set(regions or {})):
        region = (regions or {}).get(frame)
        decision = engine.update(frame, by_frame.get(frame, []), region=region, uncertain=uncertain)
        emitted = engine.should_emit(decision, frame)
        counts[decision.state] = counts.get(decision.state, 0) + 1
        trace.append({
            "frame": frame,
            "state": decision.state,
            "reason": decision.reason,
            "confidence": round(decision.confidence, 3),
            "speech": decision.speech if emitted else None,
            "region_source": getattr(region, "source", None),
            "region_surface": getattr(region, "surface", "unknown"),
            "region_left": round(float(getattr(region, "left", 0.36)), 4) if region else None,
            "region_right": round(float(getattr(region, "right", 0.64)), 4) if region else None,
            "region_floor_y": round(float(getattr(region, "floor_y", 0.48)), 4) if region else None,
            "region_confidence": round(float(getattr(region, "confidence", 0.0)), 4) if region else None,
        })
    return {"trace": trace, "state_counts": counts}
