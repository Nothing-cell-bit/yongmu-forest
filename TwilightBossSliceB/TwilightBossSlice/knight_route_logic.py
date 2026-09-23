# -*- coding: utf-8 -*-
"""Pure Knight Stronghold and six-Phantom encounter rules.

The module is intentionally engine-free so saved group state can be migrated,
validated and regression-tested without a running NetEase client.
"""

from __future__ import division

import copy
import math
import random


GROUP_SCHEMA_VERSION = 2
MEMBER_COUNT = 6
MEMBER_MAX_HEALTH = 35.0
HOME_RADIUS = 30
RING_RADIUS = 4
COMBAT_Y_OFFSET = 1.0
CIRCLE_SMALL_RADIUS = 2.5
CIRCLE_LARGE_RADIUS = 8.5
PROJECTILE_CLEARANCE = 1.0
PROJECTILE_LAUNCH_HEIGHT = 2.0
DYING_ASCENT_TICKS = 18
DEATH_PARTICLE_TICKS = 70
DEATH_TOTAL_TICKS = DYING_ASCENT_TICKS + DEATH_PARTICLE_TICKS
RUNTIME_MISSING_GRACE_TICKS = 20
WALL_STALL_TRIGGER_TICKS = 10
WALL_ESCAPE_TICKS = 20
WALL_ESCAPE_RELOCATION_STEP = 0.5
WALL_STALL_MIN_DISTANCE = 1.0
WALL_STALL_MOVE_EPSILON = 0.05
KNIGHT_CRUISE_SPEED = 0.20
KNIGHT_CHARGE_SPEED = 0.40
KNIGHT_ESCAPE_SPEED = 0.30
CHARGE_PASS_RADIUS = 0.75
KNIGHT_PROJECTILE_TTL_TICKS = 100
KNIGHT_PROJECTILE_REGISTRY_LIMIT = 256
BLOCK_CHAIN_DAMAGE = 10.0
BLOCK_CHAIN_MAX_DISTANCE = 16.0
BLOCK_CHAIN_MAX_SMASH = 12
BLOCK_CHAIN_ENTITY_DURABILITY_COST = 1
BLOCK_CHAIN_MAX_BLOCK_DURABILITY_COST = 3
BLOCK_CHAIN_SHIELD_DAMAGE = 5
BLOCK_CHAIN_SHIELD_DISABLE_TICKS = 100
KNIGHTMETAL_SHIELD_RAISE_TICKS = 5
BLOCK_CHAIN_GRAVITY = 0.05
BLOCK_CHAIN_BOUNCE = 0.6
BLOCK_CHAIN_LINK_FRACTIONS = (0.05, 0.25, 0.45, 0.65, 0.85)
BLOCK_CHAIN_HAND_YAW_OFFSET = 0.4
BLOCK_CHAIN_HAND_VERTICAL_OFFSET = -0.4
BLOCK_CHAIN_SPAWN_FORWARD_OFFSET = 0.5
ROLE_SWORD = 0
ROLE_AXE = 1
ROLE_PICKAXE = 2

FORMATION_DURATIONS = {
    "hover": 90,
    "large_clockwise": 180,
    "small_clockwise": 90,
    "large_anticlockwise": 180,
    "small_anticlockwise": 90,
    "charge_plus_x": 180,
    "charge_minus_x": 180,
    "charge_plus_z": 180,
    "charge_minus_z": 180,
    "waiting_for_leader": 10,
    "attack_player_start": 50,
    "attack_player_attack": 50,
}
FORMATION_SEQUENCE = (
    "hover",
    "large_clockwise",
    "small_clockwise",
    "large_anticlockwise",
    "small_anticlockwise",
    "charge_plus_x",
    "charge_minus_x",
    "charge_plus_z",
    "charge_minus_z",
    "waiting_for_leader",
    "attack_player_start",
    "attack_player_attack",
)
RANDOM_FORMATION_TABLE = (
    "small_clockwise",
    "small_anticlockwise",
    "small_anticlockwise",
    "charge_plus_x",
    "charge_minus_x",
    "charge_plus_z",
    "charge_minus_z",
    "small_clockwise",
)
CHARGING_FORMATIONS = frozenset(
    ("attack_player_start", "attack_player_attack")
)
IGNORED_ENVIRONMENTAL_DAMAGE_CAUSES = frozenset(
    ("suffocation", "in_wall", "inwall")
)
ORDINARY_FORMATIONS = frozenset(
    (
        "hover",
        "large_clockwise",
        "small_clockwise",
        "large_anticlockwise",
        "small_anticlockwise",
        "charge_plus_x",
        "charge_minus_x",
        "charge_plus_z",
        "charge_minus_z",
    )
)
ACCEPTED_TROPHIES = frozenset(
    (
        "tf_slice:naga_trophy",
        "tf_slice:lich_trophy",
        "tf_slice:minoshroom_trophy",
        "tf_slice:hydra_trophy",
        "tf_slice:knight_phantom_trophy",
        "tf_slice:ur_ghast_trophy",
        "tf_slice:quest_ram_trophy",
    )
)
PLAYER_SHIELD_BYPASS_CAUSES = frozenset(
    (
        "void",
        "suicide",
        "magic",
        "wither",
        "starve",
        "drown",
        "fire",
        "lava",
        "fall",
        "suffocation",
        "in_wall",
        "inwall",
    )
)


