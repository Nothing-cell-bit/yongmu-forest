#!/usr/bin/env python3
"""Render the Hydra body, active heads, and five source neck parts together."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

import render_entity_geo_preview as preview


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT = ROOT / "TwilightBossSliceB" / "TwilightBossSlice"
sys.path.insert(0, str(PACKAGE_ROOT))

import hydra_logic


def translated_bones(source_bones, prefix, offset, entity_rotation=None):
    root = next(
        (bone for bone in source_bones if bone["name"] == "root"),
        {},
    )
    root_rotation = root.get("rotation", [0.0, 0.0, 0.0])
    result = []
    for source in source_bones:
        if source["name"] == "root":
            continue
        converted = copy.deepcopy(source)
        converted["name"] = prefix + source["name"]
        parent = source.get("parent", "root")
        converted["parent"] = "root" if parent == "root" else prefix + parent
        converted["pivot"] = [
            float(source["pivot"][axis]) + float(offset[axis])
            for axis in range(3)
        ]
        for cube in converted.get("cubes", ()):
            cube["origin"] = [
                float(cube["origin"][axis]) + float(offset[axis])
                for axis in range(3)
            ]
        if parent == "root":
            source_rotation = converted.get("rotation", [0.0, 0.0, 0.0])
            actor_rotation = entity_rotation or (0.0, 0.0, 0.0)
            converted["rotation"] = [
                float(source_rotation[axis])
                + float(root_rotation[axis])
                + float(actor_rotation[axis])
                for axis in range(3)
            ]
        result.append(converted)
    return result


def build_composite_bones(
    document, active_heads=(0, 1, 2), head_rotations=None
):
    head_rotations = head_rotations or {}
    geometries = {
        entry["description"]["identifier"]: entry
        for entry in document["minecraft:geometry"]
    }
    body = copy.deepcopy(geometries["geometry.tf_slice.hydra"]["bones"])
    head = geometries["geometry.tf_slice.hydra_head"]["bones"]
    neck = geometries["geometry.tf_slice.hydra_neck"]["bones"]
    composite = body
    for head_index in active_heads:
        pitch, yaw = head_rotations.get(head_index, (0.0, 0.0))
        head_offset = tuple(
            value * 16.0 for value in hydra_logic.rest_head_offset(head_index)
        )
        composite.extend(
            translated_bones(
                head,
                "head%d_" % head_index,
                head_offset,
                (pitch, yaw, 0.0),
            )
        )
        transforms = hydra_logic.neck_segment_transforms(
            hydra_logic.neck_root_offset(head_index),
            hydra_logic.rest_head_offset(head_index),
            0.0,
            yaw,
            pitch,
        )
        for segment_index, (segment, rotation) in enumerate(
            transforms
        ):
            neck_offset = tuple(value * 16.0 for value in segment)
            composite.extend(
                translated_bones(
                    neck,
                    "head%d_neck%d_" % (head_index, segment_index),
                    neck_offset,
                    (rotation[0], rotation[1], 0.0),
                )
            )
    return composite


def render_contact_sheet(path, document, texture):
    image = Image.new("RGB", (1500, 920), (15, 17, 21))
    draw = ImageDraw.Draw(image, "RGBA")
    try:
        draw.font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        pass
    bones = build_composite_bones(document)
    rest = preview.source_rest_pose(bones)
    walk = dict(rest)
    walk.update(
        {
            "leg_1": [40, 0, 0],
            "leg_2": [-40, 0, 0],
            "tail_1": [0, 8, 0],
            "tail_2": [0, -10, 0],
            "tail_3": [0, 12, 0],
            "tail_4": [0, -14, 0],
        }
    )
    look_bones = build_composite_bones(
        document,
        head_rotations=dict((index, (-30.0, 0.0)) for index in range(3)),
    )
    panels = (
        ((10, 10, 500, 450), "Rest - left side", bones, rest, 90, -8),
        ((505, 10, 995, 450), "Rest - front", bones, rest, 0, -8),
        ((1000, 10, 1490, 450), "Rest - 3/4", bones, rest, 35, -15),
        ((10, 460, 745, 910), "Walk extreme", bones, walk, 55, -12),
        (
            (755, 460, 1490, 910),
            "Head look extreme",
            look_bones,
            preview.source_rest_pose(look_bones),
            35,
            -15,
        ),
    )
    for panel, title, panel_bones, pose, yaw, pitch in panels:
        preview.render_view(
            draw, panel, title, panel_bones, pose, yaw, pitch, texture
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--texture", required=True, type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()

    document = json.loads(args.geometry.read_text(encoding="utf-8"))
    with Image.open(args.texture) as source_texture:
        texture = source_texture.convert("RGBA")
    render_contact_sheet(args.output, document, texture)
    print(args.output)

    if args.evidence_dir:
        bones = build_composite_bones(document)
        rest = preview.source_rest_pose(bones)
        walk = dict(rest)
        walk.update({"leg_1": [40, 0, 0], "leg_2": [-40, 0, 0]})
        views = {
            "front": (0, -8),
            "back": (180, -8),
            "left": (90, -8),
            "right": (-90, -8),
            "top": (0, 90),
            "three_quarter": (35, -15),
        }
        pose_specs = {
            "rest": (bones, rest),
            "walk_extreme": (bones, walk),
        }
        for name, pitch in (("look_up", -30.0), ("look_down", 30.0)):
            pose_bones = build_composite_bones(
                document,
                head_rotations=dict(
                    (index, (pitch, 0.0)) for index in range(3)
                ),
            )
            pose_specs[name] = (
                pose_bones,
                preview.source_rest_pose(pose_bones),
            )
        for name, (yaw, pitch) in views.items():
            preview.render_single(
                args.evidence_dir / "views" / (name + ".png"),
                "Hydra - " + name,
                bones,
                rest,
                yaw,
                pitch,
                texture,
            )
        for name, (pose_bones, pose) in pose_specs.items():
            preview.render_single(
                args.evidence_dir / "poses" / (name + ".png"),
                "Hydra - " + name,
                pose_bones,
                pose,
                35,
                -15,
                texture,
            )
        print(args.evidence_dir)


if __name__ == "__main__":
    main()
