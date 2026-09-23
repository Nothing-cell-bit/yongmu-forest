# -*- coding: utf-8 -*-
"""Pure presentation timing for Ur-Ghast weather and Ghast Trap effects."""

from __future__ import division

import math


STORM_RAMP_PER_TICK = 0.1
STORM_FADE_PER_TICK = 0.02
STORM_MAX_INTENSITY = 1.0
STORM_KEEPALIVE_TICKS = 40
WEATHER_PARTICLE_BUDGET = 100

TRAP_WARMUP_END = 30
TRAP_ACTIVE_END = 80
TRAP_DURATION = 120
TRAP_SPIRAL_RADIUS = 2.5
TRAP_SPIRAL_HEIGHT = 20.0
# The authoritative tear damage/lift AABB remains the source-sized Boss box.
# This smaller presentation sheet starts at the actor's underside and lets the
# particle itself fall, avoiding sparse sprites scattered through all 50 blocks.
TEAR_COLUMN_HALF_WIDTH = 4.5
TEAR_COLUMN_MIN_Y = -0.5
TEAR_COLUMN_MAX_Y = 0.5
TEAR_PARTICLES_PER_PULSE = 16


def native_weather_levels(active):
    """Use native rain while keeping source lightning presentation-only."""
    return {
        "rain": 1.0 if active else 0.0,
        "thunder": 0.0,
    }


def advance_storm_intensity(intensity, alive):
    intensity = max(0.0, min(STORM_MAX_INTENSITY, float(intensity)))
    if alive:
        return min(STORM_MAX_INTENSITY, intensity + STORM_RAMP_PER_TICK)
    return max(0.0, intensity - STORM_FADE_PER_TICK)


def weather_particle_budget(intensity, reduced=False):
    intensity = max(0.0, min(STORM_MAX_INTENSITY, float(intensity)))
    budget = int(WEATHER_PARTICLE_BUDGET * intensity * intensity)
    return budget // 2 if reduced else budget


def storm_presentation_step(storms, current_tick, dimension_id, intensity):
    """Advance one client tick of visible storm ownership."""
    current_tick = int(current_tick)
    dimension_id = int(dimension_id)
    active = any(
        int(storm.get("dimensionId", -1)) == dimension_id
        and storm_keepalive_active(current_tick, storm.get("expires", -1))
        for storm in (storms or {}).values()
    )
    intensity = advance_storm_intensity(intensity, active)
    return {
        "active": active,
        "intensity": intensity,
        "particleBudget": max(
            1 if active else 0,
            weather_particle_budget(intensity, reduced=True),
        ),
    }


def storm_keepalive_active(current_tick, expires_tick):
    return int(current_tick) < int(expires_tick)


def tear_column_positions(origin, samples):
    """Map normalized samples into a compact sheet under the Boss body."""
    origin = tuple(float(value) for value in origin)
    positions = []
    for sample in list(samples or ())[:TEAR_PARTICLES_PER_PULSE]:
        if sample is None or len(sample) != 3:
            continue
        values = [max(0.0, min(1.0, float(value))) for value in sample]
        positions.append((
            origin[0] + (values[0] * 2.0 - 1.0) * TEAR_COLUMN_HALF_WIDTH,
            origin[1] + TEAR_COLUMN_MIN_Y
            + values[1] * (TEAR_COLUMN_MAX_Y - TEAR_COLUMN_MIN_Y),
            origin[2] + (values[2] * 2.0 - 1.0) * TEAR_COLUMN_HALF_WIDTH,
        ))
    return positions


def trap_effect_stage(counter):
    counter = max(0, int(counter))
    if counter < TRAP_WARMUP_END:
        return "warmup"
    if counter < TRAP_ACTIVE_END:
        return "active"
    if counter < TRAP_DURATION:
        return "spindown"
    return "stop"


def trap_spiral_vectors(counter):
    angle = float(counter) / 10.0
    x_motion = math.cos(angle) * TRAP_SPIRAL_RADIUS
    z_motion = math.sin(angle) * TRAP_SPIRAL_RADIUS
    height = TRAP_SPIRAL_HEIGHT
    return [
        (x_motion, height, z_motion),
        (-x_motion, height, -z_motion),
        (-x_motion, height / 2.0, z_motion),
        (x_motion, height / 2.0, -z_motion),
        (x_motion / 2.0, height / 4.0, z_motion / 2.0),
        (-x_motion / 2.0, height / 4.0, -z_motion / 2.0),
    ]


def trap_effect_interval(stage):
    return {
        "warmup": 5,
        "active": 5,
        "spindown": 5,
        "stop": 1,
    }.get(str(stage), 5)


def rain_emitter_count(intensity):
    budget = weather_particle_budget(intensity)
    if budget <= 0:
        return 0
    if budget < 36:
        return 1
    if budget < 72:
        return 2
    return 3
