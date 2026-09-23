# -*- coding: utf-8 -*-
"""Pure state transitions for Dark Tower mechanisms and consumables."""

from __future__ import division

import math
import random


BUILDER_RANGE = 16
BUILDER_STEP_TICKS = 10
BUILDER_STOP_DELAY_TICKS = 60
BUILDER_REMOVE_STEP_TICKS = 10
BUILDER_IDLE_POWER_POLL_TICKS = 20
ANTIBUILDER_RADIUS = 4
REACTOR_TOTAL_TICKS = 350
REACTOR_NETHER_ORES = (
    "minecraft:nether_quartz_ore",
    "minecraft:nether_gold_ore",
)
REACTOR_IMMUNE_BLOCKS = frozenset((
    "minecraft:barrier",
    "minecraft:bedrock",
    "minecraft:end_portal",
    "minecraft:end_portal_frame",
    "minecraft:end_gateway",
    "minecraft:command_block",
    "minecraft:repeating_command_block",
    "minecraft:chain_command_block",
    "minecraft:structure_block",
    "minecraft:jigsaw",
    "minecraft:moving_piston",
    "minecraft:light",
    "minecraft:reinforced_deepslate",
    "tf_slice:naga_boss_spawner",
    "tf_slice:lich_boss_spawner",
    "tf_slice:minoshroom_boss_spawner",
    "tf_slice:hydra_boss_spawner",
    "tf_slice:knight_phantom_boss_spawner",
    "tf_slice:ur_ghast_boss_spawner",
    "tf_slice:alpha_yeti_boss_spawner",
    "tf_slice:snow_queen_boss_spawner",
    "tf_slice:final_boss_boss_spawner",
    "tf_slice:stronghold_shield",
    "tf_slice:unbreakable_vanishing_block",
    "tf_slice:locked_vanishing_block",
    "tf_slice:tower_key_door",
    "tf_slice:pink_force_field",
    "tf_slice:orange_force_field",
    "tf_slice:green_force_field",
    "tf_slice:blue_force_field",
    "tf_slice:violet_force_field",
    "tf_slice:keepsake_casket",
    "tf_slice:trophy_pedestal",
))
ANTIBUILDER_IGNORED_BLOCKS = REACTOR_IMMUNE_BLOCKS.union(frozenset((
    "minecraft:redstone_lamp",
    "minecraft:tnt",
    "minecraft:water",
    "tf_slice:carminite_antibuilder",
    "tf_slice:carminite_builder",
    # The NetEase port's temporary bridge block is the locked source's
    # twilightforest:built_block.  Both the current and captured state must be
    # ignored so a nearby antibuilder cannot erase a live builder path.
    "tf_slice:temporary_builder_block",
    "tf_slice:reactor_debris",
    "tf_slice:carminite_reactor",
    "tf_slice:reappearing_block",
    "tf_slice:ghast_trap",
    "tf_slice:fake_diamond",
    "tf_slice:fake_gold",
)))
EXPERIMENT_115_SERVINGS = 8
LIFE_CHARM_HEALTH = 8
LIFE_CHARM_REGENERATION_TICKS = 100
VANISHING_CHAIN_LIMIT = 512
# Locked 4.3.2508 behavior: an 80-tick red vanished trace followed by a
# 15-tick green active trace before the full block becomes solid again.
REAPPEARING_RED_TRACE_TICKS = 80
REAPPEARING_GREEN_TRACE_TICKS = 15
REAPPEARING_RESTORE_TICKS = (
    REAPPEARING_RED_TRACE_TICKS + REAPPEARING_GREEN_TRACE_TICKS
)
VANISHING_MIN_DELAY_TICKS = 2
VANISHING_MAX_DELAY_TICKS = 6
LOCKED_DOOR_BLOCKS = frozenset((
    "tf_slice:tower_key_door",
    "tf_slice:locked_vanishing_block",
))


