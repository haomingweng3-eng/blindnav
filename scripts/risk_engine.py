"""分级风险引擎原型：不依赖绝对距离，用检测框面积变化率(looming)+横向位移判断风险等级。

核心逻辑：
- 面积变大且持续 = 快速接近（looming）
- 面积变大 + 横向位移小 = 直冲你来，最高危
- 面积稳定 + 横向大位移 = 横向穿过，中危（会切进路线）
- 面积变小 = 远离，无视
"""
import math
from statistics import median


LVL_NONE, LVL_LOW, LVL_MID, LVL_HIGH = 0, 1, 2, 3
LVL_NAME = {0: "无", 1: "提示", 2: "警告", 3: "危险"}


def box_area(b):
    return max(b[2] - b[0], 1) * max(b[3] - b[1], 1)


def box_center(b):
    return ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)


class TrackState:
    """单个跟踪目标的历史状态，模拟 ByteTrack 输出的 per-track 数据。"""

    def __init__(
        self,
        tid,
        cls,
        looming_threshold=0.06,
        corridor_half_width=0.18,
        corridor_center=0.0,
        entry_lateral_threshold=0.04,
        entry_confirm_frames=3,
        prediction_frames=5,
        fps=1.0,
        reference_fps=1.0,
        min_approach_area=0.0,
    ):
        if looming_threshold < 0:
            raise ValueError("looming_threshold must be non-negative")
        if corridor_half_width <= 0:
            raise ValueError("corridor_half_width must be positive")
        if not -0.5 <= corridor_center <= 0.5:
            raise ValueError("corridor_center must be between -0.5 and 0.5")
        if entry_lateral_threshold < 0:
            raise ValueError("entry_lateral_threshold must be non-negative")
        if not isinstance(entry_confirm_frames, int) or entry_confirm_frames <= 0:
            raise ValueError("entry_confirm_frames must be a positive integer")
        if prediction_frames <= 0:
            raise ValueError("prediction_frames must be positive")
        if fps <= 0 or reference_fps <= 0:
            raise ValueError("fps and reference_fps must be positive")
        if min_approach_area < 0:
            raise ValueError("min_approach_area must be non-negative")
        self.tid = tid
        self.cls = cls
        self.looming_threshold = float(looming_threshold)
        self.corridor_half_width = float(corridor_half_width)
        self.corridor_center = float(corridor_center)
        self.entry_lateral_threshold = float(entry_lateral_threshold)
        self.entry_confirm_frames = entry_confirm_frames
        self.prediction_frames = int(prediction_frames)
        self.fps = float(fps)
        self.reference_fps = float(reference_fps)
        self.min_approach_area = float(min_approach_area)
        self.boxes = []
        self.frame_indices = []
        self.last_alert = -999
        self.cooldown = 5  # 同一目标告警冷却帧数，防反复播报

    def update(self, box, frame_idx=None):
        if frame_idx is None:
            frame_idx = self.frame_indices[-1] + 1 if self.frame_indices else 0
        self.boxes.append(box)
        self.frame_indices.append(int(frame_idx))
        if len(self.boxes) > 10:
            self.boxes.pop(0)
            self.frame_indices.pop(0)

    def assess(self, frame_idx):
        if len(self.boxes) < 4:
            return LVL_NONE, {}

        new = self.boxes[-1]
        a_new_n = box_area(new) / (640 * 640)

        # 用连续帧的 log-area 增长率，再取中位数，降低单帧检测框抖动的影响。
        # 单帧突变只会贡献一个异常增长率，不应单独升级风险。
        window_start = max(0, len(self.boxes) - 6)
        areas = [
            max(box_area(box), 1e-6) for box in self.boxes[window_start:]
        ]
        frames = self.frame_indices[window_start:]
        log_growth = [
            (math.log(new_area) - math.log(old_area))
            * self.fps
            / self.reference_fps
            / max(new_frame - old_frame, 1)
            for old_area, new_area, old_frame, new_frame in zip(
                areas, areas[1:], frames, frames[1:]
            )
        ]
        looming = math.expm1(median(log_growth))

        centers = [box_center(box)[0] for box in self.boxes[window_start:]]
        lateral_rates = [
            (new_cx - old_cx)
            / 640.0
            * self.fps
            / self.reference_fps
            / max(new_frame - old_frame, 1)
            for old_cx, new_cx, old_frame, new_frame in zip(
                centers, centers[1:], frames, frames[1:]
            )
        ]
        lateral = median(lateral_rates)
        current_x = box_center(new)[0] / 640.0 - 0.5
        if current_x < -0.15:
            direction = "left"
        elif current_x > 0.15:
            direction = "right"
        else:
            direction = "front"
        future_x = current_x + lateral * self.prediction_frames
        corridor_min = self.corridor_center - self.corridor_half_width
        corridor_max = self.corridor_center + self.corridor_half_width
        previous_xs = [
            box_center(box)[0] / 640.0 - 0.5 for box in self.boxes[window_start:-1]
        ]
        current_inside = corridor_min <= current_x <= corridor_max
        inside_streak = 0
        for box in reversed(self.boxes[window_start:]):
            x = box_center(box)[0] / 640.0 - 0.5
            if corridor_min <= x <= corridor_max:
                inside_streak += 1
            else:
                break
        entered_from_outside = any(
            not (corridor_min <= previous_x <= corridor_max)
            for previous_x in previous_xs
        )
        route_entry = (
            current_inside
            and entered_from_outside
            and inside_streak >= self.entry_confirm_frames
        )
        predicted_entry = (
            not current_inside
            and corridor_min <= future_x <= corridor_max
            and abs(lateral) >= self.entry_lateral_threshold
        )
        # 横向告警只针对“进入路线”的运动。目标已经在路线内但正在
        # 向外离开，或只是沿路线边缘平行经过，不应仅凭横向速度报警。
        entry_motion = route_entry or predicted_entry
        inside_confirmed = current_inside and (
            not entered_from_outside
            or inside_streak >= self.entry_confirm_frames
        )
        if route_entry:
            route_relation = "entered"
        elif predicted_entry:
            route_relation = "predicted_entry"
        elif current_inside and entered_from_outside and not inside_confirmed:
            route_relation = "inside_unconfirmed"
        elif current_inside and not (corridor_min <= future_x <= corridor_max):
            route_relation = "exiting"
        elif current_inside:
            route_relation = "inside"
        else:
            route_relation = "outside"
        dynamic_path_conflict = inside_confirmed or predicted_entry
        path_conflict = (
            corridor_min <= current_x <= corridor_max
            or min(current_x, future_x) <= corridor_max
            and max(current_x, future_x) >= corridor_min
        )

        # 近距离阈值分两档
        close_high = a_new_n > 0.06  # ≈157px 框，直冲危险距离
        close_low = a_new_n > 0.015  # ≈78px 框，横向值得提示
        predicted_area_n = a_new_n * math.exp(
            max(looming, 0.0) * self.prediction_frames
        )
        predicted_approach = (
            a_new_n < self.min_approach_area
            and predicted_area_n >= self.min_approach_area
            and looming > self.looming_threshold
            and dynamic_path_conflict
            and (route_entry or predicted_entry)
            and route_relation not in {"exiting", "outside", "inside_unconfirmed"}
        )

        lvl = LVL_NONE
        reason = ""
        if (
            looming > self.looming_threshold
            and dynamic_path_conflict
            and (a_new_n >= self.min_approach_area or predicted_approach)
            and close_high
        ):
            lvl = LVL_HIGH
            reason = "快速接近且近距离"
        elif (
            looming > self.looming_threshold
            and dynamic_path_conflict
            and (a_new_n >= self.min_approach_area or predicted_approach)
        ):
            lvl = LVL_MID
            reason = "预计快速接近" if predicted_approach else "快速接近"
        elif (
            abs(lateral) >= self.entry_lateral_threshold
            and close_low
            and entry_motion
        ):
            lvl = LVL_MID
            reason = "横向穿过"
        elif close_high and inside_confirmed:
            lvl = LVL_LOW
            reason = "近距离静态"

        if lvl >= LVL_MID and frame_idx - self.last_alert < self.cooldown:
            lvl = LVL_NONE
        elif lvl >= LVL_MID:
            self.last_alert = frame_idx

        return lvl, {
            "looming": round(looming, 4),
            "looming_threshold": self.looming_threshold,
            "fps": self.fps,
            "reference_fps": self.reference_fps,
            "lateral": round(lateral, 4),
            "direction": direction,
            "path_conflict": path_conflict,
            "dynamic_path_conflict": dynamic_path_conflict,
            "inside_confirmed": inside_confirmed,
            "predicted_entry": predicted_entry,
            "route_entry": route_entry,
            "entry_motion": entry_motion,
            "route_relation": route_relation,
            "corridor_center": self.corridor_center,
            "corridor_half_width": self.corridor_half_width,
            "entry_lateral_threshold": self.entry_lateral_threshold,
            "entry_confirm_frames": self.entry_confirm_frames,
            "inside_streak": inside_streak,
            "area_n": round(a_new_n, 4),
            "predicted_area_n": round(predicted_area_n, 4),
            "predicted_approach": predicted_approach,
            "min_approach_area": self.min_approach_area,
            "close": close_high,
            "reason": reason,
        }
