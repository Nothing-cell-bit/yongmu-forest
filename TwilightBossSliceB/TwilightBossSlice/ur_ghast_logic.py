# -*- coding: utf-8 -*-
"""Pure Ur-Ghast phase, trap, persistence and death-flow rules."""

from __future__ import division

import copy
import math


STATE_VERSION = 6
ENGINE_UPDATE_HZ = 30
SOURCE_LOGIC_HZ = 20
MAX_HEALTH = 250.0
TRACKING_RANGE = 128
HOME_RADIUS = 64.0
HOVER_HEIGHT = 20
FIRST_PHASE_DAMAGE_THRESHOLD = 10.0
PHASE_DAMAGE_THRESHOLD = 18.0
TANTRUM_DAMAGE_MULTIPLIER = 0.1
MAX_TANTRUM_TRAPS = 2
MINIONS_PER_TANTRUM_TRAP = 6
MINION_SPAWN_TRIES = 24
MINION_SPAWN_HORIZONTAL_RADIUS = 4
MINION_SPAWN_VERTICAL_RANGE = 8
MINIONS_REQUIRED_AT_TRAP = 4
BOSS_WIDTH = 14.0
BOSS_HEIGHT = 18.0
BOSS_HEAD_HALF_WIDTH = 6.25
BOSS_HEAD_MIN_Y = 6.25
BOSS_HEAD_MAX_Y = 18.75
PLAYER_COLLISION_RADIUS = 0.35
PLAYER_COLLISION_HEIGHT = 1.8
FIREBALL_SPAWN_DISTANCE = 8.5
FIREBALL_HEALTH = 32.0
FIREBALL_DIRECT_DAMAGE = 16.0
FIREBALL_EXPLOSION_POWER = 1
FIREBALL_SPEED = 0.6
FIREBALL_REFLECT_SPEED = 1.0
FIREBALL_ACCELERATION = 0.1
FIREBALL_DRAG = 0.95
FIREBALL_RADIUS = 0.5
FIREBALL_SIBLING_SEPARATION = 1.1
FIREBALL_OWNER_IGNORE_TICKS = 4
FIREBALL_REFLECTION_WORLD_GRACE_TICKS = 4
FIREBALL_REFLECTION_RECOVERY_MAX_DISTANCE = 6.0
FIREBALL_REFLECTION_RECOVERY_RAY_RADIUS = 1.75
FIREBALL_REFLECTION_RECOVERY_BEHIND_TOLERANCE = 1.25
ATTACK_RANGE = 64.0
ATTACK_RANGE_SQ = ATTACK_RANGE * ATTACK_RANGE
ATTACK_WARN_TICK = 10
ATTACK_FIRE_TICK = 20
ATTACK_COOLDOWN_TICKS = 40
HURT_FEEDBACK_TICKS = 6
VISUAL_PITCH_LIMIT = 90.0
COMBAT_VISUAL_PITCH_LIMIT = 45.0
TANTRUM_TEAR_INTERVAL = 10
TANTRUM_TEAR_DAMAGE = 3.0
TANTRUM_MINION_LIFT_MAX = 1.1
TANTRUM_CRY_MIN_TICKS = 20
TANTRUM_CRY_SPREAD = 30
MINION_ABSORB_HEAL = 2.0
TRAP_DEATHS_TO_CHARGE = 3
TRAP_CHARGE_HORIZONTAL_RADIUS = 10
TRAP_CHARGE_VERTICAL_RADIUS = 16
TRAP_ACTIVE_HORIZONTAL_RADIUS = 6
TRAP_ACTIVE_HEIGHT = 32
TRAP_ACTIVE_TICKS = 120
TRAP_UR_GHAST_DAMAGE = 7.0
TRAP_OTHER_GHAST_DAMAGE = 10.0
TRAP_DAMAGE_ROLL = 10
TRAP_PULL_SCALE = -0.1
DEATH_FALL_ACCELERATION = 0.03
DEATH_FALL_MAX_SPEED = 1.5
FLIGHT_ACCELERATION = 0.1
FLIGHT_COURSE_COOLDOWN_MIN = 2
FLIGHT_COURSE_COOLDOWN_SPREAD = 5
FLIGHT_DRAG = 0.91
FLIGHT_CORRUPT_SPEED_LIMIT = 1.0
FLIGHT_ARRIVAL_RADIUS = 1.0
FLIGHT_STALL_TICKS = 10
FLIGHT_STALL_DISTANCE_SQ = 0.0025
FLIGHT_ALTITUDE_MARGIN = 8.0
DIRECT_COMPAT_SPEED = 0.25
ENGINE_MOTION_FAILURE_FRAMES = 5
ENGINE_MOTION_RECOVERY_FRAMES = 20
ENGINE_MOTION_MIN_REQUEST_SPEED = 0.05
ENGINE_MOTION_MIN_DISPLACEMENT = 0.05
TRAP_DISCOVERY_INTERVAL = 100
TRAP_PRUNE_INTERVAL = 60
TRAP_FALLBACK_SCAN_INTERVAL = 5
GHAST_PERCEPTION_REFRESH_INTERVAL = 4
XP_REWARD = 317
DEATH_SEQUENCE_TICKS = 90
DEATH_BURST_TICKS = 30


def advance_source_clock(remainder):
    """Map NetEase's 30 Hz Update cadence onto source-owned 20 Hz ticks."""
    total = max(0, int(remainder)) + SOURCE_LOGIC_HZ
    return {
        "steps": total // ENGINE_UPDATE_HZ,
        "remainder": total % ENGINE_UPDATE_HZ,
    }


def _ordered_route_points(points, route_order=None):
    points = [list(point) for point in points]
    if route_order is None:
        return points
    ordered = []
    used = set()
    for raw_index in route_order:
        index = int(raw_index)
        if index < 0 or index >= len(points) or index in used:
            continue
        ordered.append(points[index])
        used.add(index)
    ordered.extend(point for index, point in enumerate(points) if index not in used)
    return ordered


def build_flight_route(home, trap_points, home_bound=False, route_order=None):
    home = [float(value) for value in home]
    traps = [[float(value) for value in point] for point in (trap_points or ())]
    height_offset = HOVER_HEIGHT if bool(home_bound) else 0.0
    if traps:
        points = [
            [point[0], point[1] + height_offset, point[2]]
            for point in traps
        ]
    else:
        route_y = home[1] + height_offset
        points = [
            [home[0] + dx, route_y, home[2] + dz]
            for dx, dz in ((20, 0), (0, -20), (-20, 0), (0, 20), (0, 0))
        ]
    return _ordered_route_points(points, route_order)


