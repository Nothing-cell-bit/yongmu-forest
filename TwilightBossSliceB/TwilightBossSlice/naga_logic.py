# -*- coding: utf-8 -*-
"""Pure, deterministic Naga combat rules ported from Twilight Forest 4.3.2508.

This module deliberately has no ModSDK imports so the state machine can be
tested on desktop Python while remaining compatible with the mobile Python 2
runtime.
"""

import math
import random


INTIMIDATE = "intimidate"
CRUMBLE = "crumble"
CHARGE = "charge"
STUNLESS_CHARGE = "stunless_charge"
CIRCLE = "circle"
DAZE = "daze"

BASE_HEALTH = 120.0
NORMAL_HEALTH_BONUS = 80.0
HARD_HEALTH_BONUS = 130.0
BASE_ATTACK_DAMAGE = 5.0
BODY_ATTACK_DAMAGE = 2.0
MAX_SEGMENTS = 12
MIN_LIVING_SEGMENTS = 2
BASE_SPEED = 0.5
HOME_XZ_BOUNDS = 46.0
HOME_Y_BOUNDS = 7.0
TICKS_BEFORE_HEALING = 600
STUN_DAMAGE_LIMIT = 15.0
SEGMENT_SPACING = 2.0
SEGMENT_DESTRUCTION_DELAY = 12
DEATH_ANIMATION_TICKS = 24
DEATH_PARTICLE_TICKS = 120
DEATH_TICKS = DEATH_ANIMATION_TICKS + DEATH_PARTICLE_TICKS
XP_REWARD = 217
INITIAL_CIRCLE_WAYPOINTS = 8
CIRCLE_WAYPOINTS_MIN = 7
CIRCLE_WAYPOINTS_VARIANCE = 2
COMBAT_WAYPOINT_TOLERANCE = 3.0
DAZE_RECOIL_TICKS = 4
MAX_TURN_DEGREES = 15.0
SHIELD_PLAYER_RECOIL_SCALE = 3.0
SHIELD_PLAYER_RECOIL_Y = 0.75
SHIELD_NAGA_RECOIL_SCALE = -1.25
SHIELD_NAGA_RECOIL_Y = 0.5
CHARGE_CONTACT_HOLD_TICKS = 4
SHIELD_SEPARATION_DISTANCE = 2.25
IDLE_PATROL_RADIUS = 12.0
IDLE_PATROL_POINT_COUNT = 8
IDLE_PATROL_PAUSE_TICKS = 1
IDLE_PATROL_REACHED_DISTANCE = COMBAT_WAYPOINT_TOLERANCE


def clamp(value, lower, upper):
    return max(lower, min(upper, value))


def max_health_for_difficulty(difficulty):
    if int(difficulty) >= 3:
        return BASE_HEALTH + HARD_HEALTH_BONUS
    if int(difficulty) >= 2:
        return BASE_HEALTH + NORMAL_HEALTH_BONUS
    return BASE_HEALTH


def head_damage_for_difficulty(difficulty):
    """The Java Naga's attack attribute is a fixed five damage."""
    return BASE_ATTACK_DAMAGE


def body_damage_for_difficulty(difficulty):
    """A Naga body part always deals two collision damage."""
    return BODY_ATTACK_DAMAGE


def segment_collision_damage(is_animal):
    """Match the original NagaSegment collision damage."""
    return 6.0 if bool(is_animal) else 2.0


def segment_count(health, max_health):
    health = max(0.0, float(health))
    max_health = max(1.0, float(max_health))
    if health <= 0.0:
        return 0
    # Naga constructs this value before the per-difficulty max-health bonus
    # is applied.  It therefore stays 120 / 10 on Easy, Normal, and Hard.
    health_per_segment = BASE_HEALTH / 10.0
    return int(clamp(int(health / health_per_segment) + 2, 0, MAX_SEGMENTS))


def attack_reach_squared(naga_width, target_width):
    """Port SimplifiedAttackGoal#getAttackReachSqr exactly."""
    width = max(0.0, float(naga_width))
    return width * width * 4.0 + max(0.0, float(target_width))