def player_shield_blocks(held, raised_ticks, from_front, damage_cause=""):
    cause = str(damage_cause or "").lower()
    bypass = any(marker in cause for marker in PLAYER_SHIELD_BYPASS_CAUSES)
    return bool(
        held
        and int(raised_ticks) >= KNIGHTMETAL_SHIELD_RAISE_TICKS
        and from_front
        and not bypass
    )


def block_chain_should_return(returning, distance, age_ticks):
    del age_ticks
    return bool(
        returning
        or float(distance) > BLOCK_CHAIN_MAX_DISTANCE
    )


def block_chain_smash_allowance(blocks_smashed):
    return max(0, BLOCK_CHAIN_MAX_SMASH - max(0, int(blocks_smashed)))


def block_chain_link_positions(owner_anchor, projectile_position):
    owner = tuple(float(value) for value in owner_anchor)
    projectile = tuple(float(value) for value in projectile_position)
    return [
        tuple(
            owner[axis] + (projectile[axis] - owner[axis]) * fraction
            for axis in range(3)
        )
        for fraction in BLOCK_CHAIN_LINK_FRACTIONS
    ]


def block_chain_hand_anchor(
    owner_position,
    rotation,
    main_hand=True,
    eye_height=1.62,
):
    """Return the classic hand-side chain origin used by EntityTFChainBlock."""
    owner = tuple(float(value) for value in owner_position)
    pitch = math.radians(float(rotation[0]))
    yaw = math.radians(float(rotation[1]))
    look_x = -math.sin(yaw) * math.cos(pitch)
    look_y = -math.sin(pitch)
    look_z = math.cos(yaw) * math.cos(pitch)
    hand_yaw = (
        -BLOCK_CHAIN_HAND_YAW_OFFSET
        if main_hand
        else BLOCK_CHAIN_HAND_YAW_OFFSET
    )
    cosine = math.cos(hand_yaw)
    sine = math.sin(hand_yaw)
    hand_x = look_x * cosine + look_z * sine
    hand_z = look_z * cosine - look_x * sine
    return (
        owner[0] + hand_x,
        owner[1]
        + look_y
        + float(eye_height)
        + BLOCK_CHAIN_HAND_VERTICAL_OFFSET,
        owner[2] + hand_z,
    )


def block_chain_spawn_position(
    owner_position,
    rotation,
    main_hand=True,
    eye_height=1.62,
):
    """Spawn beyond the hand so Bedrock never renders the flail in-camera."""
    anchor = block_chain_hand_anchor(
        owner_position, rotation, main_hand, eye_height
    )
    pitch = math.radians(float(rotation[0]))
    yaw = math.radians(float(rotation[1]))
    look = (
        -math.sin(yaw) * math.cos(pitch),
        -math.sin(pitch),
        math.cos(yaw) * math.cos(pitch),
    )
    return tuple(
        anchor[axis] + look[axis] * BLOCK_CHAIN_SPAWN_FORWARD_OFFSET
        for axis in range(3)
    )


def block_chain_visual_state(hand_anchor, projectile_position):
    hand = tuple(float(value) for value in hand_anchor)
    projectile = tuple(float(value) for value in projectile_position)
    toward_hand = tuple(
        hand[axis] - projectile[axis] for axis in range(3)
    )
    return {
        "towardHand": toward_hand,
        "length": math.sqrt(sum(value * value for value in toward_hand)),
    }


def block_chain_can_hit_target(target_id, owner_id, target_type):
    return bool(
        target_id is not None
        and str(target_id) != str(owner_id)
        and str(target_type or "") != "tf_slice:block_chain_link"
    )


def block_chain_rotation_for_motion(motion, fallback_yaw=0.0):
    dx, dy, dz = (float(value) for value in motion)
    horizontal = math.sqrt(dx * dx + dz * dz)
    if horizontal <= 0.000001 and abs(dy) <= 0.000001:
        return (0.0, float(fallback_yaw))
    pitch = math.degrees(math.atan2(-dy, horizontal))
    yaw = (
        math.degrees(math.atan2(-dx, dz))
        if horizontal > 0.000001
        else float(fallback_yaw)
    )
    return (pitch, yaw)


def block_chain_return_motion(
    base_motion,
    owner_anchor,
    projectile_position,
    age_ticks,
):
    base = tuple(float(value) for value in base_motion)
    owner = tuple(float(value) for value in owner_anchor)
    projectile = tuple(float(value) for value in projectile_position)
    delta = tuple(owner[axis] - projectile[axis] for axis in range(3))
    length = math.sqrt(sum(value * value for value in delta)) or 1.0
    back = tuple(value / length for value in delta)
    blend = min(max(float(age_ticks) * 0.03, 0.0), 1.0)
    return (
        base[0] * (1.0 - blend) + back[0] * 2.0 * blend,
        base[1] * (1.0 - blend) + back[1] * 2.0 * blend
        - BLOCK_CHAIN_GRAVITY,
        base[2] * (1.0 - blend) + back[2] * 2.0 * blend,
    )


