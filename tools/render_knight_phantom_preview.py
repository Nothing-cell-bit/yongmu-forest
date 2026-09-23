#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render Knight Phantom evidence with its renderer-owned armor layer."""

from __future__ import print_function

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import render_entity_geo_preview as base


def source_held_item_bones(entity_bones):
    """Orient the texture proxy like Java's third-person held-item pass."""
    bones = base.held_item_bones(entity_bones)
    attachment = next(bone for bone in bones if bone["name"] == "rightItem")
    cube = attachment["cubes"][0]
    for face_name in ("north", "south"):
        cube["uv"][face_name] = {
            "uv": [16, 16],
            "uv_size": [-16, -16],
        }
    return bones


def visor_face_bones(entity_bones):
    """Keep only the source skeleton head behind the transparent visor."""
    return base.attachment_focus_bones(entity_bones, "skeleton_head")


def source_pose(age_ticks=0.0, arm_amplitude=0.0):
    """Evaluate the locked KnightPhantomModel pose in degrees."""
    leg = math.degrees(0.2 * math.sin(float(age_ticks) * 0.3) + 0.4)
    arm = math.degrees(float(arm_amplitude))
    idle_pitch = math.degrees(math.sin(float(age_ticks) * 0.067) * 0.05)
    idle_roll = math.degrees(math.cos(float(age_ticks) * 0.09) * 0.05 + 0.05)
    return {
        "right_arm": [round(-18.0 - arm * 0.5 + idle_pitch, 4), 0, round(idle_roll, 4)],
        "left_arm": [round(arm - idle_pitch, 4), 0, round(-idle_roll, 4)],
        "right_leg": [leg, 0, 0],
        "left_leg": [leg, 0, 0],
    }


def look_pose(base_pose, pitch, yaw):
    pose = dict(base_pose)
    pose["head"] = [pitch, yaw, 0]
    pose["hat"] = [pitch, yaw, 0]
    return pose


def render_state(
    path,
    title,
    panel,
    skeleton_bones,
    armor_bones,
    pose,
    yaw,
    pitch,
    skeleton_texture,
    armor_texture,
    held_layer,
    charging,
    canvas=None,
):
    if canvas is None:
        canvas = Image.new("RGB", (640, 640), (15, 17, 21))
    draw = ImageDraw.Draw(canvas, "RGBA")
    if charging:
        primary_bones = skeleton_bones
        primary_texture = skeleton_texture
        overlays = [(armor_bones, {}, armor_texture)]
    else:
        primary_bones = visor_face_bones(skeleton_bones)
        primary_texture = skeleton_texture
        overlays = [(armor_bones, {}, armor_texture)]
    base.render_view(
        draw,
        panel,
        title,
        primary_bones,
        pose,
        yaw,
        pitch,
        primary_texture,
        base.preview_layers(overlays, held_layer, pose),
        max_texture_samples=16,
    )
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(path)
    return canvas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--skeleton-texture", required=True, type=Path)
    parser.add_argument("--armor-texture", required=True, type=Path)
    parser.add_argument("--held-item-texture", required=True, type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()

    geometries = json.loads(args.geometry.read_text(encoding="utf-8"))[
        "minecraft:geometry"
    ]
    by_id = {
        item["description"]["identifier"]: item for item in geometries
    }
    skeleton_bones = by_id[
        "geometry.tf_slice.knight_phantom"
    ]["bones"]
    armor_bones = by_id[
        "geometry.tf_slice.knight_phantom_armor"
    ]["bones"]
    with Image.open(args.skeleton_texture) as image:
        skeleton_texture = image.convert("RGBA")
    with Image.open(args.armor_texture) as image:
        armor_texture = image.convert("RGBA")
    with Image.open(args.held_item_texture) as image:
        held_texture = image.convert("RGBA")
    held_layer = (source_held_item_bones(skeleton_bones), held_texture)

    rest = source_pose(0.0, 0.0)
    motion = source_pose(math.pi / 0.6, 1.0)
    look = look_pose(rest, 20, 35)
    panels = (
        ((10, 10, 500, 450), "Visor face rest - left", rest, 90, -8, False),
        ((505, 10, 995, 450), "Visor face rest - front", rest, 0, -8, False),
        ((1000, 10, 1490, 450), "Visor face rest - 3/4", rest, 35, -15, False),
        ((10, 460, 745, 910), "Charging - skeleton revealed", motion, 35, -15, True),
        ((755, 460, 1490, 910), "Look extreme (20/35 deg)", look, 35, -15, False),
    )
    image = Image.new("RGB", (1500, 920), (15, 17, 21))
    draw = ImageDraw.Draw(image, "RGBA")
    try:
        draw.font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        pass
    for panel, title, pose, yaw, pitch, charging in panels:
        render_state(
            None,
            title,
            panel,
            skeleton_bones,
            armor_bones,
            pose,
            yaw,
            pitch,
            skeleton_texture,
            armor_texture,
            held_layer,
            charging,
            image,
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
        for name, (yaw, pitch) in views.items():
            render_state(
                args.evidence_dir / "views" / (name + ".png"),
                "Visor face view - " + name,
                (10, 10, 630, 630),
                skeleton_bones,
                armor_bones,
                rest,
                yaw,
                pitch,
                skeleton_texture,
                armor_texture,
                held_layer,
                False,
            )
        poses = {
            "rest": rest,
            "walk_extreme": motion,
            "look_up": look_pose(rest, -30, 0),
            "look_down": look_pose(rest, 30, 0),
        }
        for name, pose in poses.items():
            render_state(
                args.evidence_dir / "poses" / (name + ".png"),
                "Visor face pose - " + name,
                (10, 10, 630, 630),
                skeleton_bones,
                armor_bones,
                pose,
                35,
                -15,
                skeleton_texture,
                armor_texture,
                held_layer,
                False,
            )
        render_state(
            args.evidence_dir / "states" / "charging.png",
            "Charging state - skeleton revealed",
            (10, 10, 630, 630),
            skeleton_bones,
            armor_bones,
            motion,
            35,
            -15,
            skeleton_texture,
            armor_texture,
            held_layer,
            True,
        )

        focus_bones = base.attachment_focus_bones(skeleton_bones, "rightItem")
        focus_held = (
            source_held_item_bones(focus_bones),
            held_texture,
        )
        base.render_single(
            args.evidence_dir / "attachments" / "mainhand.png",
            "Attachment - mainhand",
            focus_bones,
            rest,
            base.MAINHAND_EVIDENCE_CAMERA[0],
            base.MAINHAND_EVIDENCE_CAMERA[1],
            skeleton_texture,
            None,
            focus_held,
        )
        print(args.evidence_dir)


if __name__ == "__main__":
    main()
