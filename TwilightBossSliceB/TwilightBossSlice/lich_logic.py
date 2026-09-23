# -*- coding: utf-8 -*-
"""Pure Twilight Lich and Death Tome rules from the locked 4.3.2508 JAR.

The module intentionally has no ModSDK imports.  The server adapter owns
entities and side effects while these functions own timings, phases and
damage decisions so desktop tests can exercise the complete state machine.
"""

import math


PHASE_SHADOW = 1
PHASE_MINION = 2
PHASE_MELEE = 3

MAX_HEALTH = 100.0
INITIAL_SHIELDS = 6
MAX_SHADOW_CLONES = 2
TOTAL_MINIONS = 9
MAX_ACTIVE_MINIONS = 3
HOME_RADIUS = 20.0
RETURN_HOME_SPEED = 1.25
TARGET_RANGE = 35.0
SPAWNER_RANGE = 9.0
INITIAL_ATTACK_COOLDOWN = 40
INITIAL_SPAWN_TIME = 20
SHADOW_ATTACK_COOLDOWN = 100
SHADOW_TELEPORT_MARK = 60
MINION_RANGED_COOLDOWN = 60
MINION_MELEE_COOLDOWN = 20
POP_COOLDOWN = 40
ABSORB_COOLDOWN = POP_COOLDOWN
SCEPTER_WINDUP_MIN = 20
SCEPTER_WINDUP_RANDOM = 20
PROJECTILE_RANGE = 20.0
SOURCE_PROJECTILE_SPEED = 0.5
SOURCE_PROJECTILE_INACCURACY = 1.0
REFLECTED_PROJECTILE_SPEED = 1.5
REFLECTED_PROJECTILE_INACCURACY = 0.1
BASE_UNDEAD_HEALING_DAMAGE = 6.0
DEATH_TICKS = 175
XP_REWARD = 217
PROJECTILE_TTL_TICKS = 200
PROJECTILE_STALL_TICKS = 6
PROJECTILE_MIN_MOTION_SQ = 0.000001

SHIELD_BREAKING_SOURCES = frozenset(
    (
        "magic",
        "indirect_magic",
        "sonic_boom",
        "lich_bolt",
        "reflected_lich_bolt",
        "twilight_scepter",
    )
)


def landmark_death_is_authoritative(state):
    """Return whether this Lich came from a landmark boss marker."""
    return bool(state and state.get("worldgenManaged", False))


def new_lich_state(spawner_spawned=False):
    return {
        "health": MAX_HEALTH,
        "maxHealth": MAX_HEALTH,
        "shieldStrength": INITIAL_SHIELDS,
        "minionsRemaining": TOTAL_MINIONS,
        "activeMinions": 0,
        "cloneCount": 0,
        "phase": PHASE_SHADOW,
        "attackCooldown": (
            INITIAL_ATTACK_COOLDOWN if spawner_spawned else 0
        ),
        "popCooldown": 0,
        "scepterTime": 0,
        "spawnTime": INITIAL_SPAWN_TIME if spawner_spawned else 0,
        "nextAttackType": 0,
        "castKind": None,
        "castTargetId": None,
        "castTargetHealth": 0.0,
        "dying": False,
        "deathTime": 0,
    }


def new_clone_state(owner_id, attack_cooldown):
    return {
        "ownerId": owner_id,
        "attackCooldown": max(0, int(attack_cooldown)),
        "nextAttackType": 0,
        "targetId": None,
        "orphanTicks": 0,
    }


def refresh_phase(state):
    if int(state.get("shieldStrength", 0)) > 0:
        state["phase"] = PHASE_SHADOW
    elif (
        int(state.get("minionsRemaining", 0)) > 0
        or int(state.get("activeMinions", 0)) > 0
    ):
        state["phase"] = PHASE_MINION
    else:
        state["phase"] = PHASE_MELEE
    return state["phase"]