def block_chain_bounce_motion(motion, hit_face):
    x, y, z = (float(value) * BLOCK_CHAIN_BOUNCE for value in motion)
    face = str(hit_face).upper()
    if face in ("0", "DOWN") and y > 0.0:
        y *= -BLOCK_CHAIN_BOUNCE
    elif face in ("1", "UP") and y < 0.0:
        y *= -BLOCK_CHAIN_BOUNCE
    elif face in ("2", "NORTH") and z > 0.0:
        z *= -BLOCK_CHAIN_BOUNCE
    elif face in ("3", "SOUTH") and z < 0.0:
        z *= -BLOCK_CHAIN_BOUNCE
    elif face in ("4", "WEST") and x > 0.0:
        x *= -BLOCK_CHAIN_BOUNCE
    elif face in ("5", "EAST") and x < 0.0:
        x *= -BLOCK_CHAIN_BOUNCE
    return (x, y, z)


def _member(number):
    number = int(number)
    return {
        "slot": number,
        "number": number,
        "role": number % 3,
        "health": MEMBER_MAX_HEALTH,
        "alive": True,
        "entityId": None,
        "formation": "hover",
        "formationTick": 0,
        "charging": False,
        "attackDamage": 1.0,
        "armorMultiplier": 5.0,
        "chargePos": None,
        "chargeVector": None,
        "shieldEquipped": False,
        "guardCoolDownTime": 0,
        "isGuard": False,
        "guarding": False,
        "dying": False,
        "deathTick": 0,
        "deathSourceId": None,
        "runtimeMissingTicks": 0,
        "runtimeLastPosition": None,
        "runtimeStallTicks": 0,
        "wallEscapeTicks": 0,
    }


def create_group_state(group_id, home, member_numbers=None):
    numbers = list(range(MEMBER_COUNT) if member_numbers is None else member_numbers)
    if sorted(int(value) for value in numbers) != list(range(MEMBER_COUNT)):
        raise ValueError("Knight Phantom member numbers must be exactly 0..5")
    return {
        "schemaVersion": GROUP_SCHEMA_VERSION,
        "groupId": str(group_id),
        "home": [int(value) for value in home],
        "homeRadius": HOME_RADIUS,
        "ringRadius": RING_RADIUS,
        "members": [_member(number) for number in numbers],
        "deathSlots": [],
        "participants": [],
        "formation": "hover",
        "formationTick": 0,
        "state": "active",
        "defeated": False,
        "rewardClaimed": False,
        "rewardChestPlaced": False,
        "deathSequenceReleased": False,
        "environmentDamageRepairApplied": False,
        "soloMode": False,
    }


def load_group_state(value):
    if not isinstance(value, dict):
        raise ValueError("Knight Phantom group state must be a mapping")
    copied = copy.deepcopy(value)
    source_version = int(copied.get("schemaVersion", 1))
    copied["schemaVersion"] = GROUP_SCHEMA_VERSION
    copied.setdefault("homeRadius", HOME_RADIUS)
    copied.setdefault("ringRadius", RING_RADIUS)
    copied.setdefault("participants", [])
    copied.setdefault("deathSlots", [])
    copied.setdefault("rewardClaimed", False)
    copied.setdefault("rewardChestPlaced", False)
    copied.setdefault("deathSequenceReleased", False)
    copied.setdefault("environmentDamageRepairApplied", False)
    copied.setdefault("soloMode", False)
    copied["deathSlots"] = sorted(
        set(int(number) for number in copied["deathSlots"] if 0 <= int(number) < MEMBER_COUNT)
    )
    members = copied.get("members", [])
    living_numbers = [
        int(member.get("number", -1))
        for member in members
        if member.get("alive", True) and not member.get("dying", False)
    ]
    if living_numbers and len(living_numbers) != len(set(living_numbers)):
        raise ValueError("duplicate Knight Phantom member numbers")
    group_formation = str(copied.get("formation", "hover"))
    if group_formation not in FORMATION_DURATIONS:
        group_formation = "hover"
    copied["formation"] = group_formation
    copied["formationTick"] = max(0, int(copied.get("formationTick", 0)))
    alive_members = [member for member in members if member.get("alive", True)]
    migrated_charger = None
    if source_version < GROUP_SCHEMA_VERSION and group_formation in CHARGING_FORMATIONS:
        if alive_members:
            migrated_charger = min(
                alive_members, key=lambda member: int(member.get("number", 0))
            )
        copied["formation"] = "hover"
        copied["formationTick"] = 0
    slots = []
    for original_index, member in enumerate(members):
        number = int(member.get("number", 0))
        slot = int(member.get("slot", number if number >= 0 else original_index))
        member["slot"] = slot
        slots.append(slot)
        member.setdefault("role", number % 3)
        member.setdefault("health", MEMBER_MAX_HEALTH)
        member.setdefault("alive", slot not in copied["deathSlots"])
        if slot in copied["deathSlots"]:
            member["alive"] = False
            member["health"] = 0.0
        member.setdefault("entityId", None)
        if source_version < GROUP_SCHEMA_VERSION:
            member["formation"] = (
                group_formation if member is migrated_charger else copied["formation"]
            )
            member["formationTick"] = (
                max(0, int(value.get("formationTick", 0)))
                if member is migrated_charger else copied["formationTick"]
            )
        else:
            member.setdefault("formation", copied["formation"])
            member.setdefault("formationTick", copied["formationTick"])
        member.setdefault("chargePos", None)
        member.setdefault("chargeVector", None)
        member.setdefault("shieldEquipped", False)
        member.setdefault("guardCoolDownTime", 0)
        member.setdefault("isGuard", False)
        member.setdefault("guarding", False)
        member.setdefault("dying", False)
        member.setdefault("deathTick", 0)
        member.setdefault("deathSourceId", None)
        member.setdefault("deathRestartPending", False)
        member.setdefault("runtimeMissingTicks", 0)
        member.setdefault("runtimeLastPosition", None)
        member.setdefault("runtimeStallTicks", 0)
        member.setdefault("wallEscapeTicks", 0)
        if member.get("dying", False):
            member["health"] = 0.0
        _sync_member_combat(member)
    if slots and len(slots) != len(set(slots)):
        raise ValueError("duplicate Knight Phantom stable slots")
    renumber_living_members(copied)
    copied["defeated"] = len(copied["deathSlots"]) == MEMBER_COUNT
    if copied["defeated"]:
        copied["state"] = "defeated"
    return copied


