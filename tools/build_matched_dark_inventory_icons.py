#!/usr/bin/env python3
"""Recolor correct mangrove icons while preserving their exact geometry."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image

try:
    import build_locked_wood_inventory_icons as inventory_builder
    import build_public_block_shapes as public_blocks
except ImportError:  # pragma: no cover - package imports in tests
    from tools import build_locked_wood_inventory_icons as inventory_builder
    from tools import build_public_block_shapes as public_blocks


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = (
    ROOT / "tools" / "references" / "matched_dark_inventory_icons_20260901"
)


def _channel_stats(path):
    pixels = list(Image.open(path).convert("RGB").get_flattened_data())
    means = [sum(pixel[index] for pixel in pixels) / float(len(pixels)) for index in range(3)]
    deviations = []
    for index, mean in enumerate(means):
        variance = sum(
            (pixel[index] - mean) ** 2 for pixel in pixels
        ) / float(len(pixels))
        deviations.append(max(1.0, math.sqrt(variance)))
    return means, deviations


def _source_for_suffix(suffix):
    return (
        public_blocks.native_creative_inventory_icon_source(
            "mangrove", suffix
        )
        or public_blocks.twilight_item_icon_source("mangrove", suffix)
    )


def recolor_icon(source, target, light_stats, dark_stats):
    image = Image.open(source).convert("RGBA")
    light_means, light_deviations = light_stats
    dark_means, dark_deviations = dark_stats
    output = []
    for red, green, blue, alpha in image.get_flattened_data():
        channels = (red, green, blue)
        if not alpha or max(channels) < 55:
            output.append((red, green, blue, alpha))
            continue
        converted = []
        for index, value in enumerate(channels):
            normalized = (value - light_means[index]) / light_deviations[index]
            mapped = dark_means[index] + normalized * dark_deviations[index]
            converted.append(max(0, min(255, int(round(mapped)))))
        output.append(tuple(converted) + (alpha,))
    image.putdata(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    image.save(target, format="PNG", optimize=False)


def build(root=ROOT):
    root = Path(root)
    blocks = root / "TwilightBossSliceR" / "textures" / "blocks"
    light_stats = _channel_stats(blocks / "mangrove_planks.png")
    dark_stats = _channel_stats(blocks / "dark_planks.png")
    installed = []
    for suffix in inventory_builder.INVENTORY_ICON_SUFFIXES:
        recolor_icon(
            _source_for_suffix(suffix),
            OUTPUT / (suffix + ".png"),
            light_stats,
            dark_stats,
        )
        installed.append(suffix)
    return tuple(installed)


if __name__ == "__main__":
    result = build()
    print("built %d geometry-matched dark inventory icons" % len(result))