def resolve_incoming_damage(state, source_kind, amount, confirmed_healing_contact=False):
    """Apply the locked-JAR shield damage tag and friendly-fire gates."""
    amount = max(0.0, float(amount))
    phase = refresh_phase(state)
    # NetEase reports zero recovery for instant healing on a full-health
    # custom actor. This explicitly authorized engine contact removes one
    # shield, without inventing an unobservable damage amount.
    healing_contact = bool(confirmed_healing_contact
                           and source_kind == "magic" and amount == 0.0
                           and phase == PHASE_SHADOW)
    result = {
        "accepted": False,
        "healthDamage": 0.0,
        "shieldDamage": 0,
        "shieldContact": False,
        "phase": phase,
    }
    if source_kind == "lich_owned" or (amount <= 0.0 and not healing_contact):
        return result
    if source_kind == "bypass":
        state["health"] = max(0.0, float(state.get("health", 0.0)) - amount)
        result["accepted"] = True
        result["healthDamage"] = amount
        return result
    if phase == PHASE_SHADOW:
        result["shieldContact"] = True
        if (source_kind not in SHIELD_BREAKING_SOURCES
                or (amount <= 2.0 and not healing_contact)):
            return result
        state["shieldStrength"] = max(
            0, int(state.get("shieldStrength", 0)) - 1
        )
        result["accepted"] = True
        result["shieldDamage"] = 1
        result["phase"] = refresh_phase(state)
        return result
    state["health"] = max(0.0, float(state.get("health", 0.0)) - amount)
    result["accepted"] = True
    result["healthDamage"] = amount
    return result


def effect_damage_source_kind(cause, attribute_buff_type):
    """Recover potion/status magic when the health event omits its cause."""
    normalized = str(cause or "").lower().replace(" ", "_")
    if "indirect" in normalized and "magic" in normalized:
        return "indirect_magic"
    if "magic" in normalized:
        return "magic"
    if "sonic" in normalized:
        return "sonic_boom"
    try:
        effect_type = int(attribute_buff_type)
    except (TypeError, ValueError):
        effect_type = -1
    # NetEase AttributeBuffType: Heal=3, Harm=4, Magic=5.  Healing harms
    # undead entities, so all three are magic damage for the Lich shield.
    if effect_type in (3, 4, 5):
        return "magic"
    return None


def lich_bolt_source_kind(reflected, owner_is_lich):
    """Keep a Lich's own bolt harmless until a non-Lich reflects it."""
    if bool(owner_is_lich) and not bool(reflected):
        return "lich_owned"
    return "reflected_lich_bolt" if bool(reflected) else "lich_bolt"


def new_projectile_state(
    projectile_type, owner_id, current_tick, velocity=None, reflected=False
):
    return {
        "type": str(projectile_type),
        "ownerId": owner_id,
        "reflected": bool(reflected),
        "spawnTick": int(current_tick),
        "expires": int(current_tick) + PROJECTILE_TTL_TICKS,
        "velocity": tuple(velocity) if velocity is not None else None,
        "stalledSince": None,
    }


def projectile_lifecycle_action(state, current_tick, entity_exists, motion):
    """Return keep/forget/destroy and update bounded stall bookkeeping."""
    if not bool(entity_exists):
        return "forget"
    current_tick = int(current_tick)
    if current_tick >= int(
        state.get("expires", current_tick + PROJECTILE_TTL_TICKS)
    ):
        return "destroy"
    if motion is None:
        return "keep"
    try:
        motion = tuple(float(value) for value in motion[:3])
    except (TypeError, ValueError):
        return "keep"
    motion_sq = sum(value * value for value in motion)
    if motion_sq > PROJECTILE_MIN_MOTION_SQ:
        state["velocity"] = motion
        state["stalledSince"] = None
        return "keep"
    stalled_since = state.get("stalledSince")
    if stalled_since is None:
        state["stalledSince"] = current_tick
        return "keep"
    if current_tick - int(stalled_since) >= PROJECTILE_STALL_TICKS:
        return "destroy"
    return "keep"


def _tick_cooldowns(state, has_target, has_line_of_sight):
    actions = []
    spawn_time = max(0, int(state.get("spawnTime", 0)))
    if int(state.get("attackCooldown", 0)) > 0 and spawn_time <= 0:
        state["attackCooldown"] = int(state["attackCooldown"]) - 1
    if (
        int(state.get("popCooldown", 0)) > 0
        and float(state.get("health", 0.0))
        < float(state.get("maxHealth", MAX_HEALTH))
        and int(state.get("scepterTime", 0)) <= 0
    ):
        state["popCooldown"] = int(state["popCooldown"]) - 1
    if int(state.get("scepterTime", 0)) > 0:
        state["scepterTime"] = int(state["scepterTime"]) - 1
    if has_target and has_line_of_sight and spawn_time > 0:
        state["spawnTime"] = spawn_time - 1
        if int(state["spawnTime"]) == 0:
            actions.append({"type": "extinguish_candles"})
    return actions