def member_state(group, number):
    number = int(number)
    for member in group.get("members", ()):
        if int(member.get("number", -1)) == number:
            return member
    return None


def member_by_slot(group, slot):
    slot = int(slot)
    for member in group.get("members", ()):
        if int(member.get("slot", member.get("number", -1))) == slot:
            return member
    return None


def member_is_charging(member):
    return str((member or {}).get("formation", "hover")) in CHARGING_FORMATIONS


def _sync_member_combat(member):
    charging = bool(
        member.get("alive", True)
        and not member.get("dying", False)
        and member_is_charging(member)
    )
    member["charging"] = charging
    member["attackDamage"] = 8.0 if charging else 1.0
    member["armorMultiplier"] = 1.0 if charging else 5.0
    return charging


def renumber_living_members(group):
    living = sorted(
        (
            member for member in group.get("members", ())
            if member.get("alive", True) and not member.get("dying", False)
        ),
        key=lambda member: int(
            member.get("slot", member.get("number", MEMBER_COUNT))
        ),
    )
    group["soloMode"] = bool(len(living) == 1)
    for number, member in enumerate(living):
        previous_role = int(member.get("role", number % 3))
        role = number % 3
        member["number"] = number
        member["role"] = role
        if previous_role != role:
            member["visualRole"] = -1
    return living


def runtime_member_stale(member, present, encounter_active, ticks=1):
    """Return true after a live actor is missing for one loaded-room second."""
    if (
        not member.get("alive", True)
        or member.get("dying", False)
        or not encounter_active
        or present
    ):
        member["runtimeMissingTicks"] = 0
        return False
    member["runtimeMissingTicks"] = min(
        RUNTIME_MISSING_GRACE_TICKS,
        max(0, int(member.get("runtimeMissingTicks", 0)))
        + max(0, int(ticks)),
    )
    return bool(
        member["runtimeMissingTicks"] >= RUNTIME_MISSING_GRACE_TICKS
    )


def advance_wall_escape(
    member,
    current_position,
    destination,
    encounter_active,
    ticks=1,
    blocked=False,
):
    current = tuple(float(value) for value in current_position)
    target = tuple(float(value) for value in destination)
    previous = member.get("runtimeLastPosition")
    member["runtimeLastPosition"] = list(current)
    if (
        not encounter_active
        or not member.get("alive", True)
        or member.get("dying", False)
    ):
        member["runtimeStallTicks"] = 0
        member["wallEscapeTicks"] = 0
        return False

    escape_ticks = max(0, int(member.get("wallEscapeTicks", 0)))
    if escape_ticks > 0:
        member["wallEscapeTicks"] = max(
            0, escape_ticks - max(0, int(ticks))
        )
        return True

    remaining = horizontal_distance(current, target)
    moved = (
        horizontal_distance(current, previous)
        if isinstance(previous, (tuple, list)) and len(previous) == 3
        else None
    )
    if blocked or (
        moved is not None
        and remaining > WALL_STALL_MIN_DISTANCE
        and moved < WALL_STALL_MOVE_EPSILON
    ):
        member["runtimeStallTicks"] = min(
            WALL_STALL_TRIGGER_TICKS,
            max(0, int(member.get("runtimeStallTicks", 0)))
            + max(0, int(ticks)),
        )
    else:
        member["runtimeStallTicks"] = 0
    if int(member.get("runtimeStallTicks", 0)) < WALL_STALL_TRIGGER_TICKS:
        return False
    member["runtimeStallTicks"] = 0
    member["wallEscapeTicks"] = WALL_ESCAPE_TICKS
    return True


def wall_escape_destination(group, member):
    home = group.get("home") or (0, 0, 0)
    return (
        float(home[0]),
        _combat_y(
            home,
            member.get("formationTick", 0),
            member.get("number", 0),
        ),
        float(home[2]),
    )


def wall_escape_relocation(
    current_position,
    destination,
    max_step=WALL_ESCAPE_RELOCATION_STEP,
):
    """Pull a colliding actor horizontally toward the safe room center."""
    current = tuple(float(value) for value in current_position)
    target = tuple(float(value) for value in destination)
    dx = target[0] - current[0]
    dz = target[2] - current[2]
    distance = math.sqrt(dx * dx + dz * dz)
    step = max(0.0, float(max_step))
    if distance <= 0.0001 or step <= 0.0:
        return current
    if distance <= step:
        return (target[0], current[1], target[2])
    return (
        current[0] + dx / distance * step,
        current[1],
        current[2] + dz / distance * step,
    )


def knight_move_speed(charging, escape_active):
    if bool(escape_active):
        return KNIGHT_ESCAPE_SPEED
    if bool(charging):
        return KNIGHT_CHARGE_SPEED
    return KNIGHT_CRUISE_SPEED