def melee_push_vector(yaw, power=2.0):
    angle = math.radians(float(yaw))
    return (-math.sin(angle) * float(power), math.cos(angle) * float(power))


def shield_recoil_motions(boss_motion, target_motion):
    """Return the visible source throw and the Naga's upward back-bounce."""
    try:
        boss = tuple(float(value) for value in boss_motion)
        target = tuple(float(value) for value in target_motion)
    except (TypeError, ValueError):
        return (
            (0.0, SHIELD_PLAYER_RECOIL_Y, 0.0),
            (0.0, SHIELD_NAGA_RECOIL_Y, 0.0),
        )
    player = (
        target[0] + boss[0] * SHIELD_PLAYER_RECOIL_SCALE,
        target[1] + SHIELD_PLAYER_RECOIL_Y,
        target[2] + boss[2] * SHIELD_PLAYER_RECOIL_SCALE,
    )
    naga = (
        boss[0] + boss[0] * SHIELD_NAGA_RECOIL_SCALE,
        boss[1] + SHIELD_NAGA_RECOIL_Y,
        boss[2] + boss[2] * SHIELD_NAGA_RECOIL_SCALE,
    )
    return player, naga


def shield_separation_position(
    boss_pos,
    target_pos,
    distance=SHIELD_SEPARATION_DISTANCE,
    fallback_direction=(0.0, 1.0),
):
    """Place a blocking player a fixed safe distance in front of the head."""
    try:
        boss = tuple(float(value) for value in boss_pos)
        target = tuple(float(value) for value in target_pos)
        dx = target[0] - boss[0]
        dz = target[2] - boss[2]
        length = math.sqrt(dx * dx + dz * dz)
        if length < 0.0001:
            dx = float(fallback_direction[0])
            dz = float(fallback_direction[1])
            length = math.sqrt(dx * dx + dz * dz)
        if length < 0.0001:
            dx, dz, length = 0.0, 1.0, 1.0
        direction = (dx / length, dz / length)
        separation = max(0.0, float(distance))
    except (TypeError, ValueError, IndexError):
        return (target_pos, (0.0, 1.0))
    return (
        (
            boss[0] + direction[0] * separation,
            target[1],
            boss[2] + direction[1] * separation,
        ),
        direction,
    )


def collision_boxes_overlap(first_pos, first_size, second_pos, second_size):
    """Return whether two feet-anchored entity AABBs intersect."""
    try:
        first_half = max(0.0, float(first_size[0])) * 0.5
        second_half = max(0.0, float(second_size[0])) * 0.5
        first_height = max(0.0, float(first_size[1]))
        second_height = max(0.0, float(second_size[1]))
        horizontal_reach = first_half + second_half
        return (
            abs(float(first_pos[0]) - float(second_pos[0]))
            < horizontal_reach
            and abs(float(first_pos[2]) - float(second_pos[2]))
            < horizontal_reach
            and float(first_pos[1])
            < float(second_pos[1]) + second_height
            and float(first_pos[1]) + first_height
            > float(second_pos[1])
        )
    except (TypeError, ValueError, IndexError):
        return False


def speed_for_segments(segments):
    segments = max(MIN_LIVING_SEGMENTS, int(segments))
    return BASE_SPEED + (float(MAX_SEGMENTS) / float(segments) * 0.02)


def scaled_navigation_speed(base_speed, segments):
    """Apply the locked segment-count speed ratio to any path state."""
    try:
        speed = max(0.0, float(base_speed))
    except (TypeError, ValueError):
        return 0.0
    return speed * (
        speed_for_segments(segments) / speed_for_segments(MAX_SEGMENTS)
    )


def stunless_chance(health, max_health, difficulty):
    health = max(0.0, float(health))
    max_health = max(1.0, float(max_health))
    health_ratio = 1.0 - (health / max_health) - 0.25
    return clamp(health_ratio + int(difficulty) * 0.05, 0.0, 0.5)


def choose_stunless(health, max_health, difficulty, rng):
    return float(rng.random()) * 0.75 < stunless_chance(
        health, max_health, difficulty
    )


