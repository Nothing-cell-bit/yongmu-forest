# -*- coding: utf-8 -*-
"""Pure, deterministic contracts for the three classic Twilight beetles."""
import math


FIRE_RANGE_SQ = 25.0
FIRE_DURATION_TICKS = 30
FIRE_WARMUP_TICKS = 5
FIRE_START_CHANCE = 0.10
FIRE_BEAM_RANGE = 30.0
FIRE_DAMAGE = 2.0
FIRE_SECONDS = 10
FIRE_MOUTH_OFFSET = 0.9
FIRE_GOAL_CHECK_INTERVAL_TICKS = 3

SLIME_INTERVAL_TICKS = 30
SLIME_RANGE = 10.0
SLIME_POWER = 0.6
SLIME_GRAVITY = 0.006
SLIME_INACCURACY = 6.0
SLIME_DAMAGE = 4.0

PINCH_MIN_RANGE_SQ = 16.0
PINCH_MAX_RANGE_SQ = 64.0
PINCH_START_CHANCE = 0.10
PINCH_WINDUP_MIN_TICKS = 15
PINCH_WINDUP_RANDOM_TICKS = 30
PINCH_CHARGE_SPEED = 1.5
PINCH_OVERSHOOT = 2.1
PINCH_CARRY_WIDTH = 2.25
PINCH_CARRY_HEIGHT = 1.25
PINCH_SNATCH_BLOCKING_RIDES = frozenset(
    ("tf_slice:pinch_beetle", "tf_slice:yeti", "tf_slice:alpha_yeti")
)


def fire_can_start(distance_sq, visible, target_valid, roll):
    return (
        bool(visible)
        and bool(target_valid)
        and float(distance_sq) <= FIRE_RANGE_SQ
        and float(roll) < FIRE_START_CHANCE
    )


def fire_goal_check_ready(current_tick, next_check_tick):
    return int(current_tick) >= int(next_check_tick)


def fire_is_damaging(elapsed_ticks):
    elapsed_ticks = int(elapsed_ticks)
    return FIRE_WARMUP_TICKS < elapsed_ticks < FIRE_DURATION_TICKS


def fire_target_eye_height(collision_height, is_player):
    if is_player:
        return 1.62
    return max(0.25, float(collision_height) * 0.85)


def fire_breath_visual_points(start, aim, travel_distances):
    """Place a short source-like stream from the mouth, never on the ground ray."""
    sx, sy, sz = (float(value) for value in start)
    ax, ay, az = (float(value) for value in aim)
    dx, dy, dz = ax - sx, ay - sy, az - sz
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length <= 1.0e-6:
        return ()
    dx, dy, dz = dx / length, dy / length, dz / length
    mouth = (
        sx + dx * FIRE_MOUTH_OFFSET,
        sy + dy * FIRE_MOUTH_OFFSET,
        sz + dz * FIRE_MOUTH_OFFSET,
    )
    return tuple(
        (
            mouth[0] + dx * float(distance),
            mouth[1] + dy * float(distance),
            mouth[2] + dz * float(distance),
        )
        for distance in travel_distances
    )


def beam_hit(start, aim, target, radius=0.75, max_range=FIRE_BEAM_RANGE):
    """True when target intersects the frozen breath ray."""
    sx, sy, sz = (float(value) for value in start)
    ax, ay, az = (float(value) for value in aim)
    tx, ty, tz = (float(value) for value in target)
    dx, dy, dz = ax - sx, ay - sy, az - sz
    length = math.sqrt(dx * dx + dy * dy + dz * dz)
    if length <= 1.0e-6:
        return False
    dx, dy, dz = dx / length, dy / length, dz / length
    vx, vy, vz = tx - sx, ty - sy, tz - sz
    projection = vx * dx + vy * dy + vz * dz
    if projection < 0.0 or projection > float(max_range):
        return False
    px, py, pz = sx + dx * projection, sy + dy * projection, sz + dz * projection
    ex, ey, ez = tx - px, ty - py, tz - pz
    return ex * ex + ey * ey + ez * ez <= float(radius) ** 2


def slime_aim_vector(origin, target):
    """Java SlimeBeetle adds horizontal distance * 0.2 to vertical aim."""
    dx = float(target[0]) - float(origin[0])
    dy = float(target[1]) - float(origin[1])
    dz = float(target[2]) - float(origin[2])
    horizontal = math.sqrt(dx * dx + dz * dz)
    return (dx, dy + horizontal * 0.2, dz)


def pinch_can_start(distance_sq, on_ground, visible, roll):
    distance_sq = float(distance_sq)
    return (
        bool(on_ground)
        and bool(visible)
        and PINCH_MIN_RANGE_SQ <= distance_sq <= PINCH_MAX_RANGE_SQ
        and float(roll) < PINCH_START_CHANCE
    )


def pinch_windup_ticks(random_value):
    return PINCH_WINDUP_MIN_TICKS + (
        int(random_value) % PINCH_WINDUP_RANDOM_TICKS
    )


def pinch_charge_should_continue(windup_ticks, navigation_done):
    return int(windup_ticks) > 0 or not bool(navigation_done)


def pinch_charge_destination(origin, target):
    """Return the original goal's point 2.1 blocks beyond its target."""
    dx = float(target[0]) - float(origin[0])
    dz = float(target[2]) - float(origin[2])
    length = math.sqrt(dx * dx + dz * dz)
    if length <= 1.0e-6:
        return tuple(float(value) for value in target)
    return (
        float(target[0]) + dx / length * PINCH_OVERSHOOT,
        float(target[1]),
        float(target[2]) + dz / length * PINCH_OVERSHOOT,
    )


def pinch_attack_reach_sq(attacker_width, target_width):
    """Match ChargeAttackGoal's non-Minoshroom contact threshold."""
    doubled_width = float(attacker_width) * 2.0
    return doubled_width * doubled_width + float(target_width)


def pinch_melee_can_grab(has_passenger, ridden_entity_type):
    return (
        not bool(has_passenger)
        and str(ridden_entity_type or "") not in PINCH_SNATCH_BLOCKING_RIDES
    )