def charge_direction(origin, target):
    delta = tuple(float(target[index]) - float(origin[index]) for index in range(3))
    length = math.sqrt(sum(value * value for value in delta))
    if length <= 0.0001:
        return None
    return tuple(value / length for value in delta)


def knight_motion_vector(
    current_position,
    destination,
    speed,
    charge_direction=None,
):
    current = tuple(float(value) for value in current_position)
    target = tuple(float(value) for value in destination)
    delta = tuple(target[index] - current[index] for index in range(3))
    distance = math.sqrt(sum(value * value for value in delta))
    movement_speed = max(0.0, float(speed))

    if isinstance(charge_direction, (tuple, list)) and len(charge_direction) == 3:
        raw_direction = tuple(float(value) for value in charge_direction)
        direction_length = math.sqrt(sum(value * value for value in raw_direction))
        if direction_length > 0.0001:
            direction = tuple(value / direction_length for value in raw_direction)
            remaining_along_charge = sum(
                delta[index] * direction[index] for index in range(3)
            )
            if distance <= CHARGE_PASS_RADIUS or remaining_along_charge <= 0.0:
                return tuple(value * movement_speed for value in direction)

    if distance <= 0.0001:
        return (0.0, 0.0, 0.0)
    return tuple(value / distance * movement_speed for value in delta)


def apply_difficulty_equipment(group, difficulty):
    hard = int(difficulty) >= 3
    changed = []
    for member in group.get("members", ()):
        equipped = bool(
            hard
            and int(member.get("slot", member.get("number", -1))) == 5
        )
        if bool(member.get("shieldEquipped", False)) != equipped:
            member["shieldEquipped"] = equipped
            if not equipped:
                member["guarding"] = False
                member["isGuard"] = False
                member["guardCoolDownTime"] = 0
            changed.append(member)
    return changed


def advance_guard(member, has_target, ticks=1):
    if not member.get("shieldEquipped", False):
        member["guarding"] = False
        return False
    for _unused in range(max(0, int(ticks))):
        if not has_target:
            continue
        if member.get("isGuard", False):
            if int(member.get("guardCoolDownTime", 0)) <= 180:
                member["guardCoolDownTime"] = int(
                    member.get("guardCoolDownTime", 0)
                ) + 1
            else:
                member["isGuard"] = False
        elif int(member.get("guardCoolDownTime", 0)) > 0:
            member["guardCoolDownTime"] = int(
                member.get("guardCoolDownTime", 0)
            ) - 1
        else:
            member["isGuard"] = True
    member["guarding"] = bool(
        has_target
        and member.get("isGuard", False)
        and str(member.get("formation", "hover")) != "attack_player_attack"
    )
    return member["guarding"]


def shield_blocks(member, from_front, bypass=False):
    return bool(
        member.get("shieldEquipped", False)
        and member.get("guarding", False)
        and from_front
        and not bypass
    )


def ignores_environmental_damage(cause):
    normalized = str(cause or "").strip().lower()
    normalized = normalized.replace("-", "_").replace(" ", "_")
    return normalized in IGNORED_ENVIRONMENTAL_DAMAGE_CAUSES


def repair_environment_damage(group):
    if group.get("environmentDamageRepairApplied", False):
        return []
    group["environmentDamageRepairApplied"] = True
    repaired = []
    for member in group.get("members", ()):
        if not member.get("alive", True) or member.get("dying", False):
            continue
        if float(member.get("health", MEMBER_MAX_HEALTH)) >= MEMBER_MAX_HEALTH:
            continue
        member["health"] = MEMBER_MAX_HEALTH
        repaired.append(member)
    return repaired


def begin_member_death(group, slot, source_id=None):
    member = member_by_slot(group, slot)
    if (
        member is None
        or not member.get("alive", True)
        or member.get("dying", False)
    ):
        return False
    if source_id is not None:
        record_participant(group, source_id)
    member["dying"] = True
    member["deathTick"] = 0
    member["deathSourceId"] = (
        str(source_id) if source_id is not None else None
    )
    member["deathRestartPending"] = False
    member["health"] = 0.0
    member["charging"] = False
    member["attackDamage"] = 1.0
    member["armorMultiplier"] = 5.0
    member["guarding"] = False
    remaining = renumber_living_members(group)
    if not remaining:
        group["deathSequenceReleased"] = True
        for dying_member in group.get("members", ()):
            if not dying_member.get("dying", False):
                continue
            dying_member["deathTick"] = 0
            dying_member["deathRestartPending"] = True
            dying_member["deathVisualStarted"] = False
    return True


def advance_member_death(member, ticks=1, release=True):
    previous = max(0, int(member.get("deathTick", 0)))
    requested = previous + max(0, int(ticks))
    if release:
        current = min(DEATH_TOTAL_TICKS, requested)
    else:
        current = min(DYING_ASCENT_TICKS, requested)
    member["deathTick"] = current
    hidden = previous < DYING_ASCENT_TICKS <= current
    trail_fraction = None
    if release and current > DYING_ASCENT_TICKS:
        trail_fraction = min(
            1.0,
            float(current - DYING_ASCENT_TICKS)
            / float(DEATH_PARTICLE_TICKS),
        )
    return {
        "ascent": current < DYING_ASCENT_TICKS,
        "hide": hidden,
        "hold": bool(not release and current >= DYING_ASCENT_TICKS),
        "trailFraction": trail_fraction,
        "finish": bool(release and current >= DEATH_TOTAL_TICKS),
    }