def circle_point(naga_pos, target_pos, clockwise, radius, rotation):
    vec_x = float(naga_pos[0]) - float(target_pos[0])
    vec_z = float(naga_pos[2]) - float(target_pos[2])
    angle = math.atan2(vec_z, vec_x)
    angle += float(rotation) if clockwise else -float(rotation)
    return (
        float(target_pos[0]) + math.cos(angle) * float(radius),
        min(float(naga_pos[1]), float(target_pos[1])),
        float(target_pos[2]) + math.sin(angle) * float(radius),
    )


def target_is_above_naga(naga_feet_y, target_feet_y):
    return float(target_feet_y) > float(naga_feet_y) + 3.0


def head_clear_positions(
    boss_pos,
    destroy_all=False,
    max_blocks=None,
):
    """Return the original Naga's expanded head AABB as block positions.

    The Java entity expands its 2 x 3 collision box by 0.75 blocks
    horizontally and one block upward.  Destructive smash scans start just
    above the feet so a charging Naga cannot remove its supporting floor.
    """
    center_x = float(boss_pos[0])
    feet_y = float(boss_pos[1])
    center_z = float(boss_pos[2])
    horizontal_radius = 2.0 * 0.5 + 0.75
    min_x = int(math.floor(center_x - horizontal_radius))
    max_x = int(math.floor(center_x + horizontal_radius))
    min_y = int(math.floor(feet_y + (1.01 if destroy_all else 0.5)))
    max_y = int(math.floor(feet_y + 3.0 + 1.0))
    min_z = int(math.floor(center_z - horizontal_radius))
    max_z = int(math.floor(center_z + horizontal_radius))

    positions = [
        (x, y, z)
        for y in range(min_y, max_y + 1)
        for x in range(min_x, max_x + 1)
        for z in range(min_z, max_z + 1)
    ]
    if max_blocks is None:
        return positions
    try:
        limit = max(0, int(max_blocks))
    except (TypeError, ValueError):
        return positions
    return positions[:limit]


def inside_home(pos, home):
    return (
        abs(float(home[0]) - float(pos[0])) <= HOME_XZ_BOUNDS
        and abs(float(home[1]) - float(pos[1])) <= HOME_Y_BOUNDS
        and abs(float(home[2]) - float(pos[2])) <= HOME_XZ_BOUNDS
    )


def courtyards_overlap(first_home, second_home):
    """Return whether two original-sized courtyard boxes intersect."""
    if first_home is None or second_home is None:
        return False
    return (
        abs(float(first_home[0]) - float(second_home[0]))
        <= HOME_XZ_BOUNDS * 2.0
        and abs(float(first_home[1]) - float(second_home[1]))
        <= HOME_Y_BOUNDS * 2.0
        and abs(float(first_home[2]) - float(second_home[2]))
        <= HOME_XZ_BOUNDS * 2.0
    )


def navigation_succeeded(result):
    """ModSDK MoveTo reports 0 only when the destination was reached."""
    if result is None:
        return False
    try:
        return int(result) == 0
    except (TypeError, ValueError):
        return False


def navigation_failed(result):
    """Treat every non-zero MoveTo result as failed or interrupted."""
    if result is None:
        return False
    try:
        return int(result) != 0
    except (TypeError, ValueError):
        return True


def navigation_finished(result):
    """Return whether ModSDK reached the requested destination.

    Results 1..3 end a MoveTo request without reaching its destination.  They
    must remain retryable instead of consuming one of the Naga's orbit or
    charge waypoints.
    """
    return navigation_succeeded(result)


def path_step_finished(distance, naga_width):
    """Match the Naga's early PathNavigation node advancement.

    The Java boss advances its current path while the next node is less than
    four collision widths away.  ModSDK does not expose individual path
    nodes, so its combat waypoint is the closest equivalent.
    """
    try:
        remaining = max(0.0, float(distance))
        width = max(0.0, float(naga_width))
    except (TypeError, ValueError):
        return False
    return width > 0.0 and remaining < width * 4.0