def flight_altitude_bounds(state):
    waypoints = state.get("waypoints") or [state.get("home", (0, 0, 0))]
    route_y = [float(point[1]) for point in waypoints if len(point) == 3]
    if not route_y:
        route_y = [float((state.get("home") or (0, 0, 0))[1])]
    return (
        min(route_y) - FLIGHT_ALTITUDE_MARGIN,
        max(route_y) + FLIGHT_ALTITUDE_MARGIN,
    )


def _sanitize_wanted_waypoint(state, wanted):
    if wanted is None or len(wanted) != 3:
        return None
    try:
        point = [float(value) for value in wanted]
    except (TypeError, ValueError):
        return None
    floor_y, ceiling_y = flight_altitude_bounds(state)
    if point[1] < floor_y or point[1] > ceiling_y:
        return None
    home = state.get("home") or (0, 0, 0)
    if sum((point[index] - float(home[index])) ** 2 for index in range(3)) > 3600.0:
        return None
    return point


def refresh_flight_route(state, trap_points, route_order=None):
    state["trapPoints"] = [
        [float(value) for value in point] for point in (trap_points or ())
    ]
    state["waypoints"] = build_flight_route(
        state.get("home", (0, 0, 0)),
        state["trapPoints"],
        state.get("homeBound", False),
        route_order,
    )
    state["waypointIndex"] = 0
    state["wantedWaypoint"] = None
    state["flightStallTicks"] = 0
    state["lastFlightPosition"] = None
    state["flightFailedWaypoints"] = []
    state["courseChangeCooldown"] = 0
    return state["waypoints"]


def create_state(
    home,
    trap_points,
    waypoints=None,
    home_bound=False,
    route_order=None,
):
    home = [float(value) for value in home]
    trap_points = list(trap_points or ())
    if waypoints is None:
        waypoints = build_flight_route(
            home, trap_points, home_bound, route_order
        )
    return {
        "version": STATE_VERSION,
        "home": home,
        "homeBound": bool(home_bound),
        "health": MAX_HEALTH,
        "maxHealth": MAX_HEALTH,
        "phase": "normal",
        "phaseDamage": 0.0,
        "damageUntilNextPhase": FIRST_PHASE_DAMAGE_THRESHOLD,
        "attackTimer": 0,
        "prevAttackTimer": 0,
        "visualAttackTimer": 0,
        "visualAttackState": 0.0,
        "visualPitch": 0.0,
        "lastValidYaw": 0.0,
        "sourceFlightVelocity": [0.0, 0.0, 0.0],
        "motionAuthority": "source_accumulator",
        "lastPhaseTransitionReason": None,
        "nextTantrumCry": 0,
        "inTrapTicks": 0,
        "waypoints": [[float(value) for value in point] for point in waypoints],
        "waypointIndex": 0,
        "wantedWaypoint": None,
        "courseChangeCooldown": 0,
        "flightStallTicks": 0,
        "lastFlightPosition": None,
        "flightFailedWaypoints": [],
        "trapDiscoveryTicks": 0,
        "trapPruneTicks": 0,
        "trapPoints": [[float(value) for value in point] for point in trap_points],
        "participants": [],
        "ghastTrapActivated": False,
        "dying": False,
        "deathSequenceId": 0,
        "settlementId": None,
        "deathTicks": 0,
        "fallSpeed": 0.0,
        "rewardClaimed": False,
        "dropsCached": False,
        "structureConquered": False,
        "engineHealthMirror": MAX_HEALTH,
        "prematureDeathRecoveries": 0,
    }


def load_state(value):
    if not isinstance(value, dict):
        raise ValueError("Ur-Ghast state must be a mapping")
    copied = copy.deepcopy(value)
    loaded_version = int(copied.get("version", 1))
    copied["version"] = STATE_VERSION
    copied.setdefault("homeBound", False)
    copied.setdefault("maxHealth", MAX_HEALTH)
    copied.setdefault("phase", "normal")
    copied.setdefault("phaseDamage", 0.0)
    if "damageUntilNextPhase" not in copied:
        legacy_progress = max(0.0, float(copied.get("phaseDamage", 0.0)))
        copied["damageUntilNextPhase"] = max(
            0.0, PHASE_DAMAGE_THRESHOLD - legacy_progress
        )
    copied.setdefault("attackTimer", 0)
    copied.setdefault("prevAttackTimer", 0)
    copied.setdefault("visualAttackTimer", copied.get("attackTimer", 0))
    copied.setdefault("visualAttackState", 0.0)
    copied["visualAttackApplied"] = -1.0
    copied.setdefault("visualPitch", 0.0)
    copied.setdefault("lastValidYaw", 0.0)
    copied.setdefault("sourceFlightVelocity", [0.0, 0.0, 0.0])
    copied.setdefault("motionAuthority", "source_accumulator")
    copied.setdefault("lastPhaseTransitionReason", None)
    copied.setdefault("nextTantrumCry", 0)
    copied.setdefault("inTrapTicks", 0)
    copied.setdefault("courseChangeCooldown", 0)
    copied.setdefault("flightStallTicks", 0)
    copied.setdefault("lastFlightPosition", None)
    copied.setdefault("flightFailedWaypoints", [])
    copied.setdefault("trapDiscoveryTicks", 0)
    copied.setdefault("trapPruneTicks", 0)
    copied.setdefault("participants", [])
    copied.setdefault("ghastTrapActivated", False)
    copied.setdefault("dying", float(copied.get("health", MAX_HEALTH)) <= 0.0)
    copied.setdefault("deathSequenceId", 0)
    copied.setdefault("settlementId", None)
    copied.setdefault("deathTicks", 0)
    copied.setdefault("fallSpeed", 0.0)
    copied.setdefault("rewardClaimed", False)
    copied.setdefault("dropsCached", copied.get("rewardClaimed", False))
    copied.setdefault("structureConquered", copied.get("rewardClaimed", False))
    copied.setdefault(
        "engineHealthMirror", float(copied.get("health", MAX_HEALTH))
    )
    copied.setdefault("prematureDeathRecoveries", 0)
    if loaded_version < STATE_VERSION:
        copied["phaseDamage"] = max(
            0.0,
            PHASE_DAMAGE_THRESHOLD
            - float(copied.get("damageUntilNextPhase", PHASE_DAMAGE_THRESHOLD)),
        )
        copied["waypoints"] = build_flight_route(
            copied.get("home", (0, 0, 0)),
            copied.get("trapPoints", ()),
            copied.get("homeBound", False),
        )
        copied["waypointIndex"] = 0
        copied["wantedWaypoint"] = None
        copied["courseChangeCooldown"] = 0
        copied["flightStallTicks"] = 0
        copied["lastFlightPosition"] = None
        copied["flightFailedWaypoints"] = []
        try:
            source_velocity = [
                float(value) for value in copied["sourceFlightVelocity"]
            ]
        except (TypeError, ValueError):
            source_velocity = []
        if (
            len(source_velocity) != 3
            or math.sqrt(sum(value * value for value in source_velocity))
            > FLIGHT_CORRUPT_SPEED_LIMIT
        ):
            source_velocity = [0.0, 0.0, 0.0]
        copied["sourceFlightVelocity"] = source_velocity
        copied["visualAttackState"] = 0.0
        copied["visualPitch"] = 0.0
        copied["motionAuthority"] = "source_accumulator"
    else:
        copied.setdefault(
            "waypoints",
            build_flight_route(
                copied.get("home", (0, 0, 0)),
                copied.get("trapPoints", ()),
                copied.get("homeBound", False),
            ),
        )
        copied.setdefault("waypointIndex", 0)
        copied["wantedWaypoint"] = _sanitize_wanted_waypoint(
            copied, copied.get("wantedWaypoint")
        )
        copied["courseChangeCooldown"] = 0
        copied["flightStallTicks"] = 0
        copied["lastFlightPosition"] = None
        copied["flightFailedWaypoints"] = []
        try:
            source_velocity = [
                float(value) for value in copied["sourceFlightVelocity"]
            ]
        except (TypeError, ValueError):
            source_velocity = []
        if (
            len(source_velocity) != 3
            or math.sqrt(sum(value * value for value in source_velocity))
            > FLIGHT_CORRUPT_SPEED_LIMIT
        ):
            source_velocity = [0.0, 0.0, 0.0]
        copied["sourceFlightVelocity"] = source_velocity
    return copied


