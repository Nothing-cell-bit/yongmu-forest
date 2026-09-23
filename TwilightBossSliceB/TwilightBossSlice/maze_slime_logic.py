# -*- coding: utf-8 -*-
"""Pure Maze Slime size and vanilla split-generation rules."""


VALID_SIZES = (1, 2, 4)


def spawn_size(base_roll, upgrade_roll, special_multiplier):
    """Mirror vanilla Slime.finalizeSpawn's power-of-two size choice."""
    exponent = max(0, min(2, int(base_roll)))
    special_multiplier = max(0.0, min(1.0, float(special_multiplier)))
    if (
        exponent < 2
        and float(upgrade_roll) < 0.5 * special_multiplier
    ):
        exponent += 1
    return 1 << exponent


def normalize_size(value):
    value = int(value)
    if value >= 4:
        return 4
    if value >= 2:
        return 2
    return 1


def size_stats(size):
    size = normalize_size(size)
    return {
        "health": 2 * size * size,
        "damage": size,
        "collision": round(0.52 * size, 2),
        "xp": size + 3,
    }


def split_plan(parent_size, random_roll):
    parent_size = normalize_size(parent_size)
    if parent_size <= 1:
        return []
    child_size = parent_size // 2
    child_count = 2 + max(0, min(2, int(random_roll)))
    return [child_size] * child_count