def connected_block_component(
    block_names,
    origin,
    allowed_names,
    limit=VANISHING_CHAIN_LIMIT,
):
    """Return the bounded six-connected mechanism group containing ``origin``.

    ``block_names`` is intentionally a plain mapping so the propagation rule
    remains unit-testable outside the NetEase runtime.  The source block uses a
    512-block safety cap when a connected vanishing wall wakes its neighbors.
    """
    origin = tuple(int(value) for value in origin)
    allowed_names = set(str(value) for value in allowed_names)
    limit = max(0, int(limit))
    if limit <= 0 or str(block_names.get(origin, "")) not in allowed_names:
        return []
    seen = set((origin,))
    pending = [origin]
    result = []
    while pending and len(result) < limit:
        current = pending.pop(0)
        result.append(current)
        for delta in (
            (-1, 0, 0),
            (1, 0, 0),
            (0, -1, 0),
            (0, 1, 0),
            (0, 0, -1),
            (0, 0, 1),
        ):
            neighbor = tuple(current[index] + delta[index] for index in range(3))
            if neighbor in seen:
                continue
            seen.add(neighbor)
            if str(block_names.get(neighbor, "")) in allowed_names:
                pending.append(neighbor)
    return result


def _vanishing_delay(parent, position):
    """Return a stable source-equivalent delay in the inclusive 2..6 range."""
    parent = parent or (0, 0, 0)
    value = 0
    for index in range(3):
        value ^= (int(position[index]) * (73856093 + index * 9749))
        value ^= (int(parent[index]) * (19349663 + index * 7919))
    return VANISHING_MIN_DELAY_TICKS + (
        abs(value) % (
            VANISHING_MAX_DELAY_TICKS - VANISHING_MIN_DELAY_TICKS + 1
        )
    )


def _build_vanishing_wave(
    component,
    origin,
    current_tick,
    restore_block=None,
    restore_ticks=REAPPEARING_RESTORE_TICKS,
    delay_for=None,
):
    """Schedule the source block's delayed six-neighbor activation wave."""
    positions = set(tuple(int(value) for value in item) for item in component)
    origin = tuple(int(value) for value in origin)
    if origin not in positions:
        return {}
    delay_for = delay_for or _vanishing_delay
    vanish_ticks = {
        origin: int(current_tick) + int(delay_for(None, origin))
    }
    pending = [origin]
    while pending:
        current = pending.pop(0)
        for delta in (
            (-1, 0, 0), (1, 0, 0),
            (0, -1, 0), (0, 1, 0),
            (0, 0, -1), (0, 0, 1),
        ):
            neighbor = tuple(
                current[index] + delta[index] for index in range(3)
            )
            if neighbor in positions and neighbor not in vanish_ticks:
                vanish_ticks[neighbor] = (
                    vanish_ticks[current] + int(delay_for(current, neighbor))
                )
                pending.append(neighbor)
    records = {}
    for position, vanish_tick in vanish_ticks.items():
        record = {
            "kind": "reappearing" if restore_block else "vanishing",
            "position": list(position),
            "phase": "pending_vanish",
            "vanishTick": vanish_tick,
        }
        if restore_block:
            record["traceActiveTick"] = (
                vanish_tick
                + min(
                    REAPPEARING_RED_TRACE_TICKS,
                    max(0, int(restore_ticks)),
                )
            )
            record["restoreTick"] = vanish_tick + int(restore_ticks)
            record["restoreBlock"] = str(restore_block)
        records[position] = record
    return records


def build_vanishing_wave(component, origin, current_tick, delay_for=None):
    """Schedule a permanent vanishing-block wave without an all-at-once delete."""
    return _build_vanishing_wave(
        component,
        origin,
        current_tick,
        delay_for=delay_for,
    )


def build_reappearing_wave(
    component,
    origin,
    current_tick,
    restore_ticks=REAPPEARING_RESTORE_TICKS,
    delay_for=None,
):
    """Schedule a staggered wave whose blocks each restore after 95 ticks."""
    return _build_vanishing_wave(
        component,
        origin,
        current_tick,
        "tf_slice:reappearing_block",
        restore_ticks,
        delay_for,
    )