def create_engine_motion_state(mode="source_accumulator"):
    mode = str(mode)
    if mode not in ("source_accumulator", "direct_compat"):
        mode = "source_accumulator"
    return {
        "mode": mode,
        "failureFrames": 0,
        "movingFrames": 0,
    }


def _vector_length(vector):
    return math.sqrt(sum(float(value) * float(value) for value in vector))


def _direct_compat_motion(target_vector):
    target_vector = tuple(float(value) for value in target_vector)
    length = _vector_length(target_vector)
    if length <= 1.0e-9:
        return (0.0, 0.0, 0.0)
    return tuple(
        value / length * DIRECT_COMPAT_SPEED for value in target_vector
    )


def advance_engine_motion_adapter(
    adapter_state,
    requested_motion,
    actual_displacement,
    set_succeeded,
    target_vector,
):
    """Choose an engine-frame motion from actual movement readback."""
    mode = str(adapter_state.get("mode", "source_accumulator"))
    if mode not in ("source_accumulator", "direct_compat"):
        mode = "source_accumulator"
    requested_motion = tuple(float(value) for value in requested_motion)
    target_vector = tuple(float(value) for value in target_vector)
    requested_speed = _vector_length(requested_motion)
    target_distance = _vector_length(target_vector)
    actual_displacement = max(0.0, float(actual_displacement))
    failure = int(adapter_state.get("failureFrames", 0))
    moving = int(adapter_state.get("movingFrames", 0))
    should_move = (
        requested_speed > ENGINE_MOTION_MIN_REQUEST_SPEED
        and target_distance > FLIGHT_ARRIVAL_RADIUS
    )
    moved = actual_displacement >= ENGINE_MOTION_MIN_DISPLACEMENT

    if mode == "source_accumulator":
        if should_move and (set_succeeded is False or not moved):
            failure += 1
        else:
            failure = 0
        moving = 0
        if failure >= ENGINE_MOTION_FAILURE_FRAMES:
            mode = "direct_compat"
    else:
        failure = max(failure, ENGINE_MOTION_FAILURE_FRAMES)
        moving = moving + 1 if moved else 0
        if moving >= ENGINE_MOTION_RECOVERY_FRAMES:
            mode = "source_accumulator"
            failure = 0
            moving = 0

    motion = (
        _direct_compat_motion(target_vector)
        if mode == "direct_compat"
        else requested_motion
    )
    adapter_state["mode"] = mode
    adapter_state["failureFrames"] = failure
    adapter_state["movingFrames"] = moving
    return {
        "mode": mode,
        "failureFrames": failure,
        "movingFrames": moving,
        "motion": motion,
    }


def record_participant(state, player_id):
    player_id = str(player_id)
    participants = state.setdefault("participants", [])
    if player_id not in participants:
        participants.append(player_id)
        participants.sort()
        return True
    return False


def apply_damage(
    state,
    amount,
    player_id=None,
    bypass_tantrum=False,
    track_phase=True,
):
    amount = max(0.0, float(amount))
    if player_id is not None:
        record_participant(state, player_id)
    phase = str(state.get("phase", "normal"))
    effective = amount
    if phase == "tantrum" and not bypass_tantrum:
        effective *= TANTRUM_DAMAGE_MULTIPLIER
    state["health"] = max(0.0, float(state.get("health", MAX_HEALTH)) - effective)
    toggled = False
    if track_phase and effective > 0.0:
        remaining = float(
            state.get("damageUntilNextPhase", PHASE_DAMAGE_THRESHOLD)
        ) - effective
        if remaining <= 0.0:
            state["phase"] = "tantrum" if phase == "normal" else "normal"
            state["damageUntilNextPhase"] = PHASE_DAMAGE_THRESHOLD
            state["phaseDamage"] = 0.0
            state["lastPhaseTransitionReason"] = "accepted_damage"
            if state["phase"] == "tantrum":
                state["nextTantrumCry"] = 0
            toggled = True
        else:
            state["damageUntilNextPhase"] = remaining
            state["phaseDamage"] = max(
                0.0, PHASE_DAMAGE_THRESHOLD - remaining
            )
    if state["health"] <= 0.0 and not state.get("dying"):
        state["deathSequenceId"] = int(
            state.get("deathSequenceId", 0)
        ) + 1
        state["dying"] = True
    return {
        "accepted": effective > 0.0,
        "effectiveDamage": effective,
        "phaseToggled": toggled,
        "phaseReason": (
            "accepted_damage" if toggled else None
        ),
        "phase": state["phase"],
        "health": state["health"],
    }