def combined_health(group):
    death_slots = set(int(value) for value in group.get("deathSlots", ()))
    return sum(
        max(0.0, float(member.get("health", 0.0)))
        for member in group.get("members", ())
        if int(member.get("slot", member.get("number", -1))) not in death_slots
        and member.get("alive", True)
        and not member.get("dying", False)
    )


def combined_max_health(group):
    return MEMBER_COUNT * MEMBER_MAX_HEALTH


def boss_bar_fraction(group):
    return max(0.0, min(1.0, combined_health(group) / combined_max_health(group)))


def combat_member_count(group):
    death_slots = set(int(value) for value in group.get("deathSlots", ()))
    return sum(
        1
        for member in group.get("members", ())
        if member.get("alive", True)
        and not member.get("dying", False)
        and int(member.get("slot", member.get("number", -1)))
        not in death_slots
        and float(member.get("health", 0.0)) > 0.0
    )


def boss_bar_visible(group):
    return bool(
        not group.get("defeated", False)
        and combat_member_count(group) > 0
        and combined_health(group) > 0.0
    )


def ring_position(home, member_number, radius=RING_RADIUS):
    angle = (int(member_number) / float(MEMBER_COUNT)) * math.pi * 2.0
    return (
        float(home[0]) + math.cos(angle) * float(radius),
        float(home[1]) + 1.0,
        float(home[2]) + math.sin(angle) * float(radius),
    )


def horizontal_distance(first, second):
    dx = float(first[0]) - float(second[0])
    dz = float(first[2]) - float(second[2])
    return math.sqrt(dx * dx + dz * dz)


def _combat_y(home, tick, number):
    return (
        float(home[1])
        + COMBAT_Y_OFFSET
        + math.cos(float(tick) / 7.0 + int(number))
    )


def _hover_destination(home, tick, number, current_position=None):
    if current_position is None:
        dx, _dy, dz = ring_position(home, number, RING_RADIUS)
    else:
        dx = float(current_position[0])
        dz = float(current_position[2])
    offset_x = float(home[0]) - dx
    offset_z = float(home[2]) - dz
    distance = math.sqrt(offset_x * offset_x + offset_z * offset_z)
    if distance > CIRCLE_LARGE_RADIUS:
        dx = float(home[0]) + offset_x / distance * CIRCLE_LARGE_RADIUS
        dz = float(home[2]) + offset_z / distance * CIRCLE_LARGE_RADIUS
    return (dx, _combat_y(home, tick, number), dz)


def _circle_destination(home, tick, number, radius, clockwise):
    angle = float(tick) * 2.0
    if not clockwise:
        angle *= -1.0
    angle += 60.0 * int(number)
    radians = math.radians(angle)
    return (
        float(home[0]) + math.cos(radians) * float(radius),
        _combat_y(home, tick, number),
        float(home[2]) + math.sin(radians) * float(radius),
    )


def _sweep_destination(home, tick, number, plus, along_x):
    lane_offset = int(number) * 3.0 - 7.5
    if int(tick) < 60:
        sweep_offset = -7.0
    else:
        sweep_offset = -7.0 + ((float(tick) - 60.0) / 120.0) * 14.0
    if not plus:
        sweep_offset *= -1.0
    return (
        float(home[0]) + (lane_offset if along_x else sweep_offset),
        _combat_y(home, tick, number),
        float(home[2]) + (sweep_offset if along_x else lane_offset),
    )


def formation_destination(
    group,
    member_number,
    player_position=None,
    current_position=None,
):
    """Return the locked-source destination for one persisted member state."""
    home = group.get("home") or (0, 0, 0)
    number = int(member_number)
    member = member_state(group, number) or {}
    formation = str(member.get("formation", group.get("formation", "hover")))
    tick = int(member.get("formationTick", group.get("formationTick", 0)))
    role = int(member.get("role", number % 3))

    if formation == "large_clockwise":
        return _circle_destination(
            home, tick, number, CIRCLE_LARGE_RADIUS, True
        )
    if formation == "small_clockwise":
        return _circle_destination(
            home, tick, number, CIRCLE_SMALL_RADIUS, True
        )
    if formation == "large_anticlockwise":
        return _circle_destination(
            home, tick, number, CIRCLE_LARGE_RADIUS, False
        )
    if formation == "small_anticlockwise":
        return _circle_destination(
            home, tick, number, CIRCLE_SMALL_RADIUS, False
        )
    if formation == "charge_plus_x":
        return _sweep_destination(home, tick, number, True, True)
    if formation == "charge_minus_x":
        return _sweep_destination(home, tick, number, False, True)
    if formation == "charge_plus_z":
        return _sweep_destination(home, tick, number, True, False)
    if formation == "charge_minus_z":
        return _sweep_destination(home, tick, number, False, False)
    if formation == "waiting_for_leader":
        return (
            float(home[0]),
            _combat_y(home, tick, number),
            float(home[2]),
        )
    if formation == "attack_player_attack" and role == ROLE_SWORD:
        charge_position = member.get("chargePos")
        if charge_position and len(charge_position) == 3:
            return tuple(float(value) for value in charge_position)
    return _hover_destination(home, tick, number, current_position)


def record_participant(group, player_id):
    player_id = str(player_id)
    participants = group.setdefault("participants", [])
    if player_id not in participants:
        participants.append(player_id)
        participants.sort()
        return True
    return False


