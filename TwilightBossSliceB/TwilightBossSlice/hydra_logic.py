# -*- coding: utf-8 -*-
"""Deterministic, server-authoritative Hydra combat contract."""

import math


MAX_HEALTH = 360.0
XP_REWARD = 511
MAX_HEADS = 7
INITIAL_ACTIVE_HEADS = 3
HYDRA_CLIENT_TWEEN_TICKS = 1.5
HYDRA_MAX_HEAD_X_ROT = 40.0
HYDRA_IDLE_BODY_LOCKED = True
HYDRA_IDLE_CHAIN_LOCKED = True
HYDRA_IDLE_HEAD_SWAY_DEGREES = 5.0
ROOT_COLLISION_HEIGHT = 12.0
# EntityType.Builder.sized(16, 12) uses the ordinary living-entity standing
# eye ratio.  The Bedrock root actor is intentionally only 0.1 blocks tall,
# so engine sensing from that proxy would ray-test at its feet instead.
HYDRA_EYE_HEIGHT = ROOT_COLLISION_HEIGHT * 0.85
HEAD_DAMAGE_THRESHOLD = 120.0
SHARED_HURT_WINDOW_TICKS = 10
# Head and neck actors are Bedrock hit proxies, not independent living parts.
# Keep their engine health far above any legitimate hit so the engine cannot
# enter its death/removal path before the server redirects the damage.
PART_ACTOR_HEALTH = 1000000.0
HEAD_RESPAWN_TICKS = 100
REGEN_DELAY_TICKS = 1000
REGEN_INTERVAL_TICKS = 5
DEATH_TICKS = 200

BITE_DAMAGE = 48.0
FLAME_DAMAGE = 19.0
MORTAR_DAMAGE = 18.0

PART_COLLISIONS = {
    "body": (6.0, 6.0),
    "left_leg": (2.0, 3.0),
    "right_leg": (2.0, 3.0),
    "tail": (6.0, 2.0),
    "head": (4.0, 4.0),
    "neck": (2.0, 2.0),
}


def hydra_eye_position(body_position):
    """Return the source-sized Hydra sensing origin for a root foot position."""
    return (
        float(body_position[0]),
        float(body_position[1]) + HYDRA_EYE_HEIGHT,
        float(body_position[2]),
    )

# Locked HydraHeadContainer IDLE poses: x rotation, y rotation, neck length.
REST_HEAD_POSES = (
    (60.0, 0.0, 7.0),
    (10.0, 60.0, 9.0),
    (10.0, -60.0, 9.0),
    (50.0, 90.0, 8.0),
    (50.0, -90.0, 8.0),
    (-10.0, 90.0, 9.0),
    (-10.0, -90.0, 9.0),
)

# HydraHeadContainer.setupStateRotations, expressed as
# (x rotation, y rotation, neck length, mouth openness).  Unspecified bite
# poses on the four rear heads retain their idle pose because those heads are
# never allowed to select a bite attack in the source AI.
_POSES = {
    "idle": tuple(pose + (0.0,) for pose in REST_HEAD_POSES),
    "cooldown": tuple(pose + (0.0,) for pose in REST_HEAD_POSES),
    "flame_begin": (
        (50.0, 0.0, 8.0, 0.75),
        (30.0, 45.0, 9.0, 0.75),
        (30.0, -45.0, 9.0, 0.75),
        (50.0, 90.0, 8.0, 0.75),
        (50.0, -90.0, 8.0, 0.75),
        (-10.0, 90.0, 9.0, 0.75),
        (-10.0, -90.0, 9.0, 0.75),
    ),
    "flaming": (
        (45.0, 0.0, 8.0, 1.0),
        (30.0, 60.0, 9.0, 1.0),
        (30.0, -60.0, 9.0, 1.0),
        (50.0, 90.0, 8.0, 1.0),
        (50.0, -90.0, 8.0, 1.0),
        (-10.0, 90.0, 9.0, 1.0),
        (-10.0, -90.0, 9.0, 1.0),
    ),
    "flame_end": (
        (60.0, 0.0, 7.0, 0.0),
        (10.0, 45.0, 9.0, 0.0),
        (10.0, -45.0, 9.0, 0.0),
        (50.0, 90.0, 8.0, 0.0),
        (50.0, -90.0, 8.0, 0.0),
        (-10.0, 90.0, 9.0, 0.0),
        (-10.0, -90.0, 9.0, 0.0),
    ),
    "dying": (
        (-20.0, 0.0, 7.0, 0.0),
        (-20.0, 60.0, 9.0, 0.0),
        (-20.0, -60.0, 9.0, 0.0),
        (-20.0, 90.0, 8.0, 0.0),
        (-20.0, -90.0, 8.0, 0.0),
        (-10.0, 90.0, 9.0, 0.0),
        (-10.0, -90.0, 9.0, 0.0),
    ),
    "dead": (
        (0.0, 179.0, 4.0, 0.0),
        (0.0, 179.0, 4.0, 0.0),
        (0.0, -180.0, 4.0, 0.0),
        (0.0, 179.0, 4.0, 0.0),
        (0.0, -180.0, 4.0, 0.0),
        (0.0, 179.0, 4.0, 0.0),
        (0.0, -180.0, 4.0, 0.0),
    ),
    "roar": (
        (60.0, 0.0, 9.0, 1.0),
        (10.0, 60.0, 11.0, 1.0),
        (10.0, -60.0, 11.0, 1.0),
        (50.0, 90.0, 10.0, 1.0),
        (50.0, -90.0, 10.0, 1.0),
        (-10.0, 90.0, 11.0, 1.0),
        (-10.0, -90.0, 11.0, 1.0),
    ),
}