def combat_waypoint_reached(
    distance, tolerance=COMBAT_WAYPOINT_TOLERANCE
):
    """Return whether the final orbit or charge destination was reached.

    The Java ``width * 4`` rule skips intermediate path nodes.  ModSDK exposes
    only the final MoveTo destination, so applying that rule to the waypoint
    itself cuts the 12/14-block orbit inward by as much as eight blocks.
    """
    try:
        remaining = max(0.0, float(distance))
        arrival = max(0.0, float(tolerance))
    except (TypeError, ValueError):
        return False
    return remaining <= arrival


def step_yaw(current_yaw, target_yaw, maximum_delta=MAX_TURN_DEGREES):
    """Turn toward a target yaw along the shortest rate-limited arc."""
    try:
        current = float(current_yaw)
        target = float(target_yaw)
        limit = max(0.0, float(maximum_delta))
    except (TypeError, ValueError):
        return current_yaw
    delta = (target - current + 180.0) % 360.0 - 180.0
    if abs(delta) <= limit:
        result = target
    else:
        result = current + (limit if delta > 0.0 else -limit)
    return (result + 180.0) % 360.0 - 180.0


def daze_recoil_finished(current_tick, stop_tick):
    try:
        return int(current_tick) >= int(stop_tick)
    except (TypeError, ValueError):
        return True


def update_navigation_progress(
    best_distance,
    current_distance,
    stalled_ticks,
    tick_step,
    minimum_progress,
):
    """Track meaningful progress toward one fixed navigation waypoint."""
    try:
        current = max(0.0, float(current_distance))
        stalled = max(0, int(stalled_ticks))
        step = max(0, int(tick_step))
        threshold = max(0.0, float(minimum_progress))
    except (TypeError, ValueError):
        return (best_distance, stalled_ticks)
    if best_distance is None:
        return (current, 0)
    try:
        best = max(0.0, float(best_distance))
    except (TypeError, ValueError):
        return (current, 0)
    if current <= best - threshold:
        return (current, 0)
    return (best, stalled + step)


def should_destroy_block(
    block_name,
    state,
    mob_griefing,
    outside_home=False,
    protected=False,
    targeted_crumble=False,
):
    """Match Naga griefing: leaves normally, solid blocks while smashing."""
    if not mob_griefing or protected or not block_name:
        return False
    lowered = str(block_name).lower()
    if "leaves" in lowered or lowered.endswith("_leaf"):
        return True
    return bool(
        outside_home
        or state in (CHARGE, STUNLESS_CHARGE)
        or (state == CRUMBLE and targeted_crumble)
    )


def naga_damage_is_blocked(
    cause,
    attacker_inside=None,
    direct_inside=None,
):
    """Match Naga.isInvulnerableTo for the source data ModSDK exposes.

    ``None`` means that no corresponding source entity was supplied.  A
    source or direct projectile outside the courtyard blocks the hit, while
    environmental damage is still allowed.  Explosions are always blocked.
    """
    if "explosion" in str(cause or "").lower():
        return True
    return attacker_inside is False or direct_inside is False


def nearest_target(origin, candidates, max_distance):
    """Return the nearest candidate id with deterministic tie-breaking."""
    limit_sq = max(0.0, float(max_distance)) ** 2
    best_id = None
    best_key = None
    for target_id, pos in candidates:
        if target_id is None or pos is None:
            continue
        try:
            dx = float(pos[0]) - float(origin[0])
            dy = float(pos[1]) - float(origin[1])
            dz = float(pos[2]) - float(origin[2])
        except (TypeError, ValueError, IndexError):
            continue
        distance_sq = dx * dx + dy * dy + dz * dz
        if distance_sq > limit_sq:
            continue
        key = (distance_sq, str(target_id))
        if best_key is None or key < best_key:
            best_key = key
            best_id = target_id
    return best_id


def _normalize_vector(vector):
    length = math.sqrt(
        float(vector[0]) ** 2
        + float(vector[1]) ** 2
        + float(vector[2]) ** 2
    )
    if length < 0.000001:
        return (0.0, 0.0, 0.0)
    return (
        float(vector[0]) / length,
        float(vector[1]) / length,
        float(vector[2]) / length,
    )


