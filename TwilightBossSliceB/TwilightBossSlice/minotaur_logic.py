# -*- coding: utf-8 -*-
"""Source-locked melee, charge and ground-slam state machines.

The functions in this module deliberately avoid engine APIs.  The server
system owns targets, motion, damage and entity events, while these helpers own
the exact Java goal predicates and one-shot temporal transitions.
"""


MINOTAUR_HEALTH = 30.0
MINOSHROOM_HEALTH = 120.0
MINOSHROOM_XP_REWARD = 100
MINOSHROOM_HOME_RADIUS = 20.0

MINOTAUR_MELEE_DAMAGE = 5.0
MINOSHROOM_MELEE_DAMAGE = 7.0
MELEE_COOLDOWN_TICKS = 20

GOLD_MINOTAUR_AXE = "tf_slice:gold_minotaur_axe"
VANILLA_GOLDEN_AXE = "minecraft:golden_axe"
DIAMOND_MINOTAUR_AXE = "tf_slice:diamond_minotaur_axe"
MINOTAUR_WEAPONS = frozenset((GOLD_MINOTAUR_AXE, VANILLA_GOLDEN_AXE))
MINOSHROOM_WEAPONS = frozenset((DIAMOND_MINOTAUR_AXE,))

CHARGE_MIN_RANGE_SQ = 16.0
CHARGE_MAX_RANGE_SQ = 64.0
MINOSHROOM_CHARGE_BONUS_SQ = 9.0
CHARGE_FREQUENCY = 10
CHARGE_WINDUP_RANGE = (15, 44)
CHARGE_SPEED = 1.5
CHARGE_OVERSHOOT = 2.1

SLAM_MIN_RANGE_SQ = 2.0
SLAM_MAX_RANGE_SQ = 9.0
SLAM_VISIBLE_FREQUENCY = 24
SLAM_HIDDEN_FREQUENCY = 20
SLAM_COOLDOWN_RANGE = (200, 399)
SLAM_WINDUP_RANGE = (30, 59)
SLAM_RECOVERY_TICKS = 6


def melee_damage(is_minoshroom):
    """Return the Java attack-damage attribute for this entity."""
    return (
        MINOSHROOM_MELEE_DAMAGE
        if is_minoshroom
        else MINOTAUR_MELEE_DAMAGE
    )


def can_target_player(game_type, is_alive, same_dimension):
    """Apply Java player-target exclusions before assigning engine aggro."""
    return bool(
        is_alive
        and same_dimension
        and int(game_type) not in (1, 3, 6)
    )


def melee_attack_reach_sq(attacker_width, target_width):
    """Match ``MeleeAttackGoal#getAttackReachSqr`` from the locked runtime."""
    doubled_width = max(0.0, float(attacker_width)) * 2.0
    return doubled_width * doubled_width + max(0.0, float(target_width))


def advance_melee(
    cooldown_ticks,
    has_target,
    target_in_range,
    special_active,
):
    """Advance the one-second Java melee cooldown by one server tick."""
    cooldown = max(0, int(cooldown_ticks) - 1)
    attack = bool(
        has_target
        and target_in_range
        and not special_active
        and cooldown == 0
    )
    if attack:
        cooldown = MELEE_COOLDOWN_TICKS
    return cooldown, attack


def _bounded_roll(value, maximum):
    return max(0, min(int(maximum), int(value)))


def spawn_weapon(is_minoshroom, random_roll, effective_difficulty):
    """Return the weapon selected by the locked Java spawn equipment rule."""
    if is_minoshroom:
        return DIAMOND_MINOTAUR_AXE
    roll = _bounded_roll(random_roll, 9)
    additional_difficulty = max(1.0, float(effective_difficulty) + 1.0)
    if int(roll / additional_difficulty) == 0:
        return GOLD_MINOTAUR_AXE
    return VANILLA_GOLDEN_AXE


def can_start_charge(
    distance_sq,
    is_minoshroom,
    on_ground,
    has_line_of_sight,
    random_roll,
):
    bonus = MINOSHROOM_CHARGE_BONUS_SQ if is_minoshroom else 0.0
    distance_sq = float(distance_sq)
    return bool(
        CHARGE_MIN_RANGE_SQ + bonus <= distance_sq
        <= CHARGE_MAX_RANGE_SQ + bonus
        and on_ground
        and has_line_of_sight
        and int(random_roll) == 0
    )


def charge_windup(random_value):
    return CHARGE_WINDUP_RANGE[0] + _bounded_roll(random_value, 29)


def charge_destination(attacker, target):
    import math

    ax, _, az = (float(value) for value in attacker)
    tx, ty, tz = (float(value) for value in target)
    dx = tx - ax
    dz = tz - az
    distance = math.sqrt(dx * dx + dz * dz)
    if distance <= 0.000001:
        return (ax, ty, az)
    scale = (distance + CHARGE_OVERSHOOT) / distance
    return (ax + dx * scale, ty, az + dz * scale)