_POSES["mortar_begin"] = _POSES["flame_begin"]
_POSES["mortar_shoot"] = _POSES["flaming"]
_POSES["mortar_end"] = _POSES["flame_end"]
_POSES["born"] = _POSES["idle"]
_POSES["roar_start"] = tuple(
    pose[:3] + (0.25,) for pose in _POSES["idle"]
)


def _bite_poses(front, mouth):
    return tuple(front) + tuple(
        pose[:3] + (mouth,) for pose in _POSES["idle"][3:]
    )


_POSES["bite_begin"] = _bite_poses(
    (
        (-5.0, 60.0, 5.0, 0.25),
        (-10.0, 60.0, 9.0, 0.25),
        (-10.0, -60.0, 9.0, 0.25),
    ),
    0.25,
)
_POSES["bite_ready"] = _bite_poses(
    (
        (-5.0, 60.0, 5.0, 1.0),
        (-10.0, 60.0, 9.0, 1.0),
        (-10.0, -60.0, 9.0, 1.0),
    ),
    1.0,
)
_POSES["biting"] = _bite_poses(
    (
        (-5.0, -30.0, 5.0, 0.2),
        (-10.0, -30.0, 5.0, 0.2),
        (-10.0, 30.0, 5.0, 0.2),
    ),
    0.2,
)
_POSES["bite_end"] = _bite_poses(
    (
        (60.0, 0.0, 7.0, 0.0),
        (-10.0, 60.0, 9.0, 0.0),
        (-10.0, -60.0, 9.0, 0.0),
    ),
    0.0,
)

# Locked body-local HydraHeadContainer neck roots.
NECK_ROOT_OFFSETS = (
    (0.0, 3.0, -1.0),
    (-1.0, 3.0, 3.0),
    (1.0, 3.0, 3.0),
    (-1.0, 3.0, 3.0),
    (1.0, 3.0, 3.0),
    (-1.0, 3.0, 5.0),
    (1.0, 3.0, 5.0),
)

# HydraHeadContainer rotates each raw neck root by a head-specific yaw before
# applying the body's yaw. Keeping this separate mirrors setNeckPosition().
NECK_ROOT_YAWS = (0.0, 90.0, -90.0, 135.0, -135.0, 135.0, -135.0)


def head_pose(state, index):
    """Return one locked HydraHeadContainer state pose."""
    poses = _POSES.get(str(state), _POSES["idle"])
    return tuple(float(value) for value in poses[int(index) % MAX_HEADS])


def _idle_sway_periods(index):
    index = int(index) % MAX_HEADS
    period_x = 20.0 if index in (0, 3) else (5.0 if index in (1, 4) else 7.0)
    period_y = 10.0 if index in (0, 4) else (6.0 if index in (1, 6) else 5.0)
    return period_x, period_y


def animated_head_pose(pose, index, tick, active=True):
    """Apply the locked per-head sinusoidal position sway."""
    values = tuple(float(value) for value in pose)
    if not bool(active):
        return values
    period_x, period_y = _idle_sway_periods(index)
    # HydraHeadContainer feeds ``xSwing`` into a radians expression before
    # converting the completed value back to degrees.  The effective degree
    # delta is therefore xSwing / PI, not the raw three-degree amplitude.
    x_swing = math.sin(float(tick) / period_x) * 3.0 / math.pi
    y_swing = math.sin(float(tick) / period_y) * 5.0
    return (
        values[0] + x_swing,
        values[1] + y_swing,
        values[2],
        values[3],
    )


def mobile_idle_head_yaw(body_yaw, index, tick):
    """Bounded head-only idle yaw for the user-selected mobile visual."""
    unusedPeriodX, period_y = _idle_sway_periods(index)
    del unusedPeriodX
    return float(body_yaw) + math.sin(
        float(tick) / period_y
    ) * HYDRA_IDLE_HEAD_SWAY_DEGREES


def interpolated_head_pose(previous_state, state, index, ticks, duration=None):
    """Interpolate the last and current Java state pose."""
    previous = head_pose(previous_state, index)
    current = head_pose(state, index)
    if duration is None:
        duration = STATE_DURATIONS.get(str(state), 1)
    factor = max(0.0, min(1.0, float(ticks) / max(1.0, float(duration))))
    return tuple(
        previous[axis] + (current[axis] - previous[axis]) * factor
        for axis in range(4)
    )