def segment_spawn_position(
    leader_pos, leader_yaw, spacing=SEGMENT_SPACING
):
    """Place a new segment behind its leader in Minecraft yaw space."""
    angle = math.radians(float(leader_yaw))
    return (
        float(leader_pos[0]) + math.sin(angle) * float(spacing),
        float(leader_pos[1]),
        float(leader_pos[2]) - math.cos(angle) * float(spacing),
    )


def segment_pose_offsets(head_pos, segment_positions):
    """Snapshot an existing curved body pose relative to the head."""
    try:
        head = tuple(float(value) for value in head_pos)
    except (TypeError, ValueError):
        return []
    offsets = []
    for position in segment_positions:
        if position is None:
            offsets.append(None)
            continue
        try:
            offsets.append(
                (
                    float(position[0]) - head[0],
                    float(position[1]) - head[1],
                    float(position[2]) - head[2],
                )
            )
        except (TypeError, ValueError, IndexError):
            offsets.append(None)
    return offsets


def segment_pose_positions(head_pos, offsets):
    """Restore a curved body pose around the head's current position."""
    try:
        head = tuple(float(value) for value in head_pos)
    except (TypeError, ValueError):
        return []
    positions = []
    for offset in offsets:
        if offset is None:
            positions.append(None)
            continue
        try:
            positions.append(
                (
                    head[0] + float(offset[0]),
                    head[1] + float(offset[1]),
                    head[2] + float(offset[2]),
                )
            )
        except (TypeError, ValueError, IndexError):
            positions.append(None)
    return positions


def is_segment_support_block(block_name):
    """Return whether a block can act as solid support for a body segment."""
    if not block_name:
        return False
    lowered = str(block_name).lower()
    if lowered in (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "minecraft:water",
        "minecraft:flowing_water",
        "minecraft:lava",
        "minecraft:flowing_lava",
        "minecraft:fire",
        "minecraft:soul_fire",
        "minecraft:tallgrass",
        "minecraft:double_plant",
        "minecraft:seagrass",
    ):
        return False
    non_support_suffixes = (
        "_flower",
        "_sapling",
        "_mushroom",
        "_vine",
        "_fern",
        "_bush",
        "_roots",
    )
    return not lowered.endswith(non_support_suffixes)


def follow_segment(
    leader_pos,
    leader_yaw,
    segment_pos,
    segment_index,
    on_ground=False,
    alive=True,
):
    """Port Naga.moveSegments for gravityless ModSDK segment entities."""
    index = max(0, int(segment_index))
    straighten = 0.05 + (0.5 / float(index + 1))
    if not alive:
        straighten = 0.0
    angle = math.radians(float(leader_yaw) + 180.0)
    ideal_x = -math.sin(angle) * straighten
    ideal_z = math.cos(angle) * straighten
    # NagaSegment#isInWall raises the ideal follow point by two blocks.
    ideal_y = 2.0 * straighten if on_ground else 0.0

    difference = _normalize_vector(
        (
            float(segment_pos[0]) - float(leader_pos[0]),
            float(segment_pos[1]) - float(leader_pos[1]),
            float(segment_pos[2]) - float(leader_pos[2]),
        )
    )
    difference = _normalize_vector(
        (
            difference[0] + ideal_x,
            difference[1] + ideal_y,
            difference[2] + ideal_z,
        )
    )
    if difference == (0.0, 0.0, 0.0):
        difference = (
            math.sin(math.radians(float(leader_yaw))),
            0.0,
            -math.cos(math.radians(float(leader_yaw))),
        )
    destination = (
        float(leader_pos[0]) + difference[0] * SEGMENT_SPACING,
        float(leader_pos[1]) + difference[1] * SEGMENT_SPACING,
        float(leader_pos[2]) + difference[2] * SEGMENT_SPACING,
    )
    horizontal = math.sqrt(
        difference[0] * difference[0]
        + difference[2] * difference[2]
    )
    yaw = math.degrees(math.atan2(difference[2], difference[0])) + 90.0
    pitch = -math.degrees(math.atan2(difference[1], horizontal))
    return destination, yaw, pitch


