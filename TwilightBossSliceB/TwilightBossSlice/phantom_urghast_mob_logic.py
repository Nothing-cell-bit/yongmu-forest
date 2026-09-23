# -*- coding: utf-8 -*-
"""Pure AI contracts for non-boss mobs on the Phantom/Ur-Ghast route.

The Bedrock component files handle ordinary navigation and targeting.  This
module owns the source-specific temporal rules which components cannot express
without losing cooldown, shield, rider, or block-wake semantics.
"""

from __future__ import division


BLOCK_CHAIN_GOBLIN = "tf_slice:block_chain_goblin"
LOWER_GOBLIN_KNIGHT = "tf_slice:lower_goblin_knight"
UPPER_GOBLIN_KNIGHT = "tf_slice:upper_goblin_knight"
TOWER_BROODLING = "tf_slice:tower_broodling"
TOWERWOOD_BORER = "tf_slice:towerwood_borer"

CHAIN_MAX_DISTANCE_SQ = 42.0
CHAIN_RANDOM_BOUND = 56
CHAIN_COOLDOWN_MIN = 100
CHAIN_COOLDOWN_SPREAD = 100
CHAIN_RETURN_TICKS = 15
CHAIN_EXPIRE_TICKS = 80

HEAVY_SPEAR_TIMER_START = 60
HEAVY_SPEAR_LAND_TICK = 25
HEAVY_SPEAR_RADIUS = 1.5
SHIELD_DAMAGE_THRESHOLD = 10.0

BORER_WAKE_STEPS = 21
GHAST_WARN_TICK = 10
GHAST_FIRE_TICK = 20
GHAST_COOLDOWN_TICKS = 40
BOSS_MINION_HEALTH = 6.0
BOSS_MINION_WANDER_FACTOR = 0.005


def create_mob_state(identifier):
    """Return serializable, server-owned state for a route mob."""
    return {
        "type": str(identifier),
        "targetId": None,
        "chainCooldown": 0,
        "chainProjectileId": None,
        "heavySpearTimer": 0,
        "heavySpearLanded": False,
        "shield": True,
        "riderId": None,
        "mountId": None,
        "borerWakeRemaining": 0,
        "ghastAttackTimer": 0,
        "ghastCharging": False,
        "bossMinion": False,
    }


def advance_chain_throw(
    state,
    distance_sq,
    has_sight,
    random_roll,
    cooldown_roll=0,
):
    """Advance the locked ThrowSpikeBlockGoal start/cooldown predicate."""
    cooldown = max(0, int(state.get("chainCooldown", 0)))
    if cooldown > 0:
        state["chainCooldown"] = cooldown - 1
        return {"launch": False, "cooldown": state["chainCooldown"]}
    can_launch = (
        state.get("chainProjectileId") is None
        and float(distance_sq) <= CHAIN_MAX_DISTANCE_SQ
        and bool(has_sight)
        and int(random_roll) % CHAIN_RANDOM_BOUND == 0
    )
    if not can_launch:
        return {"launch": False, "cooldown": 0}
    state["chainCooldown"] = CHAIN_COOLDOWN_MIN + (
        int(cooldown_roll) % CHAIN_COOLDOWN_SPREAD
    )
    return {"launch": True, "cooldown": state["chainCooldown"]}


def chain_projectile_phase(age_ticks, returning=False):
    age_ticks = max(0, int(age_ticks))
    return {
        "returning": bool(returning or age_ticks >= CHAIN_RETURN_TICKS),
        "expired": age_ticks > CHAIN_EXPIRE_TICKS,
    }


def start_heavy_spear(state):
    state["heavySpearTimer"] = HEAVY_SPEAR_TIMER_START
    state["heavySpearLanded"] = False
    return state["heavySpearTimer"]


def advance_heavy_spear(state, has_valid_target):
    timer = max(0, int(state.get("heavySpearTimer", 0)))
    if timer <= 0 or not has_valid_target:
        if not has_valid_target:
            state["heavySpearTimer"] = 0
            state["heavySpearLanded"] = False
        return {"active": False, "land": False, "timer": 0}
    timer -= 1
    state["heavySpearTimer"] = timer
    land = timer == HEAVY_SPEAR_LAND_TICK and not state.get(
        "heavySpearLanded", False
    )
    if land:
        state["heavySpearLanded"] = True
    if timer == 0:
        state["heavySpearLanded"] = False
    return {"active": timer > 0, "land": land, "timer": timer}


def shield_hit_result(amount, shield_present, from_front=True, hit_count=0):
    blocked = bool(shield_present and from_front)
    return {
        "blocked": blocked,
        "healthDamage": 0.0 if blocked else max(0.0, float(amount)),
        "breakShield": bool(
            blocked and float(amount) > SHIELD_DAMAGE_THRESHOLD and int(hit_count) >= 2
        ),
    }


def rider_spear_freezes_mount(timer, has_rider, has_valid_target):
    return bool(
        has_rider
        and has_valid_target
        and 0 < int(timer) < HEAVY_SPEAR_TIMER_START
    )


def notify_borer_hurt(state):
    state["borerWakeRemaining"] = BORER_WAKE_STEPS
    return True


def advance_borer_summon(state, block_kind):
    """Consume one of the 21 source scan steps after a borer is hurt."""
    remaining = max(0, int(state.get("borerWakeRemaining", 0)))
    if remaining <= 0:
        return []
    state["borerWakeRemaining"] = remaining - 1
    kind = str(block_kind or "")
    if kind in ("infested", "towerwood", "cracked_towerwood"):
        return [{
            "kind": "wake_borer",
            "scanIndex": BORER_WAKE_STEPS - remaining,
            "replaceBlock": "tf_slice:towerwood",
        }]
    return [{
        "kind": "scan_empty",
        "scanIndex": BORER_WAKE_STEPS - remaining,
    }]


def carminite_golem_hit_result():
    """Return the source golem's successful-melee side effects."""
    return {"verticalMotion": 0.4, "attackTimer": 10}


def broodling_companion_count(spawn_more, random_roll):
    """Tower broodlings inherit the swarm-spider companion spawn contract."""
    if not spawn_more:
        return 0
    return 1 + (int(random_roll) % 2)


def advance_ghast_attack(state, has_target, in_range, has_sight):
    """Advance GhastguardAttackGoal's warn/fire/cooldown timeline."""
    timer = int(state.get("ghastAttackTimer", 0))
    if not has_target:
        state["ghastAttackTimer"] = 0
        state["ghastCharging"] = False
        return {"warn": False, "fire": False, "charging": False, "timer": 0}
    if in_range and has_sight:
        timer += 1
    elif timer > 0:
        timer -= 1
    warn = timer == GHAST_WARN_TICK
    fire = timer == GHAST_FIRE_TICK
    if fire:
        timer = -GHAST_COOLDOWN_TICKS
    state["ghastAttackTimer"] = timer
    state["ghastCharging"] = timer > GHAST_WARN_TICK
    return {
        "warn": warn,
        "fire": fire,
        "charging": state["ghastCharging"],
        "timer": timer,
    }


def mini_ghast_should_attack(
    distance,
    look_dot,
    has_sight,
    wearing_pumpkin=False,
):
    """Mirror CarminiteGhastling's pumpkin and player-gaze attack gate."""
    if wearing_pumpkin or not has_sight:
        return False
    distance = max(0.0, float(distance))
    if distance <= 3.5:
        return True
    return float(look_dot) > 1.0 - 0.025 / max(distance, 0.001)