def head_offset_for_pose(pose):
    """Convert a state pose to the source body-local endpoint."""
    x_rotation, y_rotation, neck_length = tuple(pose)[:3]
    x_radians = math.radians(x_rotation)
    y_radians = math.radians(-y_rotation)
    raised = neck_length * math.sin(x_radians)
    forward = neck_length * math.cos(x_radians)
    return (
        forward * math.sin(y_radians),
        raised + 3.0,
        forward * math.cos(y_radians),
    )


def _world_offset(position, yaw_degrees, offset):
    yaw = math.radians(float(yaw_degrees))
    ox, oy, oz = tuple(float(value) for value in offset[:3])
    position = tuple(float(value) for value in position[:3])
    return (
        position[0] + ox * math.cos(yaw) - oz * math.sin(yaw),
        position[1] + oy,
        position[2] + ox * math.sin(yaw) + oz * math.cos(yaw),
    )


def _unwrapped_angle_target(previous, target):
    previous = float(previous)
    target = float(target)
    while target - previous <= -180.0:
        target += 360.0
    while target - previous > 180.0:
        target -= 360.0
    return target


def interpolated_actor_transform(
    previous_position,
    target_position,
    previous_rotation,
    target_rotation,
    elapsed_ticks,
    duration_ticks=HYDRA_CLIENT_TWEEN_TICKS,
):
    """Blend one real actor sample on the client's 30 Hz tick.

    The server actors retain exact authoritative transforms.  The client uses
    this sample only for a small model offset and local render rotation, which
    recreates Java's previous/current part interpolation without moving hit
    proxies or entering the camera-space virtual world.
    """
    previous_position = tuple(
        float(value) for value in previous_position[:3]
    )
    target_position = tuple(float(value) for value in target_position[:3])
    previous_rotation = tuple(
        float(value) for value in previous_rotation[:2]
    )
    target_rotation = tuple(float(value) for value in target_rotation[:2])
    duration = max(0.000001, float(duration_ticks))
    factor = max(0.0, min(1.0, float(elapsed_ticks) / duration))
    unwrapped_target = (
        _unwrapped_angle_target(previous_rotation[0], target_rotation[0]),
        _unwrapped_angle_target(previous_rotation[1], target_rotation[1]),
    )
    return {
        "position": tuple(
            previous_position[axis]
            + (target_position[axis] - previous_position[axis]) * factor
            for axis in range(3)
        ),
        "rotation": tuple(
            previous_rotation[axis]
            + (unwrapped_target[axis] - previous_rotation[axis]) * factor
            for axis in range(2)
        ),
        "factor": factor,
    }


def world_offset_to_local(world_offset, yaw_degrees):
    """Convert a world-space visual correction into actor-local offset."""
    dx, dy, dz = tuple(float(value) for value in world_offset[:3])
    yaw = math.radians(float(yaw_degrees))
    return (
        dx * math.cos(yaw) + dz * math.sin(yaw),
        dy,
        -dx * math.sin(yaw) + dz * math.cos(yaw),
    )


def head_chain_frame(
    index,
    previous_state,
    state,
    state_ticks,
    world_tick,
    body_position,
    body_yaw,
    head_yaw,
    head_pitch,
    lock_idle_chain=False,
):
    """Compute one immutable source pose sample for a head and all five necks."""
    index = int(index) % MAX_HEADS
    pose = interpolated_head_pose(
        previous_state, state, index, state_ticks
    )
    if not bool(lock_idle_chain):
        pose = animated_head_pose(
            pose, index, world_tick, str(state) != "dead"
        )
    head_position = _world_offset(
        body_position, body_yaw, head_offset_for_pose(pose)
    )
    start = _world_offset(body_position, body_yaw, neck_root_offset(index))
    neck_end = (
        float(head_position[0]),
        float(head_position[1]) - 0.5,
        float(head_position[2]),
    )
    neckYaw = float(body_yaw) if lock_idle_chain else float(head_yaw)
    neckPitch = 0.0 if lock_idle_chain else float(head_pitch)
    necks = neck_segment_transforms(
        start, neck_end, body_yaw, neckYaw, neckPitch
    )
    return {
        "pose": pose,
        "mouth": float(pose[3]),
        "head_position": head_position,
        "neck_endpoint": head_position,
        "facing": (float(head_yaw), float(head_pitch)),
        "necks": necks,
    }


def rest_head_offset(index):
    """Return the locked Java IDLE head position in body-local blocks."""
    return head_offset_for_pose(head_pose("idle", index))


def neck_root_offset(index):
    """Return the locked, pre-body-yaw neck root in body-local blocks."""
    index = int(index) % MAX_HEADS
    x_value, y_value, z_value = NECK_ROOT_OFFSETS[index]
    radians = math.radians(-NECK_ROOT_YAWS[index])
    return (
        x_value * math.cos(radians) + z_value * math.sin(radians),
        y_value,
        z_value * math.cos(radians) - x_value * math.sin(radians),
    )