def _begin_cast(state, kind, target, rng):
    state["castKind"] = str(kind)
    state["castTargetId"] = target.get("id")
    state["castTargetHealth"] = max(0.0, float(target.get("health", 0.0)))
    state["scepterTime"] = SCEPTER_WINDUP_MIN + int(
        rng.randrange(SCEPTER_WINDUP_RANDOM)
    )
    return {"type": "start_%s" % kind, "targetId": target.get("id")}


def cancel_scepter_cast(state):
    state["castKind"] = None
    state["castTargetId"] = None
    state["castTargetHealth"] = 0.0
    state["scepterTime"] = 0


def add_pop_healing(state, target_count):
    target_count = max(0, int(target_count))
    before = float(state.get("health", 0.0))
    state["health"] = min(
        float(state.get("maxHealth", MAX_HEALTH)),
        before + 2.0 * target_count,
    )
    return state["health"] - before


def _finish_cast(state):
    kind = state.get("castKind")
    target_id = state.get("castTargetId")
    target_health = max(0.0, float(state.get("castTargetHealth", 0.0)))
    before = float(state.get("health", 0.0))
    if kind == "pop":
        healed = add_pop_healing(state, 1)
        action = {
            "type": "pop_mob",
            "targetId": target_id,
            "healed": healed,
        }
    elif kind == "absorb":
        state["health"] = min(
            float(state.get("maxHealth", MAX_HEALTH)),
            before + target_health,
        )
        state["activeMinions"] = max(
            0, int(state.get("activeMinions", 0)) - 1
        )
        action = {
            "type": "absorb_minion",
            "targetId": target_id,
            "healed": state["health"] - before,
        }
    else:
        cancel_scepter_cast(state)
        return None
    state["popCooldown"] = POP_COOLDOWN
    cancel_scepter_cast(state)
    return action


def _choose_next_shadow_attack(state, rng):
    state["nextAttackType"] = 0 if int(rng.randrange(3)) > 0 else 1


def _shadow_actions(state, distance, has_line_of_sight, rng, spawn_clones):
    actions = []
    attack_cooldown = int(state.get("attackCooldown", 0))
    if attack_cooldown == SHADOW_TELEPORT_MARK:
        actions.append({"type": "teleport"})
        if spawn_clones and int(state.get("cloneCount", 0)) < MAX_SHADOW_CLONES:
            actions.append({"type": "spawn_clone"})
            state["cloneCount"] = int(state.get("cloneCount", 0)) + 1
    if (
        attack_cooldown <= 0
        and has_line_of_sight
        and distance < PROJECTILE_RANGE
    ):
        projectile = (
            "bomb" if int(state.get("nextAttackType", 0)) != 0 else "bolt"
        )
        actions.append({"type": "shoot_%s" % projectile})
        _choose_next_shadow_attack(state, rng)
        state["attackCooldown"] = SHADOW_ATTACK_COOLDOWN
    return actions