def start_charge(random_value, destination, target_id):
    return {
        "phase": "windup",
        "ticks_remaining": charge_windup(random_value),
        "destination": tuple(float(value) for value in destination),
        "target_id": target_id,
        "has_attacked": False,
    }


def advance_charge(state, navigation_done, target_in_range):
    state = dict(state or {})
    actions = {
        "navigate": False,
        "attack": False,
        "clear_charging": False,
    }
    phase = state.get("phase", "stopped")
    if phase == "stopped":
        actions["clear_charging"] = True
        return state, actions

    if target_in_range and not state.get("has_attacked", False):
        state["has_attacked"] = True
        actions["attack"] = True

    if phase == "windup":
        remaining = max(0, int(state.get("ticks_remaining", 0)) - 1)
        state["ticks_remaining"] = remaining
        if remaining == 0:
            state["phase"] = "moving"
            actions["navigate"] = True
    elif phase == "moving" and navigation_done:
        state["phase"] = "stopped"
        state["target_id"] = None
        actions["clear_charging"] = True
    return state, actions


def cancel_charge(state):
    state = dict(state or {})
    state.update({
        "phase": "stopped",
        "ticks_remaining": 0,
        "target_id": None,
        "has_attacked": False,
    })
    return state


def charge_push(yaw_degrees):
    import math

    yaw = math.radians(float(yaw_degrees))
    return (
        -math.sin(yaw) * CHARGE_OVERSHOOT,
        math.cos(yaw) * CHARGE_OVERSHOOT,
    )


def can_start_slam(
    distance_sq,
    on_ground,
    has_line_of_sight,
    random_roll,
    cooldown_ticks,
):
    frequency = (
        SLAM_VISIBLE_FREQUENCY
        if has_line_of_sight
        else SLAM_HIDDEN_FREQUENCY
    )
    return bool(
        int(cooldown_ticks) <= 0
        and SLAM_MIN_RANGE_SQ <= float(distance_sq) <= SLAM_MAX_RANGE_SQ
        and on_ground
        and 0 <= int(random_roll) < frequency
        and int(random_roll) == 0
    )


def slam_cooldown(random_value):
    return SLAM_COOLDOWN_RANGE[0] + _bounded_roll(random_value, 199)


def slam_windup(random_value):
    return SLAM_WINDUP_RANGE[0] + _bounded_roll(random_value, 29)


def start_slam(cooldown_random, windup_random, target_id):
    return {
        "phase": "windup",
        "ticks_remaining": slam_windup(windup_random),
        "cooldown_ticks": slam_cooldown(cooldown_random),
        "target_id": target_id,
        "impacted": False,
    }


def advance_slam(state):
    state = dict(state or {})
    actions = {"impact": False, "clear_ground_attack": False}
    if state.get("phase", "stopped") == "stopped":
        actions["clear_ground_attack"] = True
        return state, actions
    remaining = int(state.get("ticks_remaining", 0))
    if remaining <= 0:
        if not state.get("impacted", False):
            state["impacted"] = True
            actions["impact"] = True
        state["phase"] = "stopped"
        state["target_id"] = None
        actions["clear_ground_attack"] = True
    else:
        state["ticks_remaining"] = remaining - 1
    return state, actions


def advance_slam_recovery(ticks_remaining):
    """Advance the six client ticks used by the source model to stand back up."""
    remaining = max(0, int(ticks_remaining))
    if remaining <= 0:
        return 0, False
    remaining -= 1
    return remaining, remaining == 0


def cancel_slam(state):
    state = dict(state or {})
    state.update({
        "phase": "stopped",
        "ticks_remaining": 0,
        "target_id": None,
    })
    return state


def ground_attack_bounds(center, relative=False):
    if relative:
        return ((-7.5, 0.0, -7.5), (7.5, 3.0, 7.5))
    x, y, z = (float(value) for value in center)
    return ((x - 7.5, y, z - 7.5), (x + 7.5, y + 3.0, z + 7.5))


def in_ground_attack_bounds(center, position):
    minimum, maximum = ground_attack_bounds(center)
    return all(
        minimum[index] <= float(position[index]) <= maximum[index]
        for index in range(3)
    )


def ground_attack_damage(attack_damage, target_grounded):
    if not target_grounded:
        return 0.0
    return max(0.0, float(attack_damage)) * 0.5


def ground_attack_knockup(target_grounded):
    return 0.23 if target_grounded else 0.0


def outside_home(position, home):
    if position is None or home is None:
        return False
    dx = float(position[0]) - float(home[0])
    dz = float(position[2]) - float(home[2])
    return dx * dx + dz * dz > MINOSHROOM_HOME_RADIUS ** 2