def tantrum_minion_spawns(state, trap_order=None):
    if state.get("phase") != "tantrum":
        return []
    return minion_spawn_plans(state, trap_order)


def minion_spawn_plans(state, trap_order=None):
    trap_points = list(state.get("trapPoints", ()))
    if trap_order is None:
        ordered = trap_points
    else:
        ordered = [
            trap_points[int(index)]
            for index in trap_order
            if 0 <= int(index) < len(trap_points)
        ]
    return [
        {
            "position": list(point),
            "entity": "tf_slice:mini_ghast",
            "count": MINIONS_PER_TANTRUM_TRAP,
            "tries": MINION_SPAWN_TRIES,
            "horizontalRadius": MINION_SPAWN_HORIZONTAL_RADIUS,
            "verticalRange": MINION_SPAWN_VERTICAL_RANGE,
        }
        for point in ordered[:MAX_TANTRUM_TRAPS]
    ]


def fireball_volley(
    origin,
    target,
    spread_offsets=None,
    facing_yaw=None,
):
    origin = tuple(float(value) for value in origin)
    target = tuple(float(value) for value in target)
    boss_center = (
        origin[0],
        origin[1] + BOSS_HEIGHT / 2.0,
        origin[2],
    )
    dx = target[0] - boss_center[0]
    dy = target[1] - boss_center[1]
    dz = target[2] - boss_center[2]
    if facing_yaw is None:
        facing_yaw = math.degrees(math.atan2(-dx, dz))
    yaw = math.radians(float(facing_yaw))
    horizontal = math.sqrt(dx * dx + dz * dz)
    distance = math.sqrt(horizontal * horizontal + dy * dy) or 1.0
    horizontal_scale = horizontal / distance
    view = (
        -math.sin(yaw) * horizontal_scale,
        dy / distance,
        math.cos(yaw) * horizontal_scale,
    )
    right = (math.cos(yaw), 0.0, math.sin(yaw))
    spawn = [
        boss_center[0] + view[0] * FIREBALL_SPAWN_DISTANCE,
        boss_center[1] + view[1] * FIREBALL_SPAWN_DISTANCE,
        boss_center[2] + view[2] * FIREBALL_SPAWN_DISTANCE,
    ]
    spreads = list(spread_offsets or ((0.0, 0.0), (0.0, 0.0)))[:2]
    while len(spreads) < 2:
        spreads.append((0.0, 0.0))
    aims = [target]
    aims.extend(
        (
            target[0] + float(spread[0]),
            target[1],
            target[2] + float(spread[1]),
        )
        for spread in spreads
    )
    shots = []
    for index, aim in enumerate(aims):
        shot_spawn = list(spawn)
        if index == 0:
            shot_spawn[1] += 2.0
        elif index == 1:
            shot_spawn[0] += right[0] * FIREBALL_SIBLING_SEPARATION
            shot_spawn[2] += right[2] * FIREBALL_SIBLING_SEPARATION
        else:
            shot_spawn[0] -= right[0] * FIREBALL_SIBLING_SEPARATION
            shot_spawn[2] -= right[2] * FIREBALL_SIBLING_SEPARATION
        spawn_offset = tuple(
            shot_spawn[axis] - boss_center[axis] for axis in range(3)
        )
        spawn_distance = math.sqrt(
            sum(value * value for value in spawn_offset)
        ) or 1.0
        minimum_distance = BOSS_WIDTH / 2.0 + FIREBALL_RADIUS + 0.01
        if spawn_distance < minimum_distance:
            shot_spawn = [
                boss_center[axis]
                + spawn_offset[axis] / spawn_distance * minimum_distance
                for axis in range(3)
            ]
        shots.append({
            "origin": shot_spawn,
            "target": list(aim),
            "directDamage": FIREBALL_DIRECT_DAMAGE,
            "explosionPower": FIREBALL_EXPLOSION_POWER,
        })
    return shots


def reflect_fireball(projectile, player_id, look_vector):
    """Transfer one tracked fireball to a player-owned outbound flight."""
    look = tuple(float(value) for value in look_vector)
    length = math.sqrt(sum(value * value for value in look)) or 1.0
    motion = tuple(value / length * FIREBALL_REFLECT_SPEED for value in look)
    acceleration = tuple(
        value / length * FIREBALL_ACCELERATION for value in look
    )
    projectile["ownerId"] = str(player_id)
    projectile["reflected"] = True
    projectile["ignoreOwnerTicks"] = FIREBALL_OWNER_IGNORE_TICKS
    projectile["velocity"] = motion
    projectile["acceleration"] = acceleration
    return {
        "reflected": True,
        "ownerId": projectile["ownerId"],
        "motion": motion,
        "acceleration": acceleration,
        "ignoreOwnerTicks": projectile["ignoreOwnerTicks"],
        "worldCollisionGraceTicks": FIREBALL_REFLECTION_WORLD_GRACE_TICKS,
    }


def reflection_recovery_score(
    projectile_position,
    projectile_motion,
    player_eye_position,
    player_look,
):
    """Score a nearby player's melee ray for a source-less fireball hit.

    NetEase reports Ur-Ghast fireball health loss without the attacker.  By
    that callback the projectile may already have crossed the player or had
    its native motion reversed, so current approach direction cannot be an
    eligibility condition.  Recover the attacker from the short player-look
    ray instead; incoming motion remains only a tie-breaking bonus.
    """
    projectile_position = tuple(float(value) for value in projectile_position)
    projectile_motion = tuple(float(value) for value in projectile_motion)
    player_eye_position = tuple(float(value) for value in player_eye_position)
    player_look = tuple(float(value) for value in player_look)
    to_projectile = tuple(
        projectile_position[index] - player_eye_position[index]
        for index in range(3)
    )
    distance = math.sqrt(sum(value * value for value in to_projectile))
    if (
        distance <= 1.0e-6
        or distance > FIREBALL_REFLECTION_RECOVERY_MAX_DISTANCE
    ):
        return None
    look_length = math.sqrt(sum(value * value for value in player_look))
    motion_length = math.sqrt(sum(value * value for value in projectile_motion))
    if look_length <= 1.0e-6:
        return None
    look_unit = tuple(value / look_length for value in player_look)
    projection = sum(
        look_unit[index] * to_projectile[index] for index in range(3)
    )
    if (
        projection < -FIREBALL_REFLECTION_RECOVERY_BEHIND_TOLERANCE
        or projection > FIREBALL_REFLECTION_RECOVERY_MAX_DISTANCE
    ):
        return None
    ray_miss_sq = max(
        0.0,
        distance * distance - projection * projection,
    )
    ray_miss = math.sqrt(ray_miss_sq)
    if ray_miss > FIREBALL_REFLECTION_RECOVERY_RAY_RADIUS:
        return None
    distance_bonus = 1.0 - (
        distance / FIREBALL_REFLECTION_RECOVERY_MAX_DISTANCE
    )
    ray_bonus = 1.0 - (
        ray_miss / FIREBALL_REFLECTION_RECOVERY_RAY_RADIUS
    )
    approach_bonus = 0.0
    if motion_length > 1.0e-6:
        toward_player = tuple(-value / distance for value in to_projectile)
        approach_dot = sum(
            projectile_motion[index] / motion_length * toward_player[index]
            for index in range(3)
        )
        approach_bonus = max(0.0, approach_dot) * 0.25
    behind_penalty = (
        max(0.0, -projection)
        / FIREBALL_REFLECTION_RECOVERY_BEHIND_TOLERANCE
        * 0.25
    )
    return 1.0 + ray_bonus + distance_bonus + approach_bonus - behind_penalty