def has_locked_door_blocks(block_names):
    """Return whether a connected vanishing door still contains a key lock."""
    return any(str(name) in LOCKED_DOOR_BLOCKS for name in block_names)


def should_activate_builder(previous_powered, current_powered):
    """Return true only for the source builder's redstone rising edge."""
    return bool(current_powered) and not bool(previous_powered)


def create_builder_state(origin):
    """Create the source builder's delayed, incremental runtime state."""
    origin = tuple(int(value) for value in origin)
    if len(origin) != 3:
        raise ValueError("builder origin must be 3D")
    return {
        "kind": "builder_power",
        "position": list(origin),
        "powered": False,
        "active": False,
        "phase": "inactive",
        "builderState": "inactive",
        "ticksRunning": 0,
        "ticksStopped": 0,
        "blocksMade": 0,
        "cursor": list(origin),
        "trackedPlayerId": None,
        "builtBlocks": [],
        "cleanupIndex": 0,
        "cleanupTicks": 0,
        "afterCleanupState": "inactive",
        # The first block-entity tick must detect a lever which was already on
        # when the chunk loaded. Later idle probes are bounded to once/second.
        "powerProbeTicks": BUILDER_IDLE_POWER_POLL_TICKS - 1,
    }


def _normalize_builder_state(state):
    phase = str(state.get("phase", ""))
    if phase not in (
        "inactive", "building", "waiting_cleanup", "cleaning", "timeout"
    ):
        phase = "building" if state.get("active") else "inactive"
    state["phase"] = phase
    state.setdefault("builderState", "active" if state.get("active") else phase)
    state.setdefault("ticksRunning", 0)
    state.setdefault("ticksStopped", 0)
    state.setdefault("blocksMade", 0)
    state.setdefault("builtBlocks", [])
    state.setdefault("cleanupIndex", 0)
    state.setdefault("cleanupTicks", 0)
    state.setdefault("afterCleanupState", "inactive")
    state.setdefault("powerProbeTicks", BUILDER_IDLE_POWER_POLL_TICKS - 1)
    return state


def builder_power_probe_due(state, neighbor_changed=False):
    """Bound idle redstone polling while keeping neighbor edges immediate."""
    _normalize_builder_state(state)
    if neighbor_changed:
        state["powerProbeTicks"] = 0
        return True
    ticks = int(state.get("powerProbeTicks", 0)) + 1
    if ticks >= BUILDER_IDLE_POWER_POLL_TICKS:
        state["powerProbeTicks"] = 0
        return True
    state["powerProbeTicks"] = ticks
    return False


def _start_builder_cleanup(state, builder_state):
    state["active"] = False
    state["trackedPlayerId"] = None
    state["builderState"] = str(builder_state)
    state["cleanupTicks"] = 0
    state["cleanupIndex"] = 0
    state["afterCleanupState"] = str(builder_state)
    if state.get("builtBlocks"):
        state["phase"] = "cleaning"
        return {
            "kind": "cleanup_started",
            "builderState": str(builder_state),
        }
    state["phase"] = str(builder_state)
    return {"kind": "stopped", "builderState": str(builder_state)}


