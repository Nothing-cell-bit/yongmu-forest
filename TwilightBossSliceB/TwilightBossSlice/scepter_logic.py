# -*- coding: utf-8 -*-
import math
"""Pure 4.3.2508 Lich scepter charge and shield rules."""


SCEPTER_MAX_CHARGES = {
    "twilight_scepter": 99,
    "lifedrain_scepter": 99,
    "zombie_scepter": 9,
    "fortification_scepter": 9,
}

RECHARGE_INGREDIENTS = {
    "twilight_scepter": frozenset(("minecraft:ender_pearl",)),
    "lifedrain_scepter": frozenset(("minecraft:fermented_spider_eye",)),
    "zombie_scepter": frozenset(
        ("minecraft:rotten_flesh", "minecraft:potion:strength")
    ),
    "fortification_scepter": frozenset(("minecraft:golden_apple",)),
}

PLAYER_PROJECTILE_EYE_HEIGHT = 1.55
PLAYER_PROJECTILE_MUZZLE_DISTANCE = 1.0
SCEPTER_TARGET_RANGE = 20.0
SCEPTER_TARGET_BASE_RADIUS = 0.9
SCEPTER_TARGET_CONE_SCALE = 0.06
SCEPTER_RAY_STEP = 0.25
LIFEDRAIN_TARGET_LOSS_GRACE_TICKS = 10
SCEPTER_RAY_PASSABLE_BLOCKS = frozenset(
    (
        "minecraft:air",
        "minecraft:cave_air",
        "minecraft:void_air",
        "minecraft:water",
        "minecraft:flowing_water",
        "minecraft:tallgrass",
        "minecraft:double_plant",
        "minecraft:yellow_flower",
        "minecraft:red_flower",
        "minecraft:brown_mushroom",
        "minecraft:red_mushroom",
        "minecraft:snow_layer",
        "minecraft:vine",
    )
)


def _normalized(vector):
    values = tuple(float(value) for value in vector)
    length = math.sqrt(sum(value * value for value in values))
    if length < 0.0001:
        return None
    return tuple(value / length for value in values)


def select_aimed_target(
    origin,
    look,
    candidates,
    max_distance=SCEPTER_TARGET_RANGE,
):
    """Return the first living target intersected by the player's aim beam."""
    direction = _normalized(look)
    if direction is None:
        return None
    origin = tuple(float(value) for value in origin)
    hits = []
    for entity_id, position in candidates:
        offset = tuple(
            float(position[index]) - origin[index] for index in range(3)
        )
        projection = sum(
            offset[index] * direction[index] for index in range(3)
        )
        if projection <= 0.0 or projection > float(max_distance):
            continue
        distance_sq = sum(value * value for value in offset)
        perpendicular_sq = max(0.0, distance_sq - projection * projection)
        radius = max(
            SCEPTER_TARGET_BASE_RADIUS,
            projection * SCEPTER_TARGET_CONE_SCALE,
        )
        if perpendicular_sq <= radius * radius:
            hits.append((projection, perpendicular_sq, str(entity_id), entity_id))
    return min(hits)[-1] if hits else None


def raycast_spawn_position(
    origin,
    look,
    block_name_at,
    max_distance=SCEPTER_TARGET_RANGE,
    step=SCEPTER_RAY_STEP,
):
    """Return the last passable block cell before the aimed solid block."""
    direction = _normalized(look)
    if direction is None or float(step) <= 0.0:
        return None
    origin = tuple(float(value) for value in origin)
    last_passable = (0, 0, 0)
    has_passable = False
    distance = float(step)
    while distance <= float(max_distance) + 0.0001:
        sample = tuple(
            origin[index] + direction[index] * distance
            for index in range(3)
        )
        block_position = tuple(int(math.floor(value)) for value in sample)
        block_name = str(block_name_at(block_position) or "")
        if block_name not in SCEPTER_RAY_PASSABLE_BLOCKS:
            if not has_passable:
                return None
            head_position = (
                last_passable[0],
                last_passable[1] + 1,
                last_passable[2],
            )
            if str(block_name_at(head_position) or "") not in (
                SCEPTER_RAY_PASSABLE_BLOCKS
            ):
                return None
            return (
                last_passable[0] + 0.5,
                float(last_passable[1]),
                last_passable[2] + 0.5,
            )
        last_passable = block_position
        has_passable = True
        distance += float(step)
    return None


