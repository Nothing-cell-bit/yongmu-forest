# -*- coding: utf-8 -*-
"""Render-only shield motion; state belongs to a cast, not its visual entity."""
from __future__ import division
import math
import time

render_clock = getattr(time, "perf_counter", None) or getattr(time, "clock", time.time)
SMOOTH_SECONDS = 0.025
MAX_LAG = 0.25
TELEPORT_DISTANCE = 4.0


def sample(state, position, now):
    """Return bounded, frame-rate-independent smoothing and continuous phase.

    Never interpolate a teleport or a long render pause across the world.
    The caller retains this state when replacing the independent client model.
    """
    position = tuple(float(value) for value in position)
    previous = state.get("position")
    elapsed = max(0.0, now - state.get("time", now))
    state["age"] = state.get("age", 0.0) + min(elapsed, 0.1)
    state["time"] = now
    if previous is not None:
        delta = tuple(position[i] - previous[i] for i in range(3))
        distance = math.sqrt(sum(value * value for value in delta))
        if elapsed <= 0.25 and distance < TELEPORT_DISTANCE:
            remaining = math.exp(-elapsed / SMOOTH_SECONDS)
            if distance > 0:
                remaining = min(remaining, MAX_LAG / distance)
            position = tuple(position[i] - delta[i] * remaining for i in range(3))
    state["position"] = position
    return position, state["age"]
