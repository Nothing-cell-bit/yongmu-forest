# -*- coding: utf-8 -*-
"""Pure recipe lookup for reversible Transformation Powder conversions."""

from __future__ import unicode_literals


# NetEase 3.8 retains the Bedrock ``zombie_pigman`` identifier for the entity
# called ``zombified_piglin`` by the Java 1.20.1 source data.
TRANSFORMATION_PAIRS = {
    "tf_slice:bighorn_sheep": "minecraft:sheep",
    "tf_slice:boar": "minecraft:pig",
    "tf_slice:deer": "minecraft:cow",
    "tf_slice:dwarf_rabbit": "minecraft:rabbit",
    "tf_slice:hedge_spider": "minecraft:spider",
    "tf_slice:hostile_wolf": "minecraft:wolf",
    "tf_slice:maze_slime": "minecraft:slime",
    "tf_slice:minotaur": "minecraft:zombie_pigman",
    "tf_slice:penguin": "minecraft:chicken",
    "tf_slice:raven": "minecraft:bat",
    "tf_slice:skeleton_druid": "minecraft:witch",
    "tf_slice:swarm_spider": "minecraft:cave_spider",
    "tf_slice:tiny_bird": "minecraft:parrot",
    "tf_slice:towerwood_borer": "minecraft:silverfish",
    "tf_slice:wraith": "minecraft:vex",
}

REVERSE_TRANSFORMATIONS = dict(
    (target, source) for source, target in TRANSFORMATION_PAIRS.items()
)
OWNABLE_TRANSFORMATION_SOURCES = frozenset(("minecraft:wolf",))


def target_for_entity(identifier):
    """Return the reversible counterpart for one supported entity type."""
    identifier = str(identifier or "")
    return TRANSFORMATION_PAIRS.get(
        identifier,
        REVERSE_TRANSFORMATIONS.get(identifier),
    )


def owner_allows_transform(identifier, owner_id, player_id):
    """Protect wild or differently owned tameable mobs during conversion."""
    identifier = str(identifier or "")
    if identifier not in OWNABLE_TRANSFORMATION_SOURCES:
        return True
    if owner_id in (None, "", -1, "-1"):
        return False
    return str(owner_id) == str(player_id)