def create_fireball_motion(origin, target, owner_id, boss_id):
    """Create source-owned LargeFireball kinematics for one volley member."""
    origin = tuple(float(value) for value in origin)
    target = tuple(float(value) for value in target)
    direction = tuple(target[index] - origin[index] for index in range(3))
    length = math.sqrt(sum(value * value for value in direction)) or 1.0
    acceleration = tuple(
        value / length * FIREBALL_ACCELERATION for value in direction
    )
    return {
        "origin": list(origin),
        "ownerId": str(owner_id),
        "bossId": str(boss_id),
        "reflected": False,
        "velocity": (0.0, 0.0, 0.0),
        "acceleration": acceleration,
        "settled": False,
    }


def advance_fireball_motion(projectile):
    """Advance inherited hurting-projectile acceleration and inertia once."""
    velocity = tuple(
        float(value) for value in projectile.get("velocity", (0.0, 0.0, 0.0))
    )
    acceleration = tuple(
        float(value)
        for value in projectile.get("acceleration", (0.0, 0.0, 0.0))
    )
    motion = tuple(
        (velocity[index] + acceleration[index]) * FIREBALL_DRAG
        for index in range(3)
    )
    projectile["velocity"] = motion
    return {"motion": motion}


def source_motion_to_engine(motion):
    """Convert source 20 Hz displacement to a NetEase 30 Hz actor motion."""
    scale = float(SOURCE_LOGIC_HZ) / float(ENGINE_UPDATE_HZ)
    return tuple(float(value) * scale for value in motion)


def tantrum_minion_lift_motion(current_motion):
    """Apply the source +1 lift at engine cadence without runaway ascent."""
    current = tuple(float(value) for value in current_motion)
    lift = source_motion_to_engine((0.0, 1.0, 0.0))[1]
    return (
        current[0],
        min(TANTRUM_MINION_LIFT_MAX, current[1] + lift),
        current[2],
    )


def fireball_collision_decision(
    projectile, target_id, target_is_projectile, tick_count
):
    """Apply source projectile exclusions before any damage or explosion."""
    if target_is_projectile:
        return "ignore_projectile"
    if (
        not projectile.get("reflected")
        and str(target_id) == str(projectile.get("bossId"))
    ):
        return "ignore_original_boss"
    if (
        str(target_id) == str(projectile.get("ownerId"))
        and int(tick_count)
        <= int(projectile.get("ignoreOwnerUntil", -1))
    ):
        return "ignore_current_owner"
    if (
        projectile.get("reflected")
        and target_id in (None, "", -1, "-1")
        and int(tick_count)
        <= int(projectile.get("ignoreWorldUntil", -1))
    ):
        return "ignore_reflected_world_grace"
    return "impact"


def advance_attack(state, has_target, distance_sq, has_sight):
    """Advance the locked warn/fire/cooldown goal for one server tick."""
    timer = int(state.get("attackTimer", 0))
    previous = timer
    if not has_target or state.get("phase") == "tantrum":
        state["prevAttackTimer"] = timer
        state["attackTimer"] = 0
        state["visualAttackTimer"] = 0
        state["visualAttackState"] = 0.0
        return {
            "warn": False,
            "fire": False,
            "charging": False,
            "visualCharging": False,
            "tracking": False,
            "visualState": 0.0,
            "clearTarget": bool(state.get("phase") == "tantrum"),
            "timer": 0,
            "visualTimer": 0,
        }
    in_range = float(distance_sq) < ATTACK_RANGE_SQ
    if in_range and has_sight:
        timer += 1
    elif timer > 0:
        timer -= 1
    warn = timer == ATTACK_WARN_TICK
    fire = timer == ATTACK_FIRE_TICK
    visual_timer = timer
    if fire:
        previous = timer
        timer = -ATTACK_COOLDOWN_TICKS
    state["prevAttackTimer"] = previous
    state["attackTimer"] = timer
    state["visualAttackTimer"] = visual_timer
    visual_state = (
        2.0
        if ATTACK_WARN_TICK < visual_timer <= ATTACK_FIRE_TICK
        else 1.0
    )
    state["visualAttackState"] = visual_state
    return {
        "warn": warn,
        "fire": fire,
        "charging": visual_state == 2.0,
        "visualCharging": visual_state == 2.0,
        "tracking": True,
        "visualState": visual_state,
        "clearTarget": False,
        "timer": timer,
        "visualTimer": visual_timer,
    }


def attack_scale(attack_timer):
    """Return the source renderer's smooth X/Y/Z scale ratios."""
    progress = max(0.0, min(20.0, float(attack_timer))) / 20.0
    fifth = progress ** 5
    xz_scale = 1.0 + 0.08 * fifth
    y_scale = (24.0 + 1.0 / (2.0 * fifth + 1.0)) / 25.0
    return (xz_scale, y_scale, xz_scale)


def yaw_for_motion(motion, fallback_yaw=0.0):
    """Match Ghast look fallback: horizontal motion owns yaw."""
    dx = float(motion[0])
    dz = float(motion[2])
    if dx * dx + dz * dz <= 1.0e-8:
        return float(fallback_yaw)
    return math.degrees(math.atan2(-dx, dz))