def advance_builder(state, current_powered, facing):
    """Advance one block-entity tick and return the next builder event.

    Power only starts the machine.  The first placement happens after ten
    block-entity ticks, and ``facing`` is evaluated again for every later
    placement so the tracked player can steer the source builder path.
    """
    _normalize_builder_state(state)
    previous_powered = bool(state.get("powered"))
    current_powered = bool(current_powered)
    state["powered"] = current_powered
    phase = state["phase"]
    if (
        should_activate_builder(previous_powered, current_powered)
        and phase == "inactive"
    ):
        origin = tuple(int(value) for value in state.get("position", ()))
        if len(origin) != 3:
            raise ValueError("builder state position must be 3D")
        state["active"] = True
        state["phase"] = "building"
        state["builderState"] = "active"
        state["ticksRunning"] = 0
        state["ticksStopped"] = 0
        state["blocksMade"] = 0
        state["cursor"] = list(origin)
        state["trackedPlayerId"] = None
        state["builtBlocks"] = []
        state["cleanupIndex"] = 0
        state["cleanupTicks"] = 0
        return {"kind": "started", "builderState": "active"}
    if not current_powered:
        if phase in ("building", "waiting_cleanup"):
            return _start_builder_cleanup(state, "inactive")
        if phase == "cleaning":
            state["builderState"] = "inactive"
            state["afterCleanupState"] = "inactive"
        elif phase == "timeout":
            state["phase"] = "inactive"
            state["builderState"] = "inactive"
            return {"kind": "reset", "builderState": "inactive"}
    if state["phase"] == "cleaning":
        state["cleanupTicks"] = int(state.get("cleanupTicks", 0)) + 1
        if state["cleanupTicks"] % BUILDER_REMOVE_STEP_TICKS != 0:
            return None
        index = int(state.get("cleanupIndex", 0))
        built_blocks = list(state.get("builtBlocks") or ())
        if index >= len(built_blocks):
            state["phase"] = str(state.get("afterCleanupState", "inactive"))
            state["builderState"] = state["phase"]
            return {
                "kind": "cleanup_complete",
                "builderState": state["builderState"],
            }
        record = built_blocks[index]
        return {
            "kind": "remove",
            "position": tuple(record.get("position", ())),
            "restoreBlock": str(record.get("restoreBlock", "minecraft:air")),
        }
    if state["phase"] == "waiting_cleanup":
        state["ticksStopped"] = int(state.get("ticksStopped", 0)) + 1
        if state["ticksStopped"] < BUILDER_STOP_DELAY_TICKS:
            return None
        return _start_builder_cleanup(state, "timeout")
    if state["phase"] != "building":
        return None

    state["ticksRunning"] = int(state.get("ticksRunning", 0)) + 1
    if state["ticksRunning"] % BUILDER_STEP_TICKS != 0:
        return None
    # The locked source uses ``blocksMade <= RANGE``. Starting from zero, that
    # creates seventeen blocks before the following half-second check stops.
    if int(state.get("blocksMade", 0)) > BUILDER_RANGE:
        state["phase"] = "waiting_cleanup"
        state["ticksStopped"] = 0
        state["trackedPlayerId"] = None
        return {"kind": "waiting_cleanup", "reason": "range"}
    if facing is None:
        return None
    facing = tuple(int(value) for value in facing)
    if len(facing) != 3 or sum(abs(value) for value in facing) != 1:
        raise ValueError("builder facing must be a unit cardinal direction")
    cursor = tuple(int(value) for value in state.get("cursor", ()))
    if len(cursor) != 3:
        raise ValueError("builder cursor must be 3D")
    return {
        "kind": "place",
        "position": tuple(
            cursor[index] + facing[index] for index in range(3)
        ),
    }


def complete_builder_placement(
    state,
    position,
    succeeded,
    restore_block="minecraft:air",
):
    """Commit one attempted source builder step or stop on obstruction."""
    _normalize_builder_state(state)
    if not succeeded:
        state["phase"] = "waiting_cleanup"
        state["ticksStopped"] = 0
        state["trackedPlayerId"] = None
        return False
    position = tuple(int(value) for value in position)
    if len(position) != 3:
        raise ValueError("builder placement must be 3D")
    state["cursor"] = list(position)
    state["blocksMade"] = int(state.get("blocksMade", 0)) + 1
    state.setdefault("builtBlocks", []).append(
        {
            "position": list(position),
            "restoreBlock": str(restore_block or "minecraft:air"),
        }
    )
    return True


def complete_builder_removal(state, position, succeeded):
    """Commit one source-order cleanup step, retaining failures for retry."""
    _normalize_builder_state(state)
    if not succeeded:
        return False
    index = int(state.get("cleanupIndex", 0))
    built_blocks = list(state.get("builtBlocks") or ())
    if index >= len(built_blocks):
        return False
    expected = tuple(int(value) for value in built_blocks[index]["position"])
    actual = tuple(int(value) for value in position)
    if actual != expected:
        return False
    state["cleanupIndex"] = index + 1
    state["cleanupTicks"] = 0
    if state["cleanupIndex"] >= len(built_blocks):
        state["builtBlocks"] = []
        state["cleanupIndex"] = 0
        state["phase"] = str(state.get("afterCleanupState", "inactive"))
        state["builderState"] = state["phase"]
    return True


