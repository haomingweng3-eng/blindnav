"""参数化风险引擎评估，不使用真实数据，不把仿真结果当成场景准确率。"""

import json
from dataclasses import dataclass

try:
    from .risk_engine import LVL_MID, LVL_NAME, TrackState
    from .feedback_policy import feedback_for
except ImportError:  # 支持直接用 PYTHONPATH=scripts 执行本文件
    from risk_engine import LVL_MID, LVL_NAME, TrackState
    from feedback_policy import feedback_for


ALERT_CLASSES = {
    "person",
    "bicycle",
    "motorcycle",
    "scooter",
    "electric_bicycle",
    "electric_bike",
    "e-bike",
    "electric bicycle",
    "car",
    "bus",
    "truck",
}


@dataclass(frozen=True)
class Scenario:
    name: str
    motion: str
    boxes: list
    expects_mid_alert: bool


def centered_box(side, cx=320.0, cy=300.0):
    half = side / 2.0
    return [cx - half, cy - half, cx + half, cy + half]


def build_scenarios():
    return [
        Scenario(
            "fast_approach",
            "approach",
            [centered_box(side) for side in [60, 66, 73, 82, 93, 106, 121]],
            True,
        ),
        Scenario(
            "slow_approach",
            "approach",
            [centered_box(side) for side in [60, 61, 62, 63, 64, 65, 66]],
            False,
        ),
        Scenario(
            "borderline_approach",
            "approach",
            [centered_box(side) for side in [70, 73, 76, 79, 82, 85, 88]],
            True,
        ),
        Scenario(
            "away",
            "away",
            [centered_box(side) for side in [140, 125, 112, 100, 89, 79, 70]],
            False,
        ),
        Scenario("static", "static", [centered_box(90)] * 7, False),
        Scenario(
            "single_frame_spike",
            "noise",
            [centered_box(side) for side in [80, 80, 80, 240, 80, 80, 80]],
            False,
        ),
        Scenario(
            "crossing_near",
            "crossing",
            [centered_box(100, cx=cx) for cx in [150, 200, 250, 300, 350, 400]],
            True,
        ),
        Scenario(
            "crossing_far",
            "crossing",
            [centered_box(50, cx=cx) for cx in [150, 200, 250, 300, 350, 400]],
            False,
        ),
        Scenario(
            "noisy_approach",
            "noise",
            [centered_box(side) for side in [70, 75, 78, 90, 88, 100, 110, 120]],
            True,
        ),
        Scenario(
            "approach_with_duplicate_frame",
            "dropout",
            [centered_box(side) for side in [70, 75, 75, 85, 95, 110, 125]],
            True,
        ),
    ]


def evaluate_scenario(scenario, looming_threshold=0.06):
    state = TrackState(
        scenario.name, "bicycle", looming_threshold=looming_threshold
    )
    levels = []
    looming_values = []

    for frame_idx, box in enumerate(scenario.boxes, start=1):
        state.update(box, frame_idx=frame_idx)
        level, info = state.assess(frame_idx)
        levels.append(level)
        if info:
            looming_values.append(info["looming"])

    return {
        "name": scenario.name,
        "motion": scenario.motion,
        "expected_mid_alert": scenario.expects_mid_alert,
        "actual_mid_alert": any(level >= LVL_MID for level in levels),
        "alert_frames": [
            frame for frame, level in enumerate(levels, start=1) if level >= LVL_MID
        ],
        "max_looming": max(looming_values, default=0.0),
    }


def evaluate_detection_records(
    records,
    width,
    height,
    looming_threshold=0.06,
    fps=1.0,
    reference_fps=1.0,
):
    """消费视频检测记录，统一缩放后按 track_id 跑风险引擎。

    每条记录格式为：
    {"frame": int, "track_id": str, "cls": str, "conf": float,
     "box": [x1, y1, x2, y2]}
    坐标使用原视频像素，输出可直接序列化为 JSON。
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    scale = 640.0 / max(width, height)
    states = {}
    detection_stats = {}
    alerts = []
    frame_count = 0

    for record in sorted(records, key=lambda item: item["frame"]):
        cls = record["cls"]
        if cls not in ALERT_CLASSES:
            continue

        frame_idx = int(record["frame"])
        frame_count = max(frame_count, frame_idx)
        detection_stats[cls] = detection_stats.get(cls, 0) + 1
        track_key = (str(record["track_id"]), cls)
        state = states.setdefault(
            track_key,
            TrackState(
                *track_key,
                looming_threshold=looming_threshold,
                fps=fps,
                reference_fps=reference_fps,
            ),
        )
        box = [float(value) * scale for value in record["box"]]
        state.update(box, frame_idx=frame_idx)
        level, info = state.assess(frame_idx)
        if level >= LVL_MID:
            alerts.append(
                {
                    "frame": frame_idx,
                    "track_id": track_key[0],
                    "cls": cls,
                    "conf": round(float(record.get("conf", 0.0)), 4),
                    "level": level,
                    "level_name": LVL_NAME[level],
                    "info": info,
                    "feedback": feedback_for(level, cls, info),
                }
            )

    return {
        "frame_count": frame_count,
        "track_count": len(states),
        "detection_stats": detection_stats,
        "alert_count": len(alerts),
        "alerts": alerts,
    }


def run_suite(looming_threshold=0.06):
    results = [
        evaluate_scenario(scenario, looming_threshold=looming_threshold)
        for scenario in build_scenarios()
    ]
    missed = [
        result["name"]
        for result in results
        if result["expected_mid_alert"] and not result["actual_mid_alert"]
    ]
    false_alerts = [
        result["name"]
        for result in results
        if not result["expected_mid_alert"] and result["actual_mid_alert"]
    ]
    return {
        "looming_threshold": looming_threshold,
        "scenario_count": len(results),
        "motion_types": len({result["motion"] for result in results}),
        "missed_expected_alerts": missed,
        "false_mid_alerts": false_alerts,
        "results": results,
    }


def sweep_looming_thresholds(thresholds):
    return [run_suite(looming_threshold=value) for value in thresholds]


if __name__ == "__main__":
    print(
        json.dumps(
            {
                "baseline": run_suite(),
                "threshold_sweep": sweep_looming_thresholds(
                    [0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10]
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