def advance_combat_tick(
    state,
    target_distance,
    has_line_of_sight,
    rng,
    pop_target=None,
    minion_target=None,
    has_target=True,
):
    """Advance one source-style boss tick and return declarative actions."""
    actions = _tick_cooldowns(state, has_target, has_line_of_sight)
    if state.get("castKind"):
        if int(state.get("scepterTime", 0)) <= 0:
            completed = _finish_cast(state)
            if completed is not None:
                actions.append(completed)
        return actions
    if (
        pop_target is not None
        and int(state.get("popCooldown", 0)) <= 0
        and float(state.get("health", 0.0))
        < float(state.get("maxHealth", MAX_HEALTH))
    ):
        actions.append(_begin_cast(state, "pop", pop_target, rng))
        return actions
    if (
        minion_target is not None
        and float(state.get("health", 0.0))
        < float(state.get("maxHealth", MAX_HEALTH)) / 2.0
        and int(state.get("activeMinions", 0)) > 0
    ):
        actions.append(_begin_cast(state, "absorb", minion_target, rng))
        return actions

    if not has_target:
        return actions

    phase = refresh_phase(state)
    distance = max(0.0, float(target_distance))
    attack_cooldown = int(state.get("attackCooldown", 0))
    if phase == PHASE_SHADOW:
        actions.extend(
            _shadow_actions(state, distance, has_line_of_sight, rng, True)
        )
    elif phase == PHASE_MINION:
        if (
            attack_cooldown % 15 == 0
            and int(state.get("minionsRemaining", 0)) > 0
            and int(state.get("activeMinions", 0)) < MAX_ACTIVE_MINIONS
        ):
            actions.append({"type": "spawn_minion"})
            state["minionsRemaining"] = int(state["minionsRemaining"]) - 1
            state["activeMinions"] = int(state["activeMinions"]) + 1
        if attack_cooldown <= 0:
            if distance < 2.0:
                actions.append({"type": "melee", "damage": 3.0})
                state["attackCooldown"] = MINION_MELEE_COOLDOWN
            elif has_line_of_sight and distance < PROJECTILE_RANGE:
                projectile = (
                    "bomb"
                    if int(state.get("nextAttackType", 0)) != 0
                    else "bolt"
                )
                actions.append({"type": "shoot_%s" % projectile})
                state["nextAttackType"] = int(rng.randrange(2))
                state["attackCooldown"] = MINION_RANGED_COOLDOWN
            else:
                actions.append({"type": "teleport"})
                state["attackCooldown"] = MINION_MELEE_COOLDOWN
    elif distance < 2.0 and attack_cooldown <= 0:
        actions.append({"type": "melee", "damage": 3.0})
        state["attackCooldown"] = MINION_MELEE_COOLDOWN
    elif distance >= 2.0:
        actions.append({"type": "chase"})
    return actions


def advance_clone_tick(state, target_distance, has_line_of_sight, rng):
    if int(state.get("attackCooldown", 0)) > 0:
        state["attackCooldown"] = int(state["attackCooldown"]) - 1
    return _shadow_actions(
        state,
        max(0.0, float(target_distance)),
        bool(has_line_of_sight),
        rng,
        False,
    )


def minion_removed(state):
    state["activeMinions"] = max(0, int(state.get("activeMinions", 0)) - 1)
    return refresh_phase(state)


def absorb_minion(state, minion_health):
    """Compatibility helper for adapters; source-style casts use the tick API."""
    if (
        float(state.get("health", 0.0)) >= float(state.get("maxHealth", MAX_HEALTH)) / 2.0
        or int(state.get("activeMinions", 0)) <= 0
    ):
        return {"absorbed": False, "healed": 0.0}
    healed = max(0.0, float(minion_health))
    before = float(state.get("health", 0.0))
    state["health"] = min(float(state.get("maxHealth", MAX_HEALTH)), before + healed)
    state["activeMinions"] = max(0, int(state["activeMinions"]) - 1)
    state["popCooldown"] = POP_COOLDOWN
    return {"absorbed": True, "healed": state["health"] - before}


def should_teleport_after_hurt(phase, rng):
    denominator = 6 if int(phase) == PHASE_MELEE else 3
    return int(rng.randrange(denominator)) == 0


def clone_damage_is_blocked(is_bypass):
    return not bool(is_bypass)


def player_can_activate_spawner(player_position, spawner_position):
    if float(player_position[1]) <= float(spawner_position[1]) - 4.0:
        return False
    dx = float(player_position[0]) - float(spawner_position[0])
    dy = float(player_position[1]) - float(spawner_position[1])
    dz = float(player_position[2]) - float(spawner_position[2])
    return dx * dx + dy * dy + dz * dz <= SPAWNER_RANGE * SPAWNER_RANGE


def should_return_home(distance):
    """Whether the source restriction goal may navigate back to its home."""
    return max(0.0, float(distance)) > HOME_RADIUS


def aim_projectile_velocity(delta, speed, inaccuracy, rng):
    length = math.sqrt(sum(float(value) ** 2 for value in delta))
    if length <= 0.000001:
        return (0.0, 0.0, 0.0)
    direction = [float(value) / length for value in delta]
    spread = 0.0172275 * max(0.0, float(inaccuracy))
    if spread > 0.0:
        direction = [
            value + float(rng.triangular(-spread, spread, 0.0))
            for value in direction
        ]
    return tuple(value * float(speed) for value in direction)