def is_authored_dark_tower_lever(block_name, landmark_kind):
    """Let native levers inside the authored Dark Tower bypass route guards."""
    return (
        str(block_name) == "minecraft:lever"
        and str(landmark_kind) == "dark_tower"
    )


def builder_path(origin, facing):
    origin = tuple(int(value) for value in origin)
    facing = tuple(int(value) for value in facing)
    if len(origin) != 3 or len(facing) != 3:
        raise ValueError("builder origin and facing must be 3D")
    if sum(abs(value) for value in facing) != 1:
        raise ValueError("builder facing must be a unit cardinal direction")
    return [
        tuple(origin[index] + facing[index] * step for index in range(3))
        for step in range(1, BUILDER_RANGE + 2)
    ]


def builder_power_probe_positions(origin):
    """Return every block whose power can reach an authored builder pad."""
    origin = tuple(int(value) for value in origin)
    return [origin] + [
        tuple(origin[index] + delta[index] for index in range(3))
        for delta in (
            (-1, 0, 0),
            (1, 0, 0),
            (0, -1, 0),
            (0, 1, 0),
            (0, 0, -1),
            (0, 0, 1),
        )
    ]


def builder_facing_from_rotation(pitch, yaw):
    """Return the source builder direction from the nearest player's look.

    CarminiteBuilderBlockEntity prioritizes steep pitch and otherwise uses the
    player's horizontal direction. ModSDK reports pitch/yaw in degrees with
    yaw zero pointing south, matching the mapping below.
    """
    pitch = float(pitch)
    yaw = float(yaw)
    if pitch <= -45.0:
        return (0, 1, 0)
    if pitch >= 45.0:
        return (0, -1, 0)
    quadrant = int(math.floor(yaw / 90.0 + 0.5)) % 4
    return (
        (0, 0, 1),
        (-1, 0, 0),
        (0, 0, -1),
        (1, 0, 0),
    )[quadrant]


def antibuilder_snapshot_positions(origin):
    origin = tuple(int(value) for value in origin)
    return [
        (origin[0] + dx, origin[1] + dy, origin[2] + dz)
        for dx in range(-ANTIBUILDER_RADIUS, ANTIBUILDER_RADIUS + 1)
        for dy in range(-ANTIBUILDER_RADIUS, ANTIBUILDER_RADIUS + 1)
        for dz in range(-ANTIBUILDER_RADIUS, ANTIBUILDER_RADIUS + 1)
    ]


def antibuilder_scan(snapshot, current, roll_for=None):
    """Return one source-equivalent scan result.

    The locked source skips a mismatch when either side belongs to its
    ``antibuilder_ignores`` tag and restores ordinary mismatches with a 1/10
    chance.  A revertable mismatch is reported even when that random roll
    misses so the block entity switches from its 20-tick slow scan to a scan
    every tick.  Ignored changes become the new snapshot, matching upstream.
    """
    roll_for = roll_for or (lambda _position: random.randrange(10))
    changes = []
    snapshot_updates = {}
    has_revertable_differences = False
    for position in sorted(snapshot):
        expected = str(snapshot[position])
        actual = str(current.get(position, "minecraft:air"))
        if expected == actual:
            continue
        if (
            expected in ANTIBUILDER_IGNORED_BLOCKS
            or actual in ANTIBUILDER_IGNORED_BLOCKS
        ):
            snapshot_updates[position] = actual
            continue
        has_revertable_differences = True
        if int(roll_for(position)) != 0:
            continue
        changes.append({"position": position, "block": expected})
    return {
        "changes": changes,
        "snapshotUpdates": snapshot_updates,
        "hasRevertableDifferences": has_revertable_differences,
    }