def record_member_damage(group, slot, amount, player_id=None):
    slot = int(slot)
    if player_id is not None:
        record_participant(group, player_id)
    for member in group.get("members", ()):
        member_slot = int(member.get("slot", member.get("number", -1)))
        if member_slot != slot or not member.get("alive", True):
            continue
        member["health"] = max(0.0, float(member.get("health", 0.0)) - max(0.0, float(amount)))
        if member["health"] <= 0.0:
            return record_member_death(group, slot)
        return False
    return False


def record_member_death(group, slot):
    slot = int(slot)
    if slot < 0 or slot >= MEMBER_COUNT:
        raise ValueError("invalid Knight Phantom stable slot")
    death_slots = group.setdefault("deathSlots", [])
    if slot in death_slots:
        return False
    death_slots.append(slot)
    death_slots.sort()
    for member in group.get("members", ()):
        member_slot = int(member.get("slot", member.get("number", -1)))
        if member_slot == slot:
            member["alive"] = False
            member["health"] = 0.0
            member["entityId"] = None
            member["number"] = -1
            member["charging"] = False
            member["chargeVector"] = None
            member["guarding"] = False
            member["dying"] = False
    renumber_living_members(group)
    final = len(death_slots) == MEMBER_COUNT
    group["defeated"] = final
    if final:
        group["state"] = "defeated"
    return final


def claim_reward(group):
    if not group.get("defeated") or group.get("rewardClaimed"):
        return False
    group["rewardClaimed"] = True
    group["rewardChestPlaced"] = True
    return True


def reset_for_peaceful(group):
    copied = copy.deepcopy(group)
    copied["schemaVersion"] = GROUP_SCHEMA_VERSION
    copied["members"] = [_member(number) for number in range(MEMBER_COUNT)]
    copied["deathSlots"] = []
    copied["participants"] = []
    copied["formation"] = "hover"
    copied["formationTick"] = 0
    copied["state"] = "rearm_marker"
    copied["defeated"] = False
    copied["rewardClaimed"] = False
    copied["rewardChestPlaced"] = False
    copied["deathSequenceReleased"] = False
    copied["environmentDamageRepairApplied"] = False
    copied["soloMode"] = False
    return copied


def select_group_formation(roll):
    return RANDOM_FORMATION_TABLE[int(roll) % len(RANDOM_FORMATION_TABLE)]


def _roll(bound, supplied=None):
    bound = max(1, int(bound))
    if supplied is None:
        return random.randrange(bound)
    return int(supplied) % bound


def _set_member_formation(member, formation, tick=0):
    formation = str(formation)
    if formation not in FORMATION_DURATIONS:
        formation = "hover"
    member["formation"] = formation
    member["formationTick"] = max(0, int(tick))
    _sync_member_combat(member)


def _living_members(group):
    death_slots = set(int(value) for value in group.get("deathSlots", ()))
    return sorted(
        (
            member for member in group.get("members", ())
            if member.get("alive", True)
            and not member.get("dying", False)
            and int(member.get("slot", member.get("number", -1)))
            not in death_slots
        ),
        key=lambda member: int(member.get("number", -1)),
    )


def _ordinary_reference(living, excluded=None):
    for member in living:
        if member is excluded:
            continue
        if str(member.get("formation", "hover")) in ORDINARY_FORMATIONS:
            return member
    return None


def _broadcast_formation(group, living, formation):
    group["formation"] = formation
    group["formationTick"] = 0
    for member in living:
        if not member_is_charging(member):
            _set_member_formation(member, formation, 0)


def _choose_charger(living, charger_roll=None):
    if not living or any(member_is_charging(member) for member in living):
        return None
    charger = living[_roll(len(living), charger_roll)]
    _set_member_formation(charger, "attack_player_start", 0)
    return charger


def _advance_one_formation_tick(
    group,
    formation_roll=None,
    charger_roll=None,
    weapon_roll=None,
):
    living = renumber_living_members(group)
    if not living:
        return

    for member in living:
        formation = str(member.get("formation", "hover"))
        if formation not in FORMATION_DURATIONS:
            _set_member_formation(member, "hover", 0)
        member["formationTick"] = int(member.get("formationTick", 0)) + 1

    for member in living:
        formation = str(member.get("formation", "hover"))
        if int(member.get("formationTick", 0)) < FORMATION_DURATIONS[formation]:
            continue
        if formation == "attack_player_start":
            _set_member_formation(member, "attack_player_attack", 0)
        elif formation == "attack_player_attack":
            if len(living) > 1:
                _set_member_formation(member, "waiting_for_leader", 0)
            else:
                member["role"] = ROLE_SWORD
                _set_member_formation(member, "attack_player_start", 0)

    for member in living:
        if str(member.get("formation", "hover")) != "waiting_for_leader":
            continue
        if int(member.get("formationTick", 0)) < FORMATION_DURATIONS["waiting_for_leader"]:
            continue
        reference = _ordinary_reference(living, member)
        if reference is None:
            _set_member_formation(member, "attack_player_start", 0)
        else:
            _set_member_formation(
                member,
                reference.get("formation", "hover"),
                reference.get("formationTick", 0),
            )

    leader = living[0]
    leader_formation = str(leader.get("formation", "hover"))
    if (
        leader_formation in ORDINARY_FORMATIONS
        and int(leader.get("formationTick", 0))
        >= FORMATION_DURATIONS[leader_formation]
    ):
        selected = select_group_formation(_roll(8, formation_roll))
        _broadcast_formation(group, living, selected)
        _choose_charger(living, charger_roll)

    reference = _ordinary_reference(living)
    if reference is not None:
        group["formation"] = str(reference.get("formation", "hover"))
        group["formationTick"] = int(reference.get("formationTick", 0))
    for member in living:
        _sync_member_combat(member)


