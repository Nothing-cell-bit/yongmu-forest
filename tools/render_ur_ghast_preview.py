#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render source-evaluated Ur-Ghast evidence with Bedrock runtime roll."""

from __future__ import print_function

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import render_entity_geo_preview as base


# The MCMod reference is a high, three-quarter perspective render.  Keeping
# this camera explicit prevents the orthographic acceptance sheet from making
# the official 16px head look too small beside fully unforeshortened limbs.
REFERENCE_CAMERA = (45.0, -35.0)
REFERENCE_PERSPECTIVE_DISTANCE = 64.0
REFERENCE_AGE_TICKS = 80.0
REFERENCE_TEXTURE_SAMPLES = 16


def apply_ur_ghast_rotation(point, rotation, pivot):
    """Match the entity-bone X/Z direction observed in the Bedrock client."""
    result = base.rotate_z(point, -rotation[2], pivot)
    result = base.rotate_y(result, rotation[1], pivot)
    return base.rotate_x(result, -rotation[0], pivot)


def source_pose(age_ticks):
    """Evaluate locked NewUrGhastModel.setupAnim formulas at one age."""
    pose = {}
    for index in range(9):
        phase = (float(age_ticks) + index * 9.0) / 2.0
        name = "tentacle_%d" % index
        pose[name] = [
            0,
            math.degrees(0.4 * math.sin(phase * 0.3)),
            0,
        ]
        pose[name + "_extension"] = [
            math.degrees(0.1 + math.cos(phase * 0.3335) * 0.15),
            0,
            0,
        ]
        pose[name + "_tip"] = [
            math.degrees(0.1 + math.cos(phase * 0.4445) * 0.2),
            0,
            0,
        ]
    return pose


def source_rest_pose(_bones):
    return source_pose(0.0)


def walk_extreme_pose(_bones):
    # ((age / 2) * 0.3) == pi / 2 gives tentacle zero its exact +0.4 yaw.
    return source_pose(math.pi / 0.3)


def source_look_pose(_bones, pitch, yaw):
    return {"body": [pitch, yaw, 0]}


def scale_reference_layer():
    """Two-block player proxy normalized against the 12.5 client scale."""
    bones = [
        {"name": "root", "pivot": [0, 0, 0]},
        {
            "name": "player_scale_reference",
            "parent": "root",
            "pivot": [-20, 0, 0],
            "cubes": [
                {
                    "origin": [-20.64, 0, -0.64],
                    "size": [1.28, 2.56, 1.28],
                    "uv": [0, 0],
                }
            ],
        },
    ]
    texture = Image.new("RGBA", (16, 16), (72, 199, 255, 255))
    return (bones, {}, texture)


def render_single(
    path,
    title,
    bones,
    pose,
    yaw,
    pitch,
    texture,
    reference=None,
    perspective_distance=None,
):
    image = Image.new("RGB", (640, 640), (15, 17, 21))
    draw = ImageDraw.Draw(image, "RGBA")
    overlays = [reference] if reference is not None else []
    base.render_view(
        draw,
        (10, 10, 630, 630),
        title,
        bones,
        pose,
        yaw,
        pitch,
        texture,
        overlays,
        perspective_distance=perspective_distance,
        max_texture_samples=REFERENCE_TEXTURE_SAMPLES,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--texture", required=True, type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument(
        "--identifier", default="geometry.tf_slice.ur_ghast"
    )
    args = parser.parse_args()

    geometries = json.loads(args.geometry.read_text(encoding="utf-8"))[
        "minecraft:geometry"
    ]
    geometry = next(
        value
        for value in geometries
        if value["description"]["identifier"] == args.identifier
    )
    bones = geometry["bones"]
    with Image.open(args.texture) as source_texture:
        texture = source_texture.convert("RGBA")

    # Keep this entity-specific. Other model evidence retains the established
    # generic preview convention and therefore does not suffer hash drift.
    base.apply_rotation = apply_ur_ghast_rotation

    image = Image.new("RGB", (1500, 920), (15, 17, 21))
    draw = ImageDraw.Draw(image, "RGBA")
    try:
        draw.font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        pass

    rest = source_rest_pose(bones)
    extreme = walk_extreme_pose(bones)
    reference = scale_reference_layer()
    look = dict(rest)
    look.update(source_look_pose(bones, 20, 35))
    panels = (
        ((10, 10, 500, 450), "Rest - left side", rest, 90, -8),
        ((505, 10, 995, 450), "Rest - front | official new/JAPPA", rest, 0, -8),
        ((1000, 10, 1490, 450), "Rest - 3/4 | three-part tentacles", rest, 35, -20),
        ((10, 460, 745, 910), "Motion extreme (locked source)", extreme, 55, -12),
        ((755, 460, 1490, 910), "Look extreme (20/35 deg)", look, 35, -15),
    )
    for panel, title, pose, yaw, pitch in panels:
        base.render_view(
            draw,
            panel,
            title,
            bones,
            pose,
            yaw,
            pitch,
            texture,
            [reference],
            perspective_distance=REFERENCE_PERSPECTIVE_DISTANCE,
            max_texture_samples=REFERENCE_TEXTURE_SAMPLES,
        )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(args.output)

    if args.evidence_dir:
        views = {
            "front": (0, -8),
            "back": (180, -8),
            "left": (90, -8),
            "right": (-90, -8),
            "top": (0, 90),
            "three_quarter": (35, -15),
        }
        poses = {
            "rest": rest,
            "walk_extreme": extreme,
            "look_up": dict(rest, **source_look_pose(bones, -30, 0)),
            "look_down": dict(rest, **source_look_pose(bones, 30, 0)),
        }
        for name, (yaw, pitch) in views.items():
            render_single(
                args.evidence_dir / "views" / (name + ".png"),
                "View - " + name,
                bones,
                rest,
                yaw,
                pitch,
                texture,
                reference,
                REFERENCE_PERSPECTIVE_DISTANCE,
            )
        for name, pose in poses.items():
            render_single(
                args.evidence_dir / "poses" / (name + ".png"),
                "Pose - " + name,
                bones,
                pose,
                35,
                -15,
                texture,
                reference,
                REFERENCE_PERSPECTIVE_DISTANCE,
            )
        render_single(
            args.evidence_dir / "views" / "reference_angle.png",
            "Reference angle - official geometry",
            bones,
            source_pose(REFERENCE_AGE_TICKS),
            REFERENCE_CAMERA[0],
            REFERENCE_CAMERA[1],
            texture,
            perspective_distance=REFERENCE_PERSPECTIVE_DISTANCE,
        )
        print(args.evidence_dir)


if __name__ == "__main__":
    main()