def _normalized_neck_angles(start_yaw, end_yaw, end_pitch):
    start_yaw = float(start_yaw)
    end_yaw = float(end_yaw)
    end_pitch = float(end_pitch)
    while start_yaw - end_yaw < -180.0:
        end_yaw -= 360.0
    while start_yaw - end_yaw >= 180.0:
        end_yaw += 360.0
    while -end_pitch < -180.0:
        end_pitch -= 360.0
    while -end_pitch >= 180.0:
        end_pitch += 360.0
    return start_yaw, end_yaw, end_pitch


def neck_segment_transforms(start, end, start_yaw, end_yaw, end_pitch):
    """Port HydraHeadContainer's five position/yaw/pitch neck samples."""
    start = tuple(float(value) for value in start[:3])
    end = [float(value) for value in end[:3]]
    start_yaw, end_yaw, end_pitch = _normalized_neck_angles(
        start_yaw, end_yaw, end_pitch
    )
    yaw_radians = math.radians(end_yaw)
    if end_pitch > 0.0:
        # Locked 4.3.2508 retracts a downward-looking neck by one block.
        end[0] += math.sin(yaw_radians)
        end[2] -= math.cos(yaw_radians)
    else:
        pitch_radians = math.radians(end_pitch)
        look = (
            -math.sin(yaw_radians) * math.cos(pitch_radians),
            -math.sin(pitch_radians),
            math.cos(yaw_radians) * math.cos(pitch_radians),
        )
        for axis in range(3):
            end[axis] -= look[axis]
    result = []
    for factor in (0.0, 0.25, 0.5, 0.75, 1.0):
        position = tuple(
            end[axis] + (start[axis] - end[axis]) * factor
            for axis in range(3)
        )
        rotation = (
            end_pitch + (0.0 - end_pitch) * factor,
            end_yaw + (start_yaw - end_yaw) * factor,
        )
        result.append((position, rotation))
    return tuple(result)


def neck_visual_rotation(rotation):
    """Preserve segment pitch/yaw for Bedrock's engine-owned actor transform.

    Java's TFPartRenderer needs an explicit matrix/model cancellation because
    it bypasses LivingEntityRenderer.  A Bedrock entity actor already owns the
    equivalent base-axis transform, so adding another fixed root turn or
    cancelling its yaw would duplicate that adapter.
    """
    return (float(rotation[0]), float(rotation[1]))


def rest_neck_segment_offsets(index):
    """Return the five locked neck samples from head back to body root."""
    index = int(index) % MAX_HEADS
    start = neck_root_offset(index)
    head = list(rest_head_offset(index))
    # HydraHeadContainer retracts the neck endpoint one block behind a
    # level-facing head before sampling factors 0, .25, .5, .75 and 1.
    head[2] -= 1.0
    factors = (0.0, 0.25, 0.5, 0.75, 1.0)
    return tuple(
        tuple(
            head[axis] + (start[axis] - head[axis]) * factor
            for axis in range(3)
        )
        for factor in factors
    )

STATE_DURATIONS = {
    "idle": 10,
    "bite_begin": 40,
    "bite_ready": 80,
    "biting": 7,
    "bite_end": 40,
    "flame_begin": 40,
    "flaming": 100,
    "flame_end": 30,
    "mortar_begin": 40,
    "mortar_shoot": 25,
    "mortar_end": 30,
    "cooldown": 80,
    "dying": 70,
    "dead": 20,
    "born": 20,
    "roar_start": 10,
    "roar": 50,
}

_NEXT_STATE = {
    "bite_begin": "bite_ready",
    "bite_ready": "biting",
    "biting": "bite_end",
    "bite_end": "cooldown",
    "flame_begin": "flaming",
    "flaming": "flame_end",
    "flame_end": "cooldown",
    "mortar_begin": "mortar_shoot",
    "mortar_shoot": "mortar_end",
    "mortar_end": "cooldown",
    "cooldown": "idle",
    "born": "roar_start",
    "roar_start": "roar",
    "roar": "idle",
    "dying": "dead",
}

_COMBAT_BODY_TURN_STATES = frozenset((
    "bite_begin", "bite_ready", "biting", "bite_end",
    "flame_begin", "flaming", "flame_end",
    "mortar_begin", "mortar_shoot", "mortar_end",
))


def lock_idle_chain_for_state(state):
    return bool(
        HYDRA_IDLE_CHAIN_LOCKED
        and str(state) in ("idle", "cooldown")
    )


def combat_body_turn_active(head_states):
    return any(
        str(state) in _COMBAT_BODY_TURN_STATES
        for state in head_states
    )