def advance_formation(
    group,
    ticks=1,
    formation_roll=None,
    charger_roll=None,
    weapon_roll=None,
):
    for _unused in range(max(0, int(ticks))):
        _advance_one_formation_tick(
            group,
            formation_roll=formation_roll,
            charger_roll=charger_roll,
            weapon_roll=weapon_roll,
        )
    return str(group.get("formation", "hover"))


def projectile_pattern(member_role, formation_tick):
    role = int(member_role) % 3
    if int(formation_tick) % 4 != 0:
        return []
    if role == ROLE_AXE:
        return [{"kind": "axe", "speed": 0.75, "damage": 0.0}]
    if role == ROLE_PICKAXE:
        return [
            {"kind": "pickaxe", "yaw": index * 45, "speed": 0.5, "damage": 3.0}
            for index in range(8)
        ]
    return []


def projectile_yaw_for_motion(motion, fallback_yaw=0.0):
    direction_x = float(motion[0])
    direction_z = float(motion[2])
    if direction_x * direction_x + direction_z * direction_z <= 0.00000001:
        return float(fallback_yaw)
    return math.degrees(math.atan2(-direction_x, direction_z))


def projectile_tracking_expired(
    spawn_tick,
    current_tick,
    max_age=KNIGHT_PROJECTILE_TTL_TICKS,
):
    return int(current_tick) - int(spawn_tick) >= max(0, int(max_age))


def projectile_registry_overflow_keys(
    registry,
    limit=KNIGHT_PROJECTILE_REGISTRY_LIMIT,
):
    overflow = max(0, len(registry) - max(0, int(limit)))
    if overflow <= 0:
        return []
    ordered = sorted(
        registry.items(),
        key=lambda item: (
            int((item[1] or {}).get("spawnTick", -1)),
            str(item[0]),
        ),
    )
    return [str(key) for key, _state in ordered[:overflow]]


def projectile_launch(origin, target, pattern):
    kind = str((pattern or {}).get("kind", ""))
    speed = max(0.0, float((pattern or {}).get("speed", 0.5)))
    if kind == "pickaxe":
        yaw = math.radians(float((pattern or {}).get("yaw", 0.0)))
        direction_x = math.cos(yaw)
        direction_z = math.sin(yaw)
        spawn = (
            float(origin[0]) + direction_x * PROJECTILE_CLEARANCE,
            float(origin[1]) + PROJECTILE_LAUNCH_HEIGHT,
            float(origin[2]) + direction_z * PROJECTILE_CLEARANCE,
        )
        motion = (direction_x * speed, 0.0, direction_z * speed)
        return {
            "spawn": spawn,
            "motion": motion,
            "yaw": projectile_yaw_for_motion(motion),
        }

    dx = float(target[0]) - float(origin[0])
    dz = float(target[2]) - float(origin[2])
    horizontal = math.sqrt(dx * dx + dz * dz)
    if horizontal <= 0.0001:
        direction_x, direction_z = 0.0, 1.0
    else:
        direction_x, direction_z = dx / horizontal, dz / horizontal
    spawn = (
        float(origin[0]) + direction_x * PROJECTILE_CLEARANCE,
        float(origin[1]) + PROJECTILE_LAUNCH_HEIGHT,
        float(origin[2]) + direction_z * PROJECTILE_CLEARANCE,
    )
    aim_x = float(target[0]) - spawn[0]
    aim_y = float(target[1]) + 0.8 - spawn[1]
    aim_z = float(target[2]) - spawn[2]
    length = math.sqrt(aim_x * aim_x + aim_y * aim_y + aim_z * aim_z) or 1.0
    return {
        "spawn": spawn,
        "yaw": projectile_yaw_for_motion(
            (aim_x / length, aim_y / length, aim_z / length)
        ),
        "motion": (
            aim_x / length * speed,
            aim_y / length * speed,
            aim_z / length * speed,
        ),
    }


def knightmetal_bonus(target_armor_points):
    """Upstream specialization: sword favors armor; tools favor no armor."""
    armored = float(target_armor_points) > 0.0
    return {"sword": 2.0 if armored else 0.0, "axe": 0.0 if armored else 2.0, "pickaxe": 0.0 if armored else 2.0}


def activate_trophy_pedestal(item_name, nearby_players, radius):
    accepted = str(item_name) in ACCEPTED_TROPHIES
    credited = []
    if accepted:
        for player in nearby_players:
            progress = player.get("progress") or {}
            if (
                float(player.get("distance", float("inf"))) <= float(radius)
                and (
                    bool(progress.get("lich_defeated"))
                    or bool(player.get("creative"))
                )
            ):
                credited.append(str(player.get("id")))
    return {
        "accepted": accepted,
        "creditedPlayers": sorted(set(credited)),
        "removeShieldWalls": bool(accepted and credited),
        # The Java pedestal reads the trophy block above it.  The item is not
        # a consumable key, so the Bedrock interaction fallback must retain it.
        "consumeTrophy": False,
    }
