#!/usr/bin/env python3
"""Render deterministic orthographic evidence for a compiled Lich Tower."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PIL import Image, ImageDraw


TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_ruin_structures as builder


AIR = {"minecraft:air", "minecraft:cave_air", "minecraft:void_air"}
COLORS = {
    "tf_slice:lich_boss_spawner": (179, 66, 255),
    "minecraft:birch_planks": (218, 194, 133),
    "minecraft:birch_slab": (238, 214, 153),
    "minecraft:birch_stairs": (245, 224, 169),
    "minecraft:glass": (133, 220, 240),
    "minecraft:bookshelf": (141, 91, 51),
    "minecraft:web": (239, 239, 246),
    "minecraft:tnt": (215, 57, 48),
    "minecraft:mob_spawner": (50, 57, 65),
    "minecraft:oak_fence": (151, 109, 62),
    "minecraft:ladder": (177, 132, 76),
    "minecraft:torch": (255, 196, 66),
    "minecraft:chest": (177, 111, 43),
    "minecraft:trapped_chest": (152, 76, 36),
    "minecraft:stone_bricks": (118, 119, 115),
    "minecraft:mossy_stone_bricks": (102, 119, 87),
    "minecraft:cracked_stone_bricks": (103, 104, 101),
    "minecraft:cobblestone": (111, 112, 108),
    "minecraft:mossy_cobblestone": (91, 111, 78),
}


def block_name(block):
    return str(block[0]) if block else "minecraft:air"


def block_color(name):
    if name in COLORS:
        return COLORS[name]
    if "stone" in name or "cobblestone" in name:
        return (112, 113, 110)
    return (168, 151, 119)


def first_solid(structure, positions):
    for position in positions:
        name = block_name(structure.blocks.get(position))
        if name not in AIR:
            return name
    return None


def raster_top(structure):
    width, height, depth = structure.size
    pixels = {}
    for x in range(width):
        for z in range(depth):
            name = first_solid(
                structure,
                ((x, y, z) for y in range(height - 1, -1, -1)),
            )
            if name:
                pixels[(x, z)] = block_color(name)
    return width, depth, pixels


def raster_front(structure):
    width, height, depth = structure.size
    pixels = {}
    for x in range(width):
        for y in range(height):
            name = first_solid(
                structure,
                ((x, y, z) for z in range(depth)),
            )
            if name:
                pixels[(x, height - y - 1)] = block_color(name)
    return width, height, pixels


def raster_center_slice(structure, center_z):
    width, height, depth = structure.size
    sample_z = [
        z for z in (center_z, center_z - 1, center_z + 1)
        if 0 <= z < depth
    ]
    pixels = {}
    for x in range(width):
        for y in range(height):
            name = first_solid(
                structure,
                ((x, y, z) for z in sample_z),
            )
            if name:
                pixels[(x, height - y - 1)] = block_color(name)
    return width, height, pixels


def raster_floor(structure, floor_y):
    width, _height, depth = structure.size
    pixels = {}
    for x in range(width):
        for z in range(depth):
            name = block_name(structure.blocks.get((x, floor_y, z)))
            if name not in AIR:
                pixels[(x, z)] = block_color(name)
    return width, depth, pixels


def draw_panel(canvas, origin, raster, scale, title):
    width, height, pixels = raster
    ox, oy = origin
    draw = ImageDraw.Draw(canvas)
    draw.text((ox, oy), title, fill=(235, 236, 240))
    top = oy + 18
    draw.rectangle(
        (ox - 1, top - 1, ox + width * scale, top + height * scale),
        outline=(83, 86, 94),
        fill=(19, 21, 27),
    )
    for (x, y), color in pixels.items():
        left = ox + x * scale
        upper = top + y * scale
        draw.rectangle(
            (left, upper, left + scale - 1, upper + scale - 1),
            fill=color,
        )


def render(seed, output):
    structure = builder.lich_tower(seed)
    marker = tuple(structure.lich_tower_metadata["bossSpawnerOffset"])
    scale = 4
    panel_gap = 28
    top = raster_top(structure)
    front = raster_front(structure)
    center = raster_center_slice(structure, marker[2])
    boss_floor = raster_floor(structure, marker[1] - 2)
    left_width = max(top[0], boss_floor[0]) * scale
    right_width = max(front[0], center[0]) * scale
    row_height = max(front[1], center[1]) * scale + 18
    canvas = Image.new(
        "RGB",
        (40 + left_width + panel_gap + right_width, 38 + row_height * 2),
        (12, 14, 19),
    )
    draw_panel(canvas, (18, 14), top, scale, "TOP / recursive birch roofs")
    draw_panel(
        canvas,
        (18 + left_width + panel_gap, 14),
        front,
        scale,
        "FRONT / full silhouette",
    )
    second_y = 20 + row_height
    draw_panel(
        canvas,
        (18, second_y),
        boss_floor,
        scale,
        "LICH FLOOR / glass arena",
    )
    draw_panel(
        canvas,
        (18 + left_width + panel_gap, second_y),
        center,
        scale,
        "CENTER CUT / stairs and rooms",
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
    return structure


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=0, choices=range(8))
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "artifacts" / "lich_tower_v00_preview.png",
    )
    args = parser.parse_args(argv)
    structure = render(args.seed, args.output)
    print(
        "rendered %s size=%s towers=%s roofs=%s boss=%s"
        % (
            args.output,
            structure.size,
            structure.lich_tower_metadata["towerCount"],
            structure.lich_tower_metadata["roofCount"],
            structure.lich_tower_metadata["bossSpawnerOffset"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
