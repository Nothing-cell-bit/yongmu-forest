# -*- coding: utf-8 -*-
"""Pure Twilight Forest 4.3.2508 small-animal AI helpers."""

import math


SEED_ITEMS = frozenset(
    (
        "minecraft:wheat_seeds",
        "minecraft:pumpkin_seeds",
        "minecraft:melon_seeds",
        "minecraft:beetroot_seeds",
    )
)


def penguin_slow_fall(current_motion, on_ground):
    """Match Bird.aiStep() descent damping from Twilight Forest 4.3.2508."""
    velocity = tuple(float(value) for value in current_motion)
    if bool(on_ground) or velocity[1] >= 0.0:
        return velocity
    return (velocity[0], velocity[1] * 0.6, velocity[2])


def is_tiny_bird_spooked(has_hurt_target, nearby_player_items):
    """Match TinyBird.isSpooked() from Twilight Forest 4.3.2508."""
    if has_hurt_target:
        return True
    for item_name in nearby_player_items:
        return str(item_name) not in SEED_ITEMS
    return False


def should_tiny_bird_take_off(
    spooked,
    in_water,
    landable,
    random_roll,
):
    """Return whether a landed bird should enter its flying state."""
    return bool(
        spooked
        or in_water
        or (int(random_roll) == 0 and not bool(landable))
    )


def should_tiny_bird_land(landable, random_roll):
    """FlyingBird attempts to land on one of every ten AI ticks."""
    return bool(landable) and int(random_roll) == 0


def tiny_bird_target(position, flight_ticks, random_values):
    """Choose the same 13x13x6 target volume as FlyingBird."""
    values = tuple(int(value) for value in random_values)
    if len(values) != 5:
        raise ValueError("five random target values are required")
    x, y, z = (float(value) for value in position)
    vertical_offset = 2 if int(flight_ticks) < 100 else 4
    return (
        x + values[0] - values[1],
        y + values[2] - vertical_offset,
        z + values[3] - values[4],
    )


def tiny_bird_motion(current_motion, position, target):
    """Apply FlyingBird's gravity damping and steering acceleration."""
    velocity_x = float(current_motion[0])
    velocity_y = float(current_motion[1]) * 0.6
    velocity_z = float(current_motion[2])
    delta_x = float(target[0]) + 0.5 - float(position[0])
    delta_y = float(target[1]) + 0.1 - float(position[1])
    delta_z = float(target[2]) + 0.5 - float(position[2])

    def direction(value):
        if value > 0.0:
            return 1.0
        if value < 0.0:
            return -1.0
        return 0.0

    velocity_x += (direction(delta_x) * 0.5 - velocity_x) * 0.1
    velocity_y += (direction(delta_y) * 0.7 - velocity_y) * 0.1
    velocity_z += (direction(delta_z) * 0.5 - velocity_z) * 0.1
    return (velocity_x, velocity_y, velocity_z)


def target_reached(position, target, radius):
    dx = float(position[0]) - float(target[0])
    dy = float(position[1]) - float(target[1])
    dz = float(position[2]) - float(target[2])
    return dx * dx + dy * dy + dz * dz < float(radius) ** 2


def flight_yaw(motion):
    """Return the upstream horizontal flight-facing yaw."""
    return math.degrees(
        math.atan2(float(motion[2]), float(motion[0]))
    ) - 90.0