def reflect_bolt(owner_id, look_vector, rng=None):
    if rng is None:
        length = math.sqrt(sum(float(value) ** 2 for value in look_vector))
        velocity = (
            (0.0, 0.0, 0.0)
            if length <= 0.000001
            else tuple(
                float(value) / length * REFLECTED_PROJECTILE_SPEED
                for value in look_vector
            )
        )
    else:
        velocity = aim_projectile_velocity(
            look_vector,
            REFLECTED_PROJECTILE_SPEED,
            REFLECTED_PROJECTILE_INACCURACY,
            rng,
        )
    return {
        "ownerId": owner_id,
        "velocity": velocity,
        "inaccuracy": REFLECTED_PROJECTILE_INACCURACY,
    }


def teleport_candidate(target_position, rng):
    return (
        float(target_position[0]) + float(rng.gauss(0.0, 1.0)) * 16.0,
        float(target_position[1]),
        float(target_position[2]) + float(rng.gauss(0.0, 1.0)) * 16.0,
    )


def serialize_persistent_state(state):
    home = state.get("home")
    return {
        "schema": 2,
        "lastLootingLevel": max(0, int(state.get("lastLootingLevel", 0))),
        "lootDeliveryKey": state.get("lootDeliveryKey"),
        "health": float(state.get("health", MAX_HEALTH)),
        "maxHealth": float(state.get("maxHealth", MAX_HEALTH)),
        "shieldStrength": int(state.get("shieldStrength", INITIAL_SHIELDS)),
        "minionsRemaining": int(state.get("minionsRemaining", TOTAL_MINIONS)),
        "activeMinions": int(state.get("activeMinions", 0)),
        "cloneCount": int(state.get("cloneCount", 0)),
        "attackCooldown": int(state.get("attackCooldown", 0)),
        "popCooldown": int(state.get("popCooldown", 0)),
        "scepterTime": int(state.get("scepterTime", 0)),
        "spawnTime": int(state.get("spawnTime", 0)),
        "nextAttackType": int(state.get("nextAttackType", 0)),
        "castKind": state.get("castKind"),
        "castTargetId": state.get("castTargetId"),
        "castTargetHealth": float(state.get("castTargetHealth", 0.0)),
        "home": list(home) if home is not None else None,
        "dimensionId": state.get("dimensionId"),
        "participants": sorted(str(value) for value in state.get("participants", set())),
        "dead": bool(state.get("dead", False)),
        "lootAwarded": bool(state.get("lootAwarded", False)),
        "dying": bool(state.get("dying", False)),
        "deathTime": max(0, int(state.get("deathTime", 0))),
        "worldgenManaged": bool(state.get("worldgenManaged", False)),
    }


def restore_persistent_state(value):
    state = new_lich_state()
    if not isinstance(value, dict):
        return state
    state["lootDeliveryKey"] = value.get("lootDeliveryKey")
    integer_fields = (
        "lastLootingLevel",
        "shieldStrength",
        "minionsRemaining",
        "activeMinions",
        "cloneCount",
        "attackCooldown",
        "popCooldown",
        "scepterTime",
        "spawnTime",
        "nextAttackType",
    )
    for key in integer_fields:
        if key in value:
            state[key] = max(0, int(value[key]))
    for key in ("health", "maxHealth", "castTargetHealth"):
        if key in value:
            state[key] = max(0.0, float(value[key]))
    state["health"] = min(state["health"], state["maxHealth"])
    state["castKind"] = value.get("castKind")
    state["castTargetId"] = value.get("castTargetId")
    home = value.get("home")
    if isinstance(home, (tuple, list)) and len(home) >= 3:
        state["home"] = tuple(float(home[index]) for index in range(3))
    if value.get("dimensionId") is not None:
        state["dimensionId"] = int(value["dimensionId"])
    state["participants"] = set(
        str(item) for item in value.get("participants", ())
    )
    state["dead"] = bool(value.get("dead", False))
    state["lootAwarded"] = bool(value.get("lootAwarded", False))
    state["dying"] = bool(value.get("dying", False))
    state["deathTime"] = max(0, int(value.get("deathTime", 0)))
    state["worldgenManaged"] = bool(value.get("worldgenManaged", False))
    refresh_phase(state)
    return state


def death_tome_incoming_damage(amount, is_fire):
    amount = max(0.0, float(amount))
    return amount * 2.0 if bool(is_fire) else amount


def death_tome_slow_ticks(difficulty):
    return (0, 40, 120, 160)[max(0, min(3, int(difficulty)))]
