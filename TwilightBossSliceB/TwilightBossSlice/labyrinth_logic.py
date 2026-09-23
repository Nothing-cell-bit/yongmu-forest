# -*- coding: utf-8 -*-
"""Deterministic metadata contract for native Labyrinth structure builds."""


SPAWN_POOL = [
    ("minotaur", 20, 2, 3),
    ("cave_spider", 10, 1, 2),
    ("creeper", 10, 1, 2),
    ("maze_slime", 10, 2, 4),
    ("enderman", 1, 1, 2),
    ("fire_beetle", 10, 1, 2),
    ("slime_beetle", 10, 1, 2),
    ("pinch_beetle", 10, 1, 1),
]
REQUIRED_MARKER_KINDS = frozenset(("boss", "chest", "spawn_zone", "map_center"))

UPPER_ROOMS = (
    "entrance",
    "exit",
    "collapse",
    "collapse",
    "fountain",
    "spawner_chest",
    "spawner_chest",
)
LOWER_ROOMS = (
    "entrance",
    "minoshroom",
    "mushroom",
    "mushroom",
    "vault",
    "spawner_chest",
    "spawner_chest",
)


def java_layout_seed(min_x, min_y, min_z):
    return (int(min_x) * 90342903 + int(min_y) * 90342903) ^ int(min_z)


def build_layout(seed):
    seed = int(seed)
    return {
        "schemaVersion": 1,
        "seed": seed,
        "size_xz": [110, 110],
        "levelHeight": 6,
        "levelOffset": 10,
        "connected": True,
        "levels": [
            {
                "index": 0,
                "rooms": list(UPPER_ROOMS),
                "mazeSeed": java_layout_seed(seed * 16, -14, seed * -16),
            },
            {
                "index": 1,
                "rooms": list(LOWER_ROOMS),
                "mazeSeed": java_layout_seed(seed * 16, -24, seed * -16),
            },
        ],
        "markers": [
            {"kind": "map_center", "level": 0, "pos": [55, 3, 55]},
            {"kind": "spawn_zone", "level": 0, "pos": [55, 3, 55]},
            {"kind": "chest", "table": "room", "level": 0},
            {"kind": "boss", "entity": "tf_slice:minoshroom", "level": 1},
            {"kind": "chest", "table": "vault", "level": 1},
        ],
    }

