# -*- coding: utf-8 -*-
"""Pure client-only Ur-Ghast hitbox debug rules."""

from __future__ import division


TOGGLE_KEY_CODE = 80

PHYSICAL_BOX = {
    "name": "physical",
    "offset": (0.0, 9.0, 0.0),
    "scale": (14.0, 18.0, 14.0),
    "color": (1.0, 0.12, 0.12),
    "priority": 10,
}

ATTACK_BOX = {
    "name": "attack",
    "offset": (0.0, 12.5, 0.0),
    "scale": (12.5, 12.5, 12.5),
    "color": (0.12, 1.0, 0.24),
    "priority": 20,
}


def _pressed(value):
    if value is True or value == 1:
        return True
    return str(value).strip().lower() in (
        "1",
        "true",
        "down",
        "pressed",
    )


def key_transition(enabled, key_down, key, is_down):
    """Toggle once for each P-key press edge, ignoring keyboard repeat."""
    try:
        key = int(key)
    except (TypeError, ValueError):
        key = -1
    enabled = bool(enabled)
    key_down = bool(key_down)
    if key != TOGGLE_KEY_CODE:
        return {
            "enabled": enabled,
            "keyDown": key_down,
            "toggled": False,
        }
    pressed = _pressed(is_down)
    toggled = bool(pressed and not key_down)
    if toggled:
        enabled = not enabled
    return {
        "enabled": enabled,
        "keyDown": pressed,
        "toggled": toggled,
    }


def box_descriptors(foot_position):
    """Return Drawing API box centers, scales and colors for one Boss."""
    if foot_position is None or len(foot_position) != 3:
        return ()
    try:
        foot = tuple(float(value) for value in foot_position)
    except (TypeError, ValueError):
        return ()
    result = []
    for source in (PHYSICAL_BOX, ATTACK_BOX):
        offset = source["offset"]
        result.append({
            "name": source["name"],
            "center": tuple(
                foot[index] + float(offset[index])
                for index in range(3)
            ),
            "scale": tuple(float(value) for value in source["scale"]),
            "color": tuple(float(value) for value in source["color"]),
            "priority": int(source["priority"]),
        })
    return tuple(result)