def player_projectile_spawn_position(position, look):
    """Place a fired bolt beyond the first-person camera and held item."""
    return (
        float(position[0])
        + float(look[0]) * PLAYER_PROJECTILE_MUZZLE_DISTANCE,
        float(position[1])
        + PLAYER_PROJECTILE_EYE_HEIGHT
        + float(look[1]) * PLAYER_PROJECTILE_MUZZLE_DISTANCE,
        float(position[2])
        + float(look[2]) * PLAYER_PROJECTILE_MUZZLE_DISTANCE,
    )


def new_scepter_state(kind, charges=None):
    maximum = int(SCEPTER_MAX_CHARGES[str(kind)])
    if charges is None:
        charges = maximum
    return {
        "kind": str(kind),
        "charges": max(0, min(maximum, int(charges))),
        "maxCharges": maximum,
    }


def _consume(state):
    if int(state.get("charges", 0)) <= 0:
        return False
    state["charges"] = int(state["charges"]) - 1
    return True


def use_twilight_scepter(state):
    if not _consume(state):
        return {"used": False, "damage": 0.0}
    return {
        "used": True,
        "projectile": "tf_slice:twilight_wand_bolt",
        "damage": 6.0,
        "speed": 1.5,
        "inaccuracy": 1.0,
    }


def lifedrain_tick(state, use_ticks, target_valid):
    result = {
        "used": False,
        "damage": 0.0,
        "healing": 0.0,
        "food": 0,
        "saturation": 0.0,
        "slownessAmplifier": 2,
        "slownessTicks": 20,
    }
    ticks = int(use_ticks)
    if not target_valid or ticks <= 0 or ticks % 5 != 0:
        return result
    if not _consume(state):
        return result
    result["used"] = True
    result["damage"] = 1.0
    if ticks % 10 == 0:
        result["healing"] = 1.0
        result["food"] = 1
        result["saturation"] = 0.1
    return result


def use_zombie_scepter(state, owner_id):
    if not _consume(state):
        return {"used": False}
    return {
        "used": True,
        "entity": "tf_slice:loyal_zombie",
        "ownerId": owner_id,
        "lifeTicks": 1200,
        "strengthAmplifier": 1,
        "strengthTicks": 1200,
    }


def new_shield_state(temporary=0, permanent=0):
    temporary = max(0, int(temporary))
    return {
        "temporary": temporary,
        "permanent": max(0, int(permanent)),
        "decayTimer": 240 if temporary else 0,
        "breakTimer": 0,
    }


def use_fortification_scepter(scepter_state, shield_state):
    if not _consume(scepter_state):
        return {"used": False, "cooldown": 0}
    shield_state["temporary"] = 5
    shield_state["decayTimer"] = 240
    return {"used": True, "cooldown": 1200}


def has_shield(state):
    return (
        int(state.get("temporary", 0)) > 0
        or int(state.get("permanent", 0)) > 0
    )


def break_shield(state):
    if int(state.get("breakTimer", 0)) > 0:
        return False
    if int(state.get("temporary", 0)) > 0:
        state["temporary"] = int(state["temporary"]) - 1
        state["decayTimer"] = 240 if state["temporary"] else 0
    elif int(state.get("permanent", 0)) > 0:
        state["permanent"] = int(state["permanent"]) - 1
    else:
        return False
    state["breakTimer"] = 20
    return True


def tick_shields(state, ticks=1, creative=False):
    for _unused in range(max(0, int(ticks))):
        if int(state.get("breakTimer", 0)) > 0:
            state["breakTimer"] = int(state["breakTimer"]) - 1
        if creative or int(state.get("temporary", 0)) <= 0:
            continue
        state["decayTimer"] = int(state.get("decayTimer", 240)) - 1
        if state["decayTimer"] <= 0 and int(state.get("breakTimer", 0)) <= 0:
            state["temporary"] = int(state["temporary"]) - 1
            state["decayTimer"] = 240 if state["temporary"] else 0
    return state


def can_recharge(kind, ingredients):
    return frozenset(str(value) for value in ingredients) == RECHARGE_INGREDIENTS.get(
        str(kind), frozenset()
    )


def recharge(state):
    state["charges"] = int(state["maxCharges"])
    return state["charges"]