def visual_pitch_degrees(origin, target, limit=COMBAT_VISUAL_PITCH_LIMIT):
    """Return a client-only positive-down pitch from mouth to target."""
    dx = float(target[0]) - float(origin[0])
    dy = float(origin[1]) - float(target[1])
    dz = float(target[2]) - float(origin[2])
    horizontal = math.sqrt(dx * dx + dz * dz)
    pitch = math.degrees(math.atan2(dy, max(horizontal, 1.0e-9)))
    return max(-float(limit), min(float(limit), pitch))


def render_yaw(logical_yaw):
    """Keep engine/model yaw aligned with the source motion/look heading."""
    return float(logical_yaw)


def player_head_separation(boss_position, player_position):
    """Move a player outside the visible head while the Boss remains noclip.

    The source Ghast ignores blocks, but NetEase's huge physical collision box
    made both navigation and melee selection unreliable.  A small player-only
    separation guard preserves block noclip without allowing the camera to
    enter the selectable head/body volume.  Tentacles intentionally remain
    non-solid and non-selectable.
    """
    if (
        boss_position is None
        or player_position is None
        or len(boss_position) != 3
        or len(player_position) != 3
    ):
        return None
    boss_x, boss_y, boss_z = (
        float(value) for value in boss_position
    )
    player_x, player_y, player_z = (
        float(value) for value in player_position
    )
    player_top = player_y + PLAYER_COLLISION_HEIGHT
    if (
        player_top <= boss_y + BOSS_HEAD_MIN_Y
        or player_y >= boss_y + BOSS_HEAD_MAX_Y
    ):
        return None
    dx = player_x - boss_x
    dz = player_z - boss_z
    boundary = BOSS_HEAD_HALF_WIDTH + PLAYER_COLLISION_RADIUS
    if abs(dx) >= boundary or abs(dz) >= boundary:
        return None
    x_penetration = boundary - abs(dx)
    z_penetration = boundary - abs(dz)
    if x_penetration <= z_penetration:
        player_x = boss_x + (boundary if dx >= 0.0 else -boundary)
    else:
        player_z = boss_z + (boundary if dz >= 0.0 else -boundary)
    return (player_x, player_y, player_z)


def authoritative_engine_health(state):
    """Keep the actor alive until the custom death sequence owns removal."""
    if state.get("dying"):
        return 1.0
    return max(1.0, float(state.get("health", MAX_HEALTH)))


def advance_tantrum(state, tick_count, cry_roll=0):
    """Return source-owned tantrum side effects for one server tick."""
    if state.get("phase") != "tantrum":
        return {
            "clearTarget": False,
            "cry": False,
            "tearDamage": False,
        }
    next_cry = int(state.get("nextTantrumCry", 0)) - 1
    cry = next_cry <= 0
    if cry:
        next_cry = TANTRUM_CRY_MIN_TICKS + (
            int(cry_roll) % TANTRUM_CRY_SPREAD
        )
    state["nextTantrumCry"] = next_cry
    return {
        "clearTarget": True,
        "cry": cry,
        "tearDamage": int(tick_count) % TANTRUM_TEAR_INTERVAL == 0,
    }


def absorb_nearby_minions(state, count):
    consumed = max(0, int(count))
    before = float(state.get("health", MAX_HEALTH))
    state["health"] = min(
        float(state.get("maxHealth", MAX_HEALTH)),
        before + consumed * MINION_ABSORB_HEAL,
    )
    return {
        "consumed": consumed,
        "healed": state["health"] - before,
        "health": state["health"],
    }


def waypoint_needs_refresh(position, wanted):
    if wanted is None or len(wanted) != 3:
        return True
    distance_sq = sum(
        (float(wanted[index]) - float(position[index])) ** 2
        for index in range(3)
    )
    return distance_sq < 1.0 or distance_sq > 3600.0


def select_next_waypoint(state):
    waypoints = state.get("waypoints") or [state.get("home", (0, 0, 0))]
    index = int(state.get("waypointIndex", 0)) % len(waypoints)
    point = list(waypoints[index])
    next_index = (index + 1) % len(waypoints)
    state["waypointIndex"] = next_index
    return {
        "point": point,
        "cycleCompleted": next_index == 0,
    }


def select_recovery_waypoint(state, position, wanted):
    """Choose a same-band route alternative; never synthesize upward drift."""
    waypoints = list(state.get("waypoints") or ())
    failed = list(state.get("flightFailedWaypoints") or ())
    wanted_key = tuple(round(float(value), 6) for value in wanted)
    if wanted_key not in failed:
        failed.append(wanted_key)
    state["flightFailedWaypoints"] = failed
    start = int(state.get("waypointIndex", 0)) % max(1, len(waypoints))
    for offset in range(len(waypoints)):
        index = (start + offset) % len(waypoints)
        candidate = [float(value) for value in waypoints[index]]
        candidate_key = tuple(round(value, 6) for value in candidate)
        if candidate_key in failed:
            continue
        state["waypointIndex"] = (index + 1) % len(waypoints)
        state["wantedWaypoint"] = candidate
        return candidate

    home = state.get("home") or position
    dx = float(home[0]) - float(position[0])
    dz = float(home[2]) - float(position[2])
    horizontal = math.sqrt(dx * dx + dz * dz)
    if horizontal <= 1.0e-9:
        dx, dz, horizontal = 1.0, 0.0, 1.0
    floor_y, ceiling_y = flight_altitude_bounds(state)
    candidate = [
        float(position[0]) + dx / horizontal * 8.0,
        max(floor_y, min(ceiling_y, float(position[1]))),
        float(position[2]) + dz / horizontal * 8.0,
    ]
    state["flightFailedWaypoints"] = []
    state["wantedWaypoint"] = candidate
    return candidate