def short_chain_should_hold(
    segment_count,
    previous_head_pos,
    current_head_pos,
    state,
    movement_threshold=0.075,
):
    """Keep a short chain from orbiting a head that only turns in place."""
    try:
        count = int(segment_count)
        if count <= 0 or count > 3 or previous_head_pos is None:
            return False
        if state in (CHARGE, STUNLESS_CHARGE):
            return False
        dx = float(current_head_pos[0]) - float(previous_head_pos[0])
        dz = float(current_head_pos[2]) - float(previous_head_pos[2])
        threshold = max(0.0, float(movement_threshold))
    except (TypeError, ValueError, IndexError):
        return False
    return dx * dx + dz * dz < threshold * threshold


def idle_patrol_point(home, waypoint_index):
    """Return a bounded loop point for the NetEase no-target presentation."""
    try:
        origin = tuple(float(value) for value in home)
        index = int(waypoint_index) % IDLE_PATROL_POINT_COUNT
    except (TypeError, ValueError):
        return None
    if len(origin) < 3:
        return None
    angle = math.pi * 2.0 * index / float(IDLE_PATROL_POINT_COUNT)
    return (
        origin[0] + math.cos(angle) * IDLE_PATROL_RADIUS,
        origin[1],
        origin[2] + math.sin(angle) * IDLE_PATROL_RADIUS,
    )


def idle_patrol_step(
    current_pos,
    home,
    waypoint_index,
    tick_count,
    pause_until_tick=0,
    navigation_complete=False,
):
    """Advance the slow idle loop without letting it drift from home."""
    try:
        position = tuple(float(value) for value in current_pos)
        index = int(waypoint_index) % IDLE_PATROL_POINT_COUNT
        now = int(tick_count)
        pause_until = max(0, int(pause_until_tick))
    except (TypeError, ValueError):
        return (0, 0, None, False)
    destination = idle_patrol_point(home, index)
    if len(position) < 3 or destination is None:
        return (index, pause_until, None, False)
    if now < pause_until:
        return (index, pause_until, None, False)
    dx = position[0] - destination[0]
    dz = position[2] - destination[2]
    reached = dx * dx + dz * dz <= IDLE_PATROL_REACHED_DISTANCE ** 2
    if reached or bool(navigation_complete):
        index = (index + 1) % IDLE_PATROL_POINT_COUNT
        return (index, now + IDLE_PATROL_PAUSE_TICKS, None, True)
    return (index, pause_until, destination, False)


def slither_motion(
    current_motion,
    forward,
    strafe,
    minimum_forward=0.075,
    lateral_scale=0.085,
):
    """Add bounded lateral slither while preserving faster path motion."""
    try:
        current = tuple(float(value) for value in current_motion)
        direction = tuple(float(value) for value in forward)
        minimum = max(0.0, float(minimum_forward))
        lateral = float(strafe) * max(0.0, float(lateral_scale))
    except (TypeError, ValueError):
        return (0.0, 0.0, 0.0)
    if len(current) < 3 or len(direction) < 2:
        return (0.0, 0.0, 0.0)
    length = math.sqrt(
        direction[0] * direction[0] + direction[1] * direction[1]
    )
    if length < 0.0001:
        return (current[0], current[1], current[2])
    forward_x = direction[0] / length
    forward_z = direction[1] / length
    forward_speed = max(
        minimum,
        current[0] * forward_x + current[2] * forward_z,
    )
    lateral_x = -forward_z
    lateral_z = forward_x
    return (
        forward_x * forward_speed + lateral_x * lateral,
        current[1],
        forward_z * forward_speed + lateral_z * lateral,
    )


def slither_strafe(tick_count, state, current_strafe=0.0):
    if state == DAZE:
        return 0.0
    if state in (CHARGE, INTIMIDATE):
        return float(current_strafe) * 0.8
    return math.cos(float(tick_count) * 0.3) * 0.6


def segment_destruction_schedule(previous_segments, new_segments):
    previous = int(clamp(int(previous_segments), 0, MAX_SEGMENTS))
    current = int(clamp(int(new_segments), 0, MAX_SEGMENTS))
    if current >= previous:
        return []
    schedule = [
        (index, (previous - index) * SEGMENT_DESTRUCTION_DELAY)
        for index in range(current, previous)
    ]
    return sorted(schedule, key=lambda item: item[1])