def antibuilder_changes(snapshot, current, roll_for=None):
    """Compatibility wrapper returning only writes from one scan."""
    return antibuilder_scan(snapshot, current, roll_for)["changes"]


def _random_reactor_burst_offset():
    return tuple(random.choice((-3, 3)) for _unused in range(3))


def reactor_fake_block_writes(position):
    """Return the source's complete 3x3 fake-gold/diamond shell."""
    position = tuple(int(value) for value in position)
    diamond_offsets = (
        (1, 1, 1),
        (1, 1, -1),
        (-1, 1, 1),
        (-1, 1, -1),
        (0, 1, 0),
        (0, 0, 1),
        (0, 0, -1),
        (1, 0, 0),
        (-1, 0, 0),
        (0, -1, 0),
        (1, -1, 1),
        (1, -1, -1),
        (-1, -1, 1),
        (-1, -1, -1),
    )
    gold_offsets = (
        (0, 1, 1),
        (0, 1, -1),
        (1, 1, 0),
        (-1, 1, 0),
        (1, 0, 1),
        (1, 0, -1),
        (-1, 0, 1),
        (-1, 0, -1),
        (0, -1, 1),
        (0, -1, -1),
        (1, -1, 0),
        (-1, -1, 0),
    )
    writes = []
    for block, offsets in (
        ("tf_slice:fake_diamond", diamond_offsets),
        ("tf_slice:fake_gold", gold_offsets),
    ):
        for offset in offsets:
            writes.append({
                "position": tuple(
                    position[index] + offset[index] for index in range(3)
                ),
                "block": block,
            })
    return writes


def reactor_blob_writes(center, radius, fuzz):
    """Trace one fuzzy source blob shell, preserving each write's fuzz value."""
    center = tuple(int(value) for value in center)
    radius = int(radius)
    fuzz = int(fuzz)
    if radius < 0:
        return []
    writes = []
    for dx in range(radius + 1):
        fuzz_x = (fuzz + dx) % 8
        for dy in range(radius + 1):
            fuzz_y = (fuzz + dy) % 8
            for dz in range(radius + 1):
                if dx >= dy and dx >= dz:
                    distance = dx + int(
                        max(dy, dz) * 0.5 + min(dy, dz) * 0.25
                    )
                elif dy >= dx and dy >= dz:
                    distance = dy + int(
                        max(dx, dz) * 0.5 + min(dx, dz) * 0.25
                    )
                else:
                    distance = dz + int(
                        max(dx, dy) * 0.5 + min(dx, dy) * 0.25
                    )
                if distance != radius or (dx == 0 and dy == 0 and dz == 0):
                    continue
                relative = (
                    (dx, dy, dz),
                    (dx, dy, -dz),
                    (-dx, dy, dz),
                    (-dx, dy, -dz),
                    (dx, -dy, dz),
                    (dx, -dy, -dz),
                    (-dx, -dy, dz),
                    (-dx, -dy, -dz),
                )[fuzz_x]
                writes.append({
                    "position": tuple(
                        center[index] + relative[index] for index in range(3)
                    ),
                    "fuzz": fuzz_y,
                })
    return writes


def reactor_blob_positions(center, radius, fuzz):
    return [
        tuple(write["position"])
        for write in reactor_blob_writes(center, radius, fuzz)
    ]


def _reactor_event(kind, center, radius, fuzz):
    return {
        "kind": kind,
        "center": [int(value) for value in center],
        "radius": int(radius),
        "fuzz": int(fuzz),
    }


def create_reactor_state(position, secondary=None, tertiary=None):
    secondary = (
        _random_reactor_burst_offset()
        if secondary is None
        else tuple(int(value) for value in secondary)
    )
    tertiary = (
        _random_reactor_burst_offset()
        if tertiary is None
        else tuple(int(value) for value in tertiary)
    )
    if tuple(secondary) == tuple(tertiary):
        tertiary = tuple(-int(value) for value in tertiary)
    return {
        "position": [int(value) for value in position],
        "counter": 0,
        "active": True,
        "exploded": False,
        "secondary": [int(value) for value in secondary],
        "tertiary": [int(value) for value in tertiary],
    }