def accepted_damage(amount, hit_part, mouth_open=False):
    amount = max(0.0, float(amount))
    if hit_part == "head" and mouth_open:
        return amount
    if hit_part in ("body", "head", "neck", "tail"):
        # Java uses Math.round(damage / 8), not a floating-point division.
        return float(int(math.floor(amount / 8.0 + 0.5)))
    return 0.0


def accepted_multipart_damage(
    amount,
    hit_part,
    mouth_open=False,
    part_alive=True,
    bypass_invulnerability=False,
):
    """Port Hydra.attackEntityFromPart plus the unpickable root distinction."""
    amount = max(0.0, float(amount))
    hit_part = str(hit_part)
    if not bool(part_alive):
        return 0.0
    if hit_part == "root":
        return amount if bool(bypass_invulnerability) else 0.0
    if hit_part == "head" and bool(mouth_open):
        return amount
    if hit_part in (
        "body", "left_leg", "right_leg", "tail", "head", "neck"
    ):
        return float(int(math.floor(amount / 8.0 + 0.5)))
    return 0.0


def difficulty_scaled_damage(amount, difficulty):
    """Apply DamageScaling.WHEN_CAUSED_BY_LIVING_NON_PLAYER."""
    amount = max(0.0, float(amount))
    difficulty = int(difficulty)
    if difficulty <= 0:
        return 0.0
    if difficulty == 1:
        return min(amount * 0.5 + 1.0, amount)
    if difficulty >= 3:
        return amount * 1.5
    return amount


def clamp_bite_yaw(index, body_yaw, head_yaw):
    """Apply the locked BITE_READY body-relative yaw bands."""
    index = int(index)
    body_yaw = float(body_yaw)
    head_yaw = float(head_yaw)
    if index in (0, 1):
        lower, upper = -90.0, -60.0
    elif index == 2:
        lower, upper = 60.0, 90.0
    else:
        return head_yaw
    relative = (head_yaw - body_yaw + 180.0) % 360.0 - 180.0
    relative = max(lower, min(upper, relative))
    return body_yaw + relative


def bite_pitch_degrees(current_pitch):
    """Preserve HydraHeadContainer's literal PI / 4 bite pitch offset."""
    return float(current_pitch) + math.pi / 4.0


def bite_throw_motion(yaw, blocking=False):
    """Return Hydra's cardinal half-block throw packet motion."""
    look = look_vector(0.0, yaw)
    if abs(look[0]) > abs(look[2]):
        step_x = 1.0 if look[0] > 0.0 else -1.0
        step_z = 0.0
    else:
        step_x = 0.0
        step_z = 1.0 if look[2] >= 0.0 else -1.0
    return (
        -step_x * 0.5,
        0.15 if bool(blocking) else 0.1,
        -step_z * 0.5,
    )


def should_acquire_target(random_roll):
    return float(random_roll) < 0.7


def target_expiry_tick(current_tick, random_ticks):
    return int(current_tick) + 100 + max(0, min(19, int(random_ticks)))


def target_is_retained(current_tick, expiry_tick, alive, distance_sq):
    return bool(alive) and int(current_tick) < int(expiry_tick) and float(
        distance_sq
    ) <= 48.0 * 48.0


def idle_body_yaw(body_yaw, velocity, reroll, new_velocity):
    velocity = float(new_velocity) if bool(reroll) else float(velocity)
    return (float(body_yaw) + velocity, velocity)


def locked_idle_body_yaw(body_yaw, entity_yaw):
    """NetEase visual override: idle raw yaw drives heads, not the body.

    The locked Java Hydra may correct yBodyRot after large raw-yaw separation.
    On the separate-actor Bedrock presentation that correction swings every
    long neck root and reads as an animation defect.  The user-selected mobile
    adaptation freezes multipart body yaw only while no target exists.
    """
    del entity_yaw
    return float(body_yaw)


def body_yaw_after_head_turn(body_yaw, movement_yaw, entity_yaw):
    """Port LivingEntity.tickHeadTurn used by the locked Hydra.

    Hydra's randomYawVelocity changes the actor's raw Y rotation. Multipart
    roots and head positions use yBodyRot, which follows the head/raw axes at
    0.3 and clamps their separation. Treating raw Y rotation as yBodyRot makes
    creative-mode rerolls whip every long neck directly around the body.
    """
    body_yaw = float(body_yaw)
    movement_yaw = float(movement_yaw)
    entity_yaw = float(entity_yaw)
    movement_delta = (
        movement_yaw - body_yaw + 180.0
    ) % 360.0 - 180.0
    body_yaw += movement_delta * 0.3
    relative = (entity_yaw - body_yaw + 180.0) % 360.0 - 180.0
    if relative < -75.0:
        relative = -75.0
    elif relative >= 75.0:
        relative = 75.0
    body_yaw = entity_yaw - relative
    if relative * relative > 2500.0:
        body_yaw += relative * 0.2
    return body_yaw