def heal_amount(ticks_since_damaged):
    ticks = int(ticks_since_damaged)
    if ticks > TICKS_BEFORE_HEALING and ticks % 20 == 0:
        return 1.0
    return 0.0


def death_trail_positions(start, end, death_time):
    """Return the source Naga's compost trail samples for one death tick.

    Ground clipping remains an engine-adapter concern.  The curve, four-tick
    trail and quarter-tick sampling are copied from Naga#tickDeathAnimation.
    """
    try:
        tick = int(death_time)
        source = tuple(float(start[index]) for index in range(3))
        destination = tuple(float(end[index]) for index in range(3))
    except (TypeError, ValueError, IndexError):
        return []
    if tick <= DEATH_ANIMATION_TICKS or tick >= DEATH_TICKS:
        return []

    difference = tuple(
        destination[index] - source[index] for index in range(3)
    )
    angle = math.degrees(math.atan2(difference[2], difference[0])) + 180.0
    x_multiplier = angle % 180.0
    x_multiplier = min(x_multiplier, 180.0 - x_multiplier)
    x_multiplier = (x_multiplier / 90.0) ** 1.5 * 2.0
    z_multiplier = (angle + 90.0) % 180.0
    z_multiplier = min(z_multiplier, 180.0 - z_multiplier)
    z_multiplier = (z_multiplier / 90.0) ** 1.5 * 2.0

    positions = []
    for trail_index in range(1, 5):
        trail_time = tick - DEATH_ANIMATION_TICKS - trail_index
        if trail_time < 0:
            continue
        for quarter in (0.0, 0.25, 0.5, 0.75):
            precise_time = float(trail_time) - quarter
            if precise_time < 0.0:
                continue
            factor = precise_time / float(DEATH_PARTICLE_TICKS)
            positions.append(
                (
                    source[0]
                    + difference[0] * factor
                    + math.sin(precise_time * math.pi * 0.075)
                    * x_multiplier,
                    source[1]
                    + difference[1] * factor
                    + math.sin(precise_time * math.pi * 0.025) * 0.1,
                    source[2]
                    + difference[2] * factor
                    + math.cos(precise_time * math.pi * 0.0625)
                    * z_multiplier,
                )
            )
    return positions


def death_burst_positions(destination, death_time, rng=None):
    """Return the locked source's final three forty-particle death clouds."""
    try:
        tick = int(death_time)
        end = tuple(float(destination[index]) for index in range(3))
    except (TypeError, ValueError, IndexError):
        return []
    if tick < DEATH_TICKS - 3 or tick >= DEATH_TICKS:
        return []
    random_source = rng or random
    positions = []
    for index in range(40):
        spread = 0.075 * float(index)
        positions.append(
            (
                end[0] + (random_source.random() - 0.5) * spread,
                end[1] + (random_source.random() - 0.5) * spread,
                end[2] + (random_source.random() - 0.5) * spread,
            )
        )
    return positions


