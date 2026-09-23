# -*- coding: utf-8 -*-
"""Pure Fire Swamp device state machines based on TF 4.3.2508.

The module has no ModSDK imports so source timings stay unit-testable on the
desktop Python runtime and on the Python 2.7 game runtime.
"""


SMOKER_INTERVAL_TICKS = 4
POPPING_TICKS = 80
FLAME_TICKS = 60
FIRE_JET_DAMAGE_INTERVAL_TICKS = 5
FIRE_JET_DAMAGE = 2
FIRE_JET_SECONDS = 15

SMOKER = "tf_slice:smoker"
FIRE_JET = "tf_slice:fire_jet"
ENCASED_SMOKER = "tf_slice:encased_smoker"
ENCASED_FIRE_JET = "tf_slice:encased_fire_jet"
DEVICE_BLOCKS = frozenset(
    (SMOKER, FIRE_JET, ENCASED_SMOKER, ENCASED_FIRE_JET)
)


def new_device(block_name):
    block_name = str(block_name)
    if block_name not in DEVICE_BLOCKS:
        raise ValueError("unknown Fire Swamp device: %s" % block_name)
    return {
        "block": block_name,
        "counter": 0,
        "phase": "idle",
        "active": block_name == SMOKER,
        "powered": False,
    }


def apply_power(device, powered):
    result = dict(device)
    powered = bool(powered)
    result["powered"] = powered
    events = ()
    if result["block"] == ENCASED_SMOKER:
        if bool(result.get("active")) != powered:
            result["active"] = powered
            events = ("smoker_toggle",)
    elif result["block"] == ENCASED_FIRE_JET:
        if result.get("phase") == "idle" and powered:
            result["phase"] = "popping"
            result["counter"] = 0
            events = ("jet_start",)
        elif result.get("phase") == "timeout" and not powered:
            result["phase"] = "idle"
            result["counter"] = 0
    return result, events


def ignite_natural_jet(device, has_lava_fuel):
    result = dict(device)
    if (
        result.get("block") == FIRE_JET
        and result.get("phase") == "idle"
        and bool(has_lava_fuel)
    ):
        result["phase"] = "popping"
        result["counter"] = 0
        return result, "consume_lava"
    return result, None


def tick_device(device):
    result = dict(device)
    block_name = result.get("block")
    counter = int(result.get("counter", 0))
    if block_name in (SMOKER, ENCASED_SMOKER):
        counter += 1
        result["counter"] = counter
        if bool(result.get("active")) and counter % SMOKER_INTERVAL_TICKS == 0:
            return result, ("smoke",)
        return result, ()

    phase = result.get("phase", "idle")
    if phase == "popping":
        counter += 1
        if counter >= POPPING_TICKS:
            result["phase"] = "flame"
            result["counter"] = 0
            return result, ()
        result["counter"] = counter
        if counter % 20 == 0:
            return result, ("pop",)
        return result, ()

    if phase != "flame":
        return result, ()

    counter += 1
    if counter > FLAME_TICKS:
        counter = 0
        result["phase"] = (
            "timeout" if block_name == ENCASED_FIRE_JET else "idle"
        )
    result["counter"] = counter
    events = []
    if counter % 2 == 0:
        events.append("flame")
    if counter == 1:
        events.append("jet_start")
    elif counter % 4 == 0:
        events.append("jet_active")
    if counter % FIRE_JET_DAMAGE_INTERVAL_TICKS == 0:
        events.append("damage")
    return result, tuple(events)


def fire_jet_damage_bounds(position):
    x, y, z = (int(value) for value in position)
    return ((x - 2, y, z - 2), (x + 2, y + 4, z + 2))


def lava_fuel_candidates(position):
    """Return the full 3x3 fuel plane directly below a natural jet."""
    x, y, z = (int(value) for value in position)
    result = [(x, y - 1, z)]
    for offset_x, offset_z in (
        (-1, -1), (0, -1), (1, -1),
        (-1, 0), (1, 0),
        (-1, 1), (0, 1), (1, 1),
    ):
        result.append((x + offset_x, y - 1, z + offset_z))
    return tuple(result)