def hydra_loot_counts(
    base_chops,
    base_blood,
    looting_level=0,
    chop_roll=0.0,
    blood_roll=0.0,
):
    level = max(0, int(looting_level))
    chop_bonus = int(
        math.floor(level * max(0.0, min(1.0, float(chop_roll))) + 0.5)
    )
    blood_bonus = int(
        math.floor(level * max(0.0, min(2.0, float(blood_roll))) + 0.5)
    )
    return {
        "hydra_chop": max(0, int(base_chops)) + chop_bonus,
        "fiery_blood": max(0, int(base_blood)) + blood_bonus,
        "hydra_trophy": 1,
    }


def head_damage_credit(accepted_damage):
    """Mirror HydraHeadContainer.addDamage's integer damage counter."""
    return max(0, int(float(accepted_damage)))


def can_settle_part_impact(last_tick, last_source, tick, source):
    """Reject duplicate proxy hits from one attacker in one server tick.

    A Java multipart Hydra resolves one raycast against one part. Bedrock uses
    separate actors, so a sweep can report overlapping head/neck/body proxies
    for the same impact unless the adapter collapses them here.
    """
    if last_tick is None:
        return True
    return not (
        int(last_tick) == int(tick)
        and str(last_source) == str(source)
    )


def shared_hurt_resolution(
    amount, last_hurt_amount, window_start_tick, current_tick
):
    """Mirror LivingEntity's shared lastHurt delta window for all parts.

    Hydra.attackEntityFromPart forwards every part hit to one LivingEntity.
    During the first ten ticks of that entity's hurt-resistant window, an
    equal or weaker hit deals no health damage and a stronger hit deals only
    the difference.  The window itself is not extended by a difference hit.
    """
    amount = max(0.0, float(amount))
    last_hurt_amount = max(0.0, float(last_hurt_amount or 0.0))
    if amount <= 0.0:
        return {
            "healthDamage": 0.0,
            "lastHurtAmount": last_hurt_amount,
            "windowStartTick": window_start_tick,
        }
    current_tick = int(current_tick)
    active = False
    if window_start_tick is not None:
        elapsed = current_tick - int(window_start_tick)
        active = 0 <= elapsed < SHARED_HURT_WINDOW_TICKS
    if active:
        return {
            "healthDamage": max(0.0, amount - last_hurt_amount),
            "lastHurtAmount": max(last_hurt_amount, amount),
            "windowStartTick": int(window_start_tick),
        }
    return {
        "healthDamage": amount,
        "lastHurtAmount": amount,
        "windowStartTick": current_tick,
    }


def register_attack_victim(victims, target):
    """Return true once per target for a short attack action."""
    key = str(target)
    if key in victims:
        return False
    victims.add(key)
    return True


def flame_ray_target(origin, direction, candidates, max_range=30.0, beam_radius=3.0):
    """Pick the nearest entity intersecting the Hydra head look ray.

    Candidates are ``(entity_id, position, pick_radius)`` tuples. This ports
    HydraHeadContainer.getHeadLookTarget's 30-block ray and three-block broad
    phase while remaining deterministic for the Bedrock adapter.
    """
    origin = tuple(float(value) for value in origin[:3])
    direction = tuple(float(value) for value in direction[:3])
    length = math.sqrt(sum(value * value for value in direction))
    if length <= 0.000001:
        return None
    direction = tuple(value / length for value in direction)
    best_id = None
    best_distance = float(max_range) + 1.0
    for candidate in candidates:
        if len(candidate) < 2:
            continue
        entity_id = candidate[0]
        position = tuple(float(value) for value in candidate[1][:3])
        radius = float(candidate[2]) if len(candidate) > 2 else 0.0
        delta = tuple(position[axis] - origin[axis] for axis in range(3))
        along = sum(delta[axis] * direction[axis] for axis in range(3))
        if along < 0.0 or along > float(max_range):
            continue
        closest = tuple(
            origin[axis] + direction[axis] * along for axis in range(3)
        )
        perpendicular = math.sqrt(
            sum(
                (position[axis] - closest[axis]) ** 2
                for axis in range(3)
            )
        )
        if perpendicular > float(beam_radius) + max(0.0, radius):
            continue
        if along < best_distance:
            best_id = entity_id
            best_distance = along
    return best_id


def approach_point(current, target, max_step):
    """Move a retained flame-aim point toward the live target."""
    current = tuple(float(value) for value in current[:3])
    target = tuple(float(value) for value in target[:3])
    delta = tuple(target[axis] - current[axis] for axis in range(3))
    distance = math.sqrt(sum(value * value for value in delta))
    step = max(0.0, float(max_step))
    if distance <= step or distance <= 0.000001:
        return target
    return tuple(
        current[axis] + delta[axis] / distance * step
        for axis in range(3)
    )