class NagaBrain(object):
    def __init__(self, rng=None):
        self.rng = rng or random.Random()
        self.state = CIRCLE
        self.counter = INITIAL_CIRCLE_WAYPOINTS
        self.clockwise = False
        self.damage_during_stun = 0.0

    def _roll(self, maximum):
        return int(self.rng.randint(0, int(maximum)))

    def snapshot(self):
        return {
            "state": self.state,
            "counter": int(self.counter),
            "clockwise": bool(self.clockwise),
            "damageDuringStun": int(self.damage_during_stun),
        }

    @classmethod
    def from_snapshot(cls, value, rng=None):
        brain = cls(rng)
        if not isinstance(value, dict):
            return brain
        state = value.get("state")
        if state in (
            INTIMIDATE,
            CRUMBLE,
            CHARGE,
            STUNLESS_CHARGE,
            CIRCLE,
            DAZE,
        ):
            brain.state = state
        try:
            brain.counter = max(0, int(value.get("counter", brain.counter)))
            brain.damage_during_stun = max(
                0, int(value.get("damageDuringStun", 0))
            )
        except (TypeError, ValueError):
            pass
        brain.clockwise = bool(value.get("clockwise", False))
        if brain.state == CIRCLE:
            brain.counter = min(
                INITIAL_CIRCLE_WAYPOINTS, brain.counter
            )
        elif brain.state in (CHARGE, STUNLESS_CHARGE):
            brain.counter = min(2, brain.counter)
        return brain

    def do_circle(self):
        self.state = CIRCLE
        self.counter = CIRCLE_WAYPOINTS_MIN + self._roll(
            CIRCLE_WAYPOINTS_VARIANCE
        )

    def force_circle(self):
        self.state = CIRCLE
        self.counter = CIRCLE_WAYPOINTS_MIN + self._roll(
            CIRCLE_WAYPOINTS_VARIANCE
        )

    def do_daze(self):
        self.state = DAZE
        self.counter = 60 + self._roll(39)

    def transition(self, target_above=False, use_stunless=False):
        if self.state == CIRCLE:
            self.state = INTIMIDATE
            self.counter += 15 + self._roll(9)
        elif self.state == INTIMIDATE:
            self.clockwise = not self.clockwise
            if target_above:
                self.state = CRUMBLE
                self.counter = 20 + self._roll(19)
            else:
                self.state = STUNLESS_CHARGE if use_stunless else CHARGE
                self.counter = 2
        elif self.state == CRUMBLE:
            self.state = STUNLESS_CHARGE if use_stunless else CHARGE
            self.counter = 2
        else:
            self.do_circle()
        return self.state

    def tick_counter(self, target_above=False, use_stunless=False):
        previous = self.counter
        self.counter -= 1
        if previous <= 0:
            return self.transition(target_above, use_stunless)
        return self.state

    def advance_timed_state(self, target_above=False, use_stunless=False):
        if self.state not in (INTIMIDATE, CRUMBLE, DAZE):
            return self.state
        return self.tick_counter(target_above, use_stunless)

    def complete_path_step(self, target_above=False, use_stunless=False):
        if self.state not in (CIRCLE, CHARGE, STUNLESS_CHARGE):
            return self.state
        self.counter -= 1
        if self.counter <= 0:
            # Java decrements before it transitions.  Preserve that -1 base
            # for the following timed state without issuing an extra path.
            self.counter = -1
            return self.transition(target_above, use_stunless)
        return self.state

    def record_damage(self, amount):
        if self.state != DAZE:
            return False
        self.damage_during_stun = int(
            self.damage_during_stun + max(0.0, float(amount))
        )
        if self.damage_during_stun > STUN_DAMAGE_LIMIT:
            self.force_circle()
            self.damage_during_stun = 0.0
            return True
        return False

    def resolve_contact(self, blocking=False, contact_damage=None):
        result = {
            "kind": "none",
            "target_damage": 0.0,
            "self_damage": 0.0,
            "shield_damage": 0,
            "shield_cooldown": 0,
            "knockback": 0.0,
        }
        if self.state == DAZE:
            return result
        if blocking and self.state == CHARGE:
            result.update(
                {
                    "kind": "shield_daze",
                    "self_damage": 2.0,
                    "shield_damage": 5,
                    "knockback": 3.0,
                }
            )
            self.do_daze()
            return result
        if blocking and self.state == STUNLESS_CHARGE:
            result.update(
                {
                    "kind": "shield_break",
                    "target_damage": 4.0,
                    "shield_damage": 10,
                    "shield_cooldown": 200,
                    "knockback": 0.0,
                }
            )
            self.do_circle()
            return result
        result.update(
            {
                "kind": "melee",
                "target_damage": (
                    BASE_ATTACK_DAMAGE
                    if contact_damage is None
                    else max(0.0, float(contact_damage))
                ),
                "knockback": 2.0,
            }
        )
        if self.state in (CHARGE, STUNLESS_CHARGE):
            self.force_circle()
        return result

    def orbit_parameters(self):
        radius = 12.0 if self.counter % 2 == 0 else 14.0
        rotation = 1.0
        if self.counter == 2:
            radius = 16.0
        if self.counter == 1:
            rotation = 0.1
        return radius, rotation
