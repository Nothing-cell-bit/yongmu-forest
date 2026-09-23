# -*- coding: utf-8 -*-
"""Pure state transitions shared by Quest Ram runtime code and tests."""

import math


WOOL_COLORS = (
    "white",
    "orange",
    "magenta",
    "light_blue",
    "yellow",
    "lime",
    "pink",
    "gray",
    "light_gray",
    "cyan",
    "purple",
    "blue",
    "brown",
    "green",
    "red",
    "black",
)
COLOR_BITS = dict(
    (color, 1 << index) for index, color in enumerate(WOOL_COLORS)
)
WOOL_ITEMS = dict(
    ("minecraft:%s_wool" % color, color) for color in WOOL_COLORS
)
COMPLETE_MASK = (1 << len(WOOL_COLORS)) - 1

REWARD_ITEMS = (
    "tf_slice:crumble_horn",
    "tf_slice:quest_ram_trophy_item",
    "minecraft:coal_block",
    "minecraft:iron_block",
    "minecraft:copper_block",
    "minecraft:lapis_block",
    "minecraft:gold_block",
    "minecraft:diamond_block",
    "minecraft:emerald_block",
)

CRUMBLE_RECIPES = {
    "minecraft:stone": "minecraft:cobblestone",
    "minecraft:cobblestone": "minecraft:gravel",
    "minecraft:gravel": "minecraft:air",
    "minecraft:sandstone": "minecraft:sand",
    "minecraft:red_sandstone": "minecraft:red_sand",
    "minecraft:grass": "minecraft:dirt",
    "minecraft:grass_block": "minecraft:dirt",
    "minecraft:podzol": "minecraft:dirt",
    "minecraft:mycelium": "minecraft:dirt",
    "minecraft:coarse_dirt": "minecraft:dirt",
    "minecraft:stone_bricks": "minecraft:cracked_stone_bricks",
    "minecraft:polished_blackstone_bricks":
        "minecraft:cracked_polished_blackstone_bricks",
    "minecraft:deepslate_bricks": "minecraft:cracked_deepslate_bricks",
    "minecraft:deepslate_tiles": "minecraft:cracked_deepslate_tiles",
    "tf_slice:etched_nagastone": "tf_slice:cracked_etched_nagastone",
    "tf_slice:nagastone_pillar": "tf_slice:cracked_nagastone_pillar",
    "tf_slice:towerwood": "tf_slice:cracked_towerwood",
    "tf_slice:cracked_towerwood": "minecraft:air",
    "tf_slice:mossy_towerwood": "tf_slice:cracked_towerwood",
    "tf_slice:underbrick": "tf_slice:cracked_underbrick",
    "tf_slice:mossy_underbrick": "tf_slice:cracked_underbrick",
    "tf_slice:cracked_underbrick": "minecraft:air",
}


def can_consume_wool(distance_sq, settled, visible):
    """QuestRamEatWoolGoal consumes only visible wool within 2.5 blocks."""
    return bool(settled) and bool(visible) and float(distance_sq) < 6.25


def ray_samples(start, end, step=0.25):
    """Yield block coordinates sampled between two eye-level positions."""
    start = tuple(float(value) for value in start)
    end = tuple(float(value) for value in end)
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    dz = end[2] - start[2]
    length = (dx * dx + dy * dy + dz * dz) ** 0.5
    count = max(1, int(length / max(0.05, float(step))))
    for index in range(1, count):
        ratio = float(index) / float(count)
        yield (
            int(math.floor(start[0] + dx * ratio)),
            int(math.floor(start[1] + dy * ratio)),
            int(math.floor(start[2] + dz * ratio)),
        )


def feed_wool(mask, rewarded, color):
    """Return a new immutable Quest Ram state for one wool offering."""
    mask = int(mask or 0) & COMPLETE_MASK
    color = str(color)
    bit = COLOR_BITS.get(color)
    if bit is None or mask & bit:
        return {
            "mask": mask,
            "accepted": False,
            "complete": mask == COMPLETE_MASK,
            "reward_due": False,
            "rewarded": bool(rewarded),
        }
    mask |= bit
    complete = mask == COMPLETE_MASK
    reward_due = complete and not bool(rewarded)
    return {
        "mask": mask,
        "accepted": True,
        "complete": complete,
        "reward_due": reward_due,
        "rewarded": bool(rewarded) or reward_due,
    }