def flame_particle_position(
    mouth, direction, gaussian_noise, spread, speed, age
):
    """Sample one locked LARGE_FLAME trajectory in world space.

    The source adds Gaussian noise scaled by ``0.0075 * spread`` to the
    retained look vector, then multiplies that velocity by a random speed.
    NetEase keeps locally emitted particles attached to the mouth, so the
    client renders short-lived world-space samples of the same trajectory.
    """
    mouth = tuple(float(value) for value in mouth[:3])
    direction = tuple(float(value) for value in direction[:3])
    noise = tuple(float(value) for value in gaussian_noise[:3])
    scale = 0.0075 * float(spread)
    travel = float(speed) * max(0.0, float(age))
    return tuple(
        mouth[axis]
        + (direction[axis] + noise[axis] * scale) * travel
        for axis in range(3)
    )


def flame_visual_sample_ages(count, phase=0.0, minimum_age=0.75, maximum_age=12.0):
    """Distribute retained world-space samples over the large-flame lifetime.

    The source spawns five moving particles every tick. NetEase cannot detach
    that emitter from a multipart head reliably, so the adapter renders
    already-advanced samples instead. Sampling only the first two ticks made
    the whole breath appear stuck beside the mouth; twelve ticks preserves the
    visible source stream without extending past its minimum particle life.
    """
    count = max(1, int(count))
    minimum_age = max(0.0, float(minimum_age))
    maximum_age = max(minimum_age, float(maximum_age))
    phase = float(phase) % 1.0
    if count == 1:
        return ((minimum_age + maximum_age) * 0.5,)
    step = (maximum_age - minimum_age) / float(count)
    return tuple(
        minimum_age + step * (float(index) + phase)
        for index in range(count)
    )


def merge_flame_candidate_ids(nearby, preferred_target=None, online_players=()):
    """Keep the ray broad phase stable when a multipart query drops players."""
    result = []
    seen = set()
    groups = (nearby or (), (preferred_target,), online_players or ())
    for group in groups:
        for entity_id in group:
            if entity_id is None:
                continue
            key = str(entity_id)
            if key in seen:
                continue
            seen.add(key)
            result.append(entity_id)
    return result


def look_vector(pitch_degrees, yaw_degrees, pitch_offset=0.0, speed=1.0):
    pitch = math.radians(float(pitch_degrees) + float(pitch_offset))
    yaw = math.radians(float(yaw_degrees))
    speed = float(speed)
    return (
        -math.sin(yaw) * math.cos(pitch) * speed,
        -math.sin(pitch) * speed,
        math.cos(yaw) * math.cos(pitch) * speed,
    )


def idle_face_target(body_position, entity_yaw):
    """Return HydraHeadContainer.faceIdle's shared world target."""
    body_position = tuple(float(value) for value in body_position[:3])
    look = look_vector(0.0, entity_yaw, speed=30.0)
    return (
        body_position[0] + look[0],
        body_position[1] + 3.0,
        body_position[2] + look[2],
    )


def mortar_launch_motion(pitch, yaw, triangular_noise=(0.0, 0.0, 0.0)):
    """Port shootFromRotation(..., -20, 0.5, 1.0) for HydraMortar."""
    direction = look_vector(pitch, yaw, pitch_offset=-20.0, speed=1.0)
    noise = tuple(float(value) for value in triangular_noise[:3])
    while len(noise) < 3:
        noise += (0.0,)
    # Projectile.shoot uses RandomSource.triangle with this vanilla scale.
    noisy = tuple(
        direction[axis] + noise[axis] * 0.0172275
        for axis in range(3)
    )
    length = math.sqrt(sum(value * value for value in noisy))
    if length <= 0.000001:
        return (0.0, 0.0, 0.5)
    return tuple(value / length * 0.5 for value in noisy)


def initial_head_state(index):
    """Return the source spawn lifecycle for one of the seven heads."""
    alive = int(index) < INITIAL_ACTIVE_HEADS
    return {
        "alive": alive,
        "state": "idle" if alive else "dead",
        # -1 is the source's unscheduled sentinel.  Only a head killed during
        # combat receives a non-negative respawn counter.
        "dead_ticks": -1,
    }


def next_dead_ticks(dead_ticks):
    value = int(dead_ticks)
    return value + 1 if value >= 0 else -1


def advance_respawn_counter(state, respawn_ticks):
    """Advance the locked per-head counter only while the head is DEAD."""
    counter = int(respawn_ticks)
    if str(state) != "dead" or counter < 0:
        return counter, False
    counter -= 1
    if counter <= 0:
        return -1, True
    return counter, False


def respawn_heads(alive_heads, killed_index, dead_ticks, extra_index=None):
    result = [bool(value) for value in list(alive_heads)[:MAX_HEADS]]
    while len(result) < MAX_HEADS:
        result.append(False)
    if int(dead_ticks) < HEAD_RESPAWN_TICKS:
        return result
    killed_index = int(killed_index)
    if 0 <= killed_index < MAX_HEADS:
        result[killed_index] = True
    candidates = [index for index, alive in enumerate(result) if not alive]
    if candidates:
        selected = candidates[0]
        if extra_index is not None and int(extra_index) in candidates:
            selected = int(extra_index)
        result[selected] = True
    return result