def advance_reactor(state, ticks=1):
    events = []
    if not state.get("active") or state.get("exploded"):
        return events
    for _unused in range(max(0, int(ticks))):
        state["counter"] = int(state.get("counter", 0)) + 1
        counter = state["counter"]
        if counter == 5:
            events.append({"kind": "fake_ores", "radius": 1})
        if counter % 5 == 0:
            position = tuple(int(value) for value in state["position"])
            secondary_center = tuple(
                position[index] + int(state["secondary"][index])
                for index in range(3)
            )
            tertiary_center = tuple(
                position[index] + int(state["tertiary"][index])
                for index in range(3)
            )
            primary = counter - 80
            secondary = counter - 120
            tertiary = counter - 160
            if 10 <= primary <= 249:
                events.append(_reactor_event(
                    "primary_clear",
                    position,
                    (primary - 10) // 40,
                    primary - 10,
                ))
            if 0 <= primary <= 200:
                events.append(_reactor_event(
                    "primary_debris", position, primary // 40, counter
                ))
            if 10 <= secondary <= 129:
                events.append(_reactor_event(
                    "secondary_clear",
                    secondary_center,
                    (secondary - 10) // 40,
                    secondary - 10,
                ))
            if 0 <= secondary <= 160:
                events.append(_reactor_event(
                    "secondary_expand",
                    secondary_center,
                    secondary // 40,
                    secondary,
                ))
            if 10 <= tertiary <= 129:
                events.append(_reactor_event(
                    "tertiary_clear",
                    tertiary_center,
                    (tertiary - 10) // 40,
                    tertiary - 10,
                ))
            if 0 <= tertiary <= 160:
                events.append(_reactor_event(
                    "tertiary_expand",
                    tertiary_center,
                    tertiary // 40,
                    tertiary,
                ))
            if counter <= 250:
                events.append({"kind": "ambient", "counter": counter})
        if counter >= REACTOR_TOTAL_TICKS:
            state["active"] = False
            state["exploded"] = True
            events.append(
                {
                    "kind": "explode",
                    "power": 4.0,
                    "miniGhasts": 6,
                }
            )
            break
    return events


def create_experiment_115_state(servings=EXPERIMENT_115_SERVINGS):
    servings = max(0, min(EXPERIMENT_115_SERVINGS, int(servings)))
    return {"servings": servings, "regenerate": False}


def eat_experiment_115(state):
    if int(state.get("servings", 0)) <= 0:
        return False
    state["servings"] = int(state["servings"]) - 1
    return True


def redstone_regenerate_experiment_115(state):
    if int(state.get("servings", 0)) >= EXPERIMENT_115_SERVINGS:
        return False
    state["servings"] = EXPERIMENT_115_SERVINGS
    state["regenerate"] = True
    return True


def consume_life_charm_1(incoming_health, max_health, charm_available):
    fatal = float(incoming_health) <= 0.0
    if not fatal or not charm_available:
        return {
            "health": max(0.0, float(incoming_health)),
            "regenerationTicks": 0,
            "consumed": False,
        }
    return {
        "health": min(float(max_health), float(LIFE_CHARM_HEALTH)),
        "regenerationTicks": LIFE_CHARM_REGENERATION_TICKS,
        "consumed": True,
    }


def unlock_key_door(key_count, remaining_locks):
    """Consume one tower key and release one of a main door's four locks."""
    key_count = int(key_count)
    # Preserve compatibility with old callers that supplied a boolean lock
    # state while allowing the rebuilt tower to model the source four locks.
    lock_count = 1 if remaining_locks is True else max(0, int(remaining_locks))
    if key_count <= 0 or lock_count <= 0:
        return {
            "unlocked": False,
            "remainingKeys": key_count,
            "remainingLocks": lock_count,
            "doorOpened": False,
        }
    lock_count -= 1
    return {
        "unlocked": True,
        "remainingKeys": key_count - 1,
        "remainingLocks": lock_count,
        "doorOpened": lock_count == 0,
    }
