#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render the rejected and corrected Ur-Ghast runtime orientation together."""

from __future__ import print_function

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw

import render_entity_geo_preview as base
import render_ur_ghast_preview as ur_preview


ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = (
    ROOT / "TwilightBossSliceR" / "models" / "entity"
    / "phantom_urghast_route.geo.json"
)
ATTACK_TEXTURE = (
    ROOT / "TwilightBossSliceR" / "textures" / "entity" / "tf_slice"
    / "ur_ghast_attack.png"
)
DEFAULT_OUTPUT = (
    ROOT / "model_acceptance" / "offline" / "comparisons"
    / "ur_ghast_orientation_before_after.png"
)

# Production runtime transforms represented by the two panels.
BEFORE_YAW_OFFSET = 180.0
BEFORE_PITCH_SIGN = 1.0
AFTER_YAW_OFFSET = 0.0
AFTER_PITCH_SIGN = 1.0
VISUAL_PITCH = 60.0
SHARED_CAMERA = (0.0, 35.0)
PLAYER_REFERENCE_HEIGHT_BLOCKS = 2.0
PLAYER_REFERENCE_UNITS_PER_BLOCK = 1.28
PLAYER_REFERENCE_FEET_Y = -10.0


def _ur_ghast_bones():
    document = json.loads(GEOMETRY.read_text(encoding="utf-8"))
    geometries = document["minecraft:geometry"]
    geometry = next(
        value
        for value in geometries
        if value["description"]["identifier"]
        == "geometry.tf_slice.ur_ghast"
    )
    return geometry["bones"]


def _preview_pose(yaw_offset, pitch_sign):
    pose = ur_preview.source_pose(80.0)
    # Latest cold-client motion traces prove that NetEase model yaw and source
    # motion yaw share the same forward axis. Keep the shared camera fixed and
    # apply the rejected/candidate production offset directly.
    face_relative_yaw = float(yaw_offset) % 360.0
    pose["pose_root"] = [
        VISUAL_PITCH * float(pitch_sign),
        face_relative_yaw,
        0.0,
    ]
    return pose


def _player_reference_layer():
    """Return a two-block cyan player proxy in the shared 3-D projection."""
    height = (
        PLAYER_REFERENCE_HEIGHT_BLOCKS * PLAYER_REFERENCE_UNITS_PER_BLOCK
    )
    feet = PLAYER_REFERENCE_FEET_Y
    leg_height = height * 0.36
    torso_height = height * 0.39
    head_height = height * 0.25

    def cube(origin, size):
        return {"origin": list(origin), "size": list(size), "uv": [0, 0]}

    bones = [
        {"name": "player_reference_root", "pivot": [0, 0, 0]},
        {
            "name": "player_reference",
            "parent": "player_reference_root",
            "pivot": [0, feet, 0],
            "cubes": [
                cube((-0.30, feet, -0.14), (0.26, leg_height, 0.28)),
                cube((0.04, feet, -0.14), (0.26, leg_height, 0.28)),
                cube(
                    (-0.42, feet + leg_height, -0.16),
                    (0.84, torso_height, 0.32),
                ),
                cube(
                    (-0.66, feet + leg_height, -0.14),
                    (0.20, torso_height, 0.28),
                ),
                cube(
                    (0.46, feet + leg_height, -0.14),
                    (0.20, torso_height, 0.28),
                ),
                cube(
                    (-0.32, feet + leg_height + torso_height, -0.32),
                    (0.64, head_height, 0.64),
                ),
            ],
        },
    ]
    texture = Image.new("RGBA", (16, 16), (58, 206, 255, 255))
    return (bones, {}, texture)


def render(output):
    bones = _ur_ghast_bones()
    player_reference = _player_reference_layer()
    with Image.open(ATTACK_TEXTURE) as source:
        texture = source.convert("RGBA")

    image = Image.new("RGB", (1400, 760), (13, 15, 19))
    draw = ImageDraw.Draw(image, "RGBA")
    draw.text(
        (20, 20),
        "Ur-Ghast orientation: same model / same camera / target below",
        fill=(242, 244, 248),
    )
    draw.text(
        (20, 48),
        "Cyan = 2-block player below Boss (exact scale; gap schematic).",
        fill=(171, 181, 194),
    )

    base.apply_rotation = ur_preview.apply_ur_ghast_rotation
    panels = (
        (
            (20, 80, 690, 740),
            "BEFORE (rejected): yaw +180 / pitch +60",
            _preview_pose(BEFORE_YAW_OFFSET, BEFORE_PITCH_SIGN),
        ),
        (
            (710, 80, 1380, 740),
            "AFTER (candidate): yaw +0 / pitch +60",
            _preview_pose(AFTER_YAW_OFFSET, AFTER_PITCH_SIGN),
        ),
    )
    for panel, title, pose in panels:
        base.render_view(
            draw,
            panel,
            title,
            bones,
            pose,
            SHARED_CAMERA[0],
            SHARED_CAMERA[1],
            texture,
            overlay_layers=[player_reference],
            perspective_distance=64.0,
            max_texture_samples=16,
        )

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    print(output)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    render(args.output)


if __name__ == "__main__":
    main()