def advance_flight_motion(
    state,
    position,
    wanted,
    current_motion,
    cooldown_roll,
):
    """Advance source cadence plus explicit Bedrock-owned flight physics."""
    previous_motion = tuple(float(value) for value in current_motion)
    motion = previous_motion
    cooldown = int(state.get("courseChangeCooldown", 0)) - 1
    accelerated = False
    floor_y, ceiling_y = flight_altitude_bounds(state)
    wanted = [float(value) for value in wanted]
    wanted[1] = max(floor_y, min(ceiling_y, wanted[1]))
    if state.get("wantedWaypoint") is not None:
        state["wantedWaypoint"] = list(wanted)
    dx = float(wanted[0]) - float(position[0])
    dy = float(wanted[1]) - float(position[1])
    dz = float(wanted[2]) - float(position[2])
    distance = math.sqrt(dx * dx + dy * dy + dz * dz)
    if distance <= FLIGHT_ARRIVAL_RADIUS:
        motion = (0.0, 0.0, 0.0)
        cooldown = 0
        state["courseChangeCooldown"] = cooldown
        state["flightStallTicks"] = 0
        state["flightFailedWaypoints"] = []
        state["lastFlightPosition"] = [float(value) for value in position]
        return {
            "motion": motion,
            "accelerated": False,
            "arrived": True,
            "reselectWaypoint": False,
            "motionChanged": motion != previous_motion,
            "courseChangeCooldown": cooldown,
        }
    last_position = state.get("lastFlightPosition")
    if last_position is not None and len(last_position) == 3:
        moved_sq = sum(
            (float(position[index]) - float(last_position[index])) ** 2
            for index in range(3)
        )
        if moved_sq <= FLIGHT_STALL_DISTANCE_SQ:
            state["flightStallTicks"] = int(
                state.get("flightStallTicks", 0)
            ) + 1
        else:
            state["flightStallTicks"] = 0
    state["lastFlightPosition"] = [float(value) for value in position]
    if int(state.get("flightStallTicks", 0)) >= FLIGHT_STALL_TICKS:
        recovery_waypoint = select_recovery_waypoint(
            state, position, wanted
        )
        state["flightStallTicks"] = 0
        state["courseChangeCooldown"] = 0
        return {
            "motion": (0.0, 0.0, 0.0),
            "accelerated": False,
            "arrived": False,
            "reselectWaypoint": True,
            "recoveryWaypoint": recovery_waypoint,
            "motionChanged": previous_motion != (0.0, 0.0, 0.0),
            "courseChangeCooldown": 0,
        }
    # The source control adds acceleration to the existing delta movement;
    # Java travel applies drag afterward.  NetEase SetMotion does not provide
    # that inherited travel step consistently, so the adapter owns it here.
    if sum(
        motion[index] * (dx, dy, dz)[index] for index in range(3)
    ) < 0.0:
        # The actor crossed the wanted point.  Discard the away-facing impulse
        # instead of spending several seconds oscillating around a 14x18 AABB.
        motion = (0.0, 0.0, 0.0)
    if cooldown <= 0:
        cooldown = FLIGHT_COURSE_COOLDOWN_MIN + (
            int(cooldown_roll) % FLIGHT_COURSE_COOLDOWN_SPREAD
        )
        acceleration = FLIGHT_ACCELERATION
        motion = (
            motion[0] + dx / distance * acceleration,
            motion[1] + dy / distance * acceleration,
            motion[2] + dz / distance * acceleration,
        )
        accelerated = True

    motion = tuple(value * FLIGHT_DRAG for value in motion)
    speed = math.sqrt(sum(value * value for value in motion))
    if speed > FLIGHT_CORRUPT_SPEED_LIMIT:
        scale = FLIGHT_CORRUPT_SPEED_LIMIT / speed
        motion = tuple(value * scale for value in motion)
    position_y = float(position[1])
    next_y = position_y + motion[1]
    if position_y > ceiling_y:
        motion = (
            motion[0],
            min(0.0, motion[1]),
            motion[2],
        )
    elif position_y < floor_y:
        motion = (
            motion[0],
            max(0.0, motion[1]),
            motion[2],
        )
    elif next_y > ceiling_y:
        motion = (motion[0], ceiling_y - position_y, motion[2])
    elif next_y < floor_y:
        motion = (motion[0], floor_y - position_y, motion[2])
    state["courseChangeCooldown"] = cooldown
    return {
        "motion": motion,
        "accelerated": accelerated,
        "arrived": False,
        "reselectWaypoint": False,
        "motionChanged": any(
            abs(motion[index] - previous_motion[index]) > 1.0e-9
            for index in range(3)
        ),
        "courseChangeCooldown": cooldown,
    }


def create_trap_state(position):
    return {
        "position": [float(value) for value in position],
        "deathIds": [],
        "deathCount": 0,
        "charged": False,
        "active": False,
        "redstonePowered": False,
        "nextPowerCheckTick": 0,
        "activeTicks": 0,
        "activationCount": 0,
        "effectStage": "idle",
    }


def _trap_position(trap):
    position = trap.get("position") if isinstance(trap, dict) else trap
    if position is None or len(position) != 3:
        return None
    return tuple(float(value) for value in position)


def resolve_death_position(event_position, tracked_position=None):
    """Return a death position even after the actor has left the world."""
    for position in (event_position, tracked_position):
        if position is not None and len(position) == 3:
            return tuple(float(value) for value in position)
    return None


def resolve_death_entity_type(event_type, engine_type, tracked_state=None):
    """Resolve an actor type after MobDieEvent has removed the live entity.

    NetEase may omit ``engineTypeStr`` and make the actor component unreadable
    before the death callback runs.  The temporal mob registry is populated
    while the actor is alive, so its recorded type is the durable final
    fallback used by the ghast-trap charge path.
    """
    tracked_type = (
        tracked_state.get("type")
        if isinstance(tracked_state, dict)
        else None
    )
    for value in (event_type, engine_type, tracked_type):
        if value:
            return str(value)
    return None


def trap_accepts_mini_ghast_death(trap, entity_position):
    """Match the source trap's 10x16x10 inactive charge scan box."""
    position = _trap_position(trap)
    if position is None or entity_position is None or len(entity_position) != 3:
        return False
    dx = float(entity_position[0]) - position[0]
    dy = float(entity_position[1]) - position[1]
    dz = float(entity_position[2]) - position[2]
    return (
        -TRAP_CHARGE_HORIZONTAL_RADIUS <= dx <= TRAP_CHARGE_HORIZONTAL_RADIUS
        and -TRAP_CHARGE_VERTICAL_RADIUS <= dy <= TRAP_CHARGE_VERTICAL_RADIUS
        and -TRAP_CHARGE_HORIZONTAL_RADIUS <= dz <= TRAP_CHARGE_HORIZONTAL_RADIUS
    )


