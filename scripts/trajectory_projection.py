"""Causal, uncertainty-gated image-space motion visualization.

Consumes the Android engine's already background-aligned contact history.
This is a relative image motion estimate, not a calibrated road path, and
does not create or change collision warnings. Missing motion evidence means
no line, rather than a fabricated stationary/directional prediction.
"""

import math
from statistics import median


def project_contact_motion(history, width, height, motion_reliable,
                           bottom_clipped=False, horizon_seconds=0.6):
    if not motion_reliable or bottom_clipped or width <= 0 or height <= 0:
        return None
    if not 0 < horizon_seconds <= 1.5:
        raise ValueError("invalid projection horizon")
    points = list(history)[-8:]
    if len(points) < 4:
        return None
    samples = [(float(p['x']) / width, float(p['y']) / height,
                float(p['timestamp_ms']) / 1000) for p in points]
    if not all(math.isfinite(v) for sample in samples for v in sample):
        return None
    steps = []
    for old, new in zip(samples, samples[1:]):
        dt = new[2] - old[2]
        if not 0 < dt <= 0.25:
            return None
        steps.append(((new[0] - old[0]) / dt, (new[1] - old[1]) / dt))
    span = samples[-1][2] - samples[0][2]
    if span < 0.15:
        return None
    vx = median(p[0] for p in steps)
    vy = median(p[1] for p in steps)
    speed = math.hypot(vx, vy)
    if speed < 0.03 or speed > 1.0:
        return None
    # Alternating detector jitter must not become a future direction.
    agreement = sum(dx * vx + dy * vy > 0 for dx, dy in steps) / len(steps)
    if agreement < 0.75:
        return None
    net = math.hypot(samples[-1][0] - samples[0][0], samples[-1][1] - samples[0][1])
    if net < 0.005:
        return None
    # A coherent constant-velocity fit must explain the observed motion.
    residual = max(math.hypot(x - samples[0][0] - vx * (t - samples[0][2]),
                              y - samples[0][1] - vy * (t - samples[0][2]))
                   for x, y, t in samples)
    if residual > max(0.003, net * 0.35):
        return None
    x, y, _ = samples[-1]
    return {
        'start': (x * width, y * height),
        'end': ((x + vx * horizon_seconds) * width,
                (y + vy * horizon_seconds) * height),
        'horizon_seconds': horizon_seconds,
        'basis': 'background_aligned_observed_contact_motion',
        'collision_guarantee': False,
    }


def track_display_level(track_level, route_relevant, guidance_state):
    """A scene-level danger must not colour other objects as incoming threats."""
    if track_level >= 2:
        return 2
    if track_level >= 1:
        return 1
    if route_relevant and guidance_state in {
        'CAUTION', 'DANGER', 'STOP', 'UNKNOWN_SLOW_DOWN', 'MOVE_LEFT', 'MOVE_RIGHT'
    }:
        return 1
    return 0