def heal_amount(ticks_since_effective_damage):
    ticks = int(ticks_since_effective_damage)
    if ticks > REGEN_DELAY_TICKS and ticks % REGEN_INTERVAL_TICKS == 0:
        return 1.0
    return 0.0


def mortar_blast_power(mega):
    return 4.0 if bool(mega) else 0.1


def mortar_fuse_after_tick(fuse, on_ground):
    """HydraMortar only consumes its 80-tick fuse after landing."""
    return int(fuse) - 1 if bool(on_ground) else int(fuse)


def attack_weight(states):
    """Count concurrent attacks using the source's weighted bite budget."""
    total = 0.0
    for state in states:
        name = str(state)
        if name in ("bite_begin", "bite_ready", "biting", "bite_end"):
            if name != "bite_end":
                total += 3.0
        elif name in (
            "flame_begin", "flaming",
            "mortar_begin", "mortar_shoot",
        ):
            total += 1.0
    return total


def can_start_attack(active_heads, other_attack_weight, difficulty_factor):
    limit = 1.0 + max(0, int(active_heads)) * float(difficulty_factor)
    return float(other_attack_weight) < limit


def choose_primary_attack(
    index,
    distance,
    target_above,
    active_heads,
    other_attack_weight,
    bite_roll,
    flame_roll,
    mortar_roll,
    difficulty_factor=0.3,
    other_biting=False,
):
    """Select an IDLE attack using HydraHeadContainer's exact gates."""
    if not can_start_attack(
        active_heads, other_attack_weight, difficulty_factor
    ):
        return None
    index = int(index)
    distance = float(distance)
    if (
        index < INITIAL_ACTIVE_HEADS
        and active_heads > 2
        and not bool(other_biting)
        and 4.0 < distance < 10.0
        and int(bite_roll) == 0
    ):
        return "bite"
    if 0.0 < distance < 20.0 and int(flame_roll) == 0:
        return "flame"
    if (
        8.0 < distance < 32.0
        and not bool(target_above)
        and int(mortar_roll) == 0
    ):
        return "mortar"
    return None


def choose_secondary_attack(index, distance, target_on_side, flame_roll, mortar_roll):
    """Choose the source's faster secondary-head attack."""
    if int(index) == 0 or not bool(target_on_side):
        return None
    distance = float(distance)
    if 0.0 < distance < 20.0 and int(flame_roll) == 0:
        return "flame"
    if 8.0 < distance < 32.0 and int(mortar_roll) == 0:
        return "mortar"
    return None


def approach_angle(current, target, max_step=5.0):
    """Approach a wrapped yaw/pitch without the 360-degree spin path."""
    current = float(current)
    target = float(target)
    max_step = abs(float(max_step))
    delta = (target - current + 180.0) % 360.0 - 180.0
    if delta > max_step:
        delta = max_step
    elif delta < -max_step:
        delta = -max_step
    # Preserve a continuous yaw stream. Returning the wrapped equivalent
    # (179 -> -179) asks Bedrock to interpolate almost a full revolution and
    # is the visible multi-head twitch reported by the client.
    return current + delta


def reflect_mortar(old_owner, player, look):
    del old_owner
    direction = tuple(float(value) for value in look[:3])
    length = sum(value * value for value in direction) ** 0.5
    if length <= 0.000001:
        direction = (0.0, 0.0, 1.0)
        length = 1.0
    return {
        "owner": player,
        "motion": tuple(value / length * 1.5 for value in direction),
        "speed": 1.5,
        "inaccuracy": 0.1,
        "added_fuse": 20,
        "exclude": player,
    }


def mortar_shot_ticks(state_ticks):
    tick = int(state_ticks)
    return tick >= 0 and tick < STATE_DURATIONS["mortar_shoot"] and tick % 10 == 0


def death_event(death_ticks):
    tick = int(death_ticks)
    return {
        "head_explosion": tick in tuple(range(20, 141, 20)),
        "settle": tick == DEATH_TICKS,
        "remove": tick >= DEATH_TICKS,
    }


class HydraHeadBrain(object):
    def __init__(self, state="idle", ticks=0):
        self.state = str(state)
        self.ticks = max(0, int(ticks))
        self.rolled_over = False

    def begin(self, attack):
        names = {
            "bite": "bite_begin",
            "flame": "flame_begin",
            "mortar": "mortar_begin",
        }
        if attack not in names:
            raise ValueError("unknown hydra attack")
        self.state = names[attack]
        self.ticks = 0
        return self.state

    def tick(self):
        self.rolled_over = False
        self.ticks += 1
        duration = STATE_DURATIONS.get(self.state)
        if duration is not None and self.ticks >= duration:
            self.state = _NEXT_STATE.get(self.state, self.state)
            self.ticks = 0
            self.rolled_over = True
        # HydraHeadContainer advances the state before attacks, particles and
        # sounds run for the tick, including the new state's tick zero.
        return self.state

    def serialize(self):
        return {"state": self.state, "ticks": self.ticks}