def trap_affects_entity(trap, entity_position):
    """Match the source active box: six blocks sideways and 32 upward."""
    if not trap.get("active"):
        return False
    position = _trap_position(trap)
    if position is None or entity_position is None or len(entity_position) != 3:
        return False
    dx = float(entity_position[0]) - position[0]
    dy = float(entity_position[1]) - position[1]
    dz = float(entity_position[2]) - position[2]
    return (
        -TRAP_ACTIVE_HORIZONTAL_RADIUS <= dx <= TRAP_ACTIVE_HORIZONTAL_RADIUS
        and 0.0 <= dy <= TRAP_ACTIVE_HEIGHT
        and -TRAP_ACTIVE_HORIZONTAL_RADIUS <= dz <= TRAP_ACTIVE_HORIZONTAL_RADIUS
    )


def record_mini_ghast_death(trap, entity_id):
    entity_id = str(entity_id)
    death_ids = trap.setdefault("deathIds", [])
    if entity_id in death_ids:
        return False
    death_ids.append(entity_id)
    trap["deathCount"] = min(
        TRAP_DEATHS_TO_CHARGE,
        int(trap.get("deathCount", 0)) + 1,
    )
    trap["charged"] = trap["deathCount"] >= TRAP_DEATHS_TO_CHARGE
    return True


def record_mini_ghast_death_for_traps(traps, entity_id, entity_position):
    """Credit one death independently to every matching inactive trap."""
    updated = []
    for trap in traps or ():
        if trap.get("active"):
            continue
        if not trap_accepts_mini_ghast_death(trap, entity_position):
            continue
        if record_mini_ghast_death(trap, entity_id):
            updated.append(trap)
    return updated


def activate_trap(trap, ur_ghast_state=None):
    """Start a charged trap even when no Ghast is currently in its beam."""
    if not trap.get("charged") or trap.get("active"):
        return {"activated": False, "pull": False, "damage": 0.0}
    trap["charged"] = False
    trap["active"] = True
    trap["deathCount"] = 0
    trap["deathIds"] = []
    trap["activeTicks"] = 0
    trap["activationCount"] = int(trap.get("activationCount", 0)) + 1
    trap["effectStage"] = "warmup"
    return {
        "activated": True,
        "pull": True,
        "pullRadius": TRAP_ACTIVE_HORIZONTAL_RADIUS,
        "damage": 0.0,
    }


def advance_trap(trap, ticks=1):
    """Advance the 120-tick source activation window."""
    advanced = 0
    for _unused in range(max(0, int(ticks))):
        if not trap.get("active"):
            break
        trap["activeTicks"] = int(trap.get("activeTicks", 0)) + 1
        advanced += 1
        if trap["activeTicks"] >= TRAP_ACTIVE_TICKS:
            trap["active"] = False
            trap["activeTicks"] = 0
            break
    return {
        "active": bool(trap.get("active")),
        "advanced": advanced,
    }


def trap_pull_motion(trap, entity_position, boss=True):
    position = _trap_position(trap)
    if position is None:
        return (0.0, 0.0, 0.0)
    target_y = position[1] + (2.5 if boss else 1.5)
    return (
        (float(entity_position[0]) - position[0] - 0.5) * TRAP_PULL_SCALE,
        (float(entity_position[1]) - target_y) * TRAP_PULL_SCALE,
        (float(entity_position[2]) - position[2] - 0.5) * TRAP_PULL_SCALE,
    )


def apply_active_trap_to_ur_ghast(
    trap,
    ur_ghast_state,
    entity_position,
    deal_damage=False,
):
    """Apply one active trap tick to an Ur-Ghast inside the source AABB."""
    if not trap_affects_entity(trap, entity_position):
        return {
            "affected": False,
            "motion": (0.0, 0.0, 0.0),
            "damage": 0.0,
        }
    ur_ghast_state["ghastTrapActivated"] = True
    ur_ghast_state["inTrapTicks"] = 20
    ur_ghast_state["phase"] = "normal"
    ur_ghast_state["phaseDamage"] = 0.0
    ur_ghast_state["damageUntilNextPhase"] = PHASE_DAMAGE_THRESHOLD
    ur_ghast_state["lastPhaseTransitionReason"] = "active_trap_pull"
    damage = 0.0
    if deal_damage:
        result = apply_damage(
            ur_ghast_state,
            TRAP_UR_GHAST_DAMAGE,
            bypass_tantrum=True,
            track_phase=False,
        )
        damage = result["effectiveDamage"]
    return {
        "affected": True,
        "motion": trap_pull_motion(trap, entity_position, True),
        "damage": damage,
    }


def apply_active_trap_to_ghast(trap, entity_position, deal_damage=False):
    """Apply the active beam to ordinary and carminite ghasts."""
    if not trap_affects_entity(trap, entity_position):
        return {
            "affected": False,
            "motion": (0.0, 0.0, 0.0),
            "damage": 0.0,
        }
    return {
        "affected": True,
        "motion": trap_pull_motion(trap, entity_position, False),
        "damage": TRAP_OTHER_GHAST_DAMAGE if deal_damage else 0.0,
    }


def next_waypoint(state):
    return select_next_waypoint(state)["point"]


def advance_death_sequence(state, ticks=1):
    """Advance the source 90-tick presentation without moving the Boss."""
    state["dying"] = True
    for _unused in range(max(0, int(ticks))):
        state["deathTicks"] = int(state.get("deathTicks", 0)) + 1
    death_ticks = int(state.get("deathTicks", 0))
    if death_ticks <= DEATH_BURST_TICKS:
        stage = "burst"
    elif death_ticks < DEATH_SEQUENCE_TICKS:
        stage = "trail"
    else:
        stage = "complete"
    return {
        "stage": stage,
        "deathTicks": death_ticks,
        "complete": death_ticks >= DEATH_SEQUENCE_TICKS,
    }


def death_trail_position(position, reward_position, death_ticks):
    """Follow the source's final two-thirds trail toward the reward chest."""
    elapsed = max(1, int(death_ticks) - DEATH_BURST_TICKS + 1)
    duration = max(1, DEATH_SEQUENCE_TICKS - DEATH_BURST_TICKS)
    factor = min(1.0, float(elapsed) / float(duration))
    return tuple(
        float(position[index])
        + (float(reward_position[index]) - float(position[index])) * factor
        for index in range(3)
    )


def claim_reward(state):
    if float(state.get("health", MAX_HEALTH)) > 0.0 or state.get("rewardClaimed"):
        return False
    state["rewardClaimed"] = True
    state["settlementId"] = int(state.get("deathSequenceId", 0))
    state["dropsCached"] = True
    state["structureConquered"] = True
    return True


def final_progress_players(state):
    if float(state.get("health", MAX_HEALTH)) > 0.0:
        return []
    return sorted(set(str(value) for value in state.get("participants", ())))
