#!/usr/bin/env python3
"""Render deterministic orthographic previews for a Bedrock entity geometry."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


FACE_INDICES = (
    (0, 1, 3, 2),
    (4, 6, 7, 5),
    (0, 4, 5, 1),
    (2, 3, 7, 6),
    (0, 2, 6, 4),
    (1, 5, 7, 3),
)
MAINHAND_EVIDENCE_CAMERA = (0, -15)


def face_texture_data(cube, face_index):
    """Return texture-space size, atlas origin, and physical corner order."""
    corner_orders = (
        (2, 3, 1, 0),
        (6, 7, 5, 4),
        (0, 1, 5, 4),
        (6, 7, 3, 2),
        (6, 2, 0, 4),
        (3, 7, 5, 1),
    )
    if isinstance(cube["uv"], dict):
        face_names = ("north", "south", "down", "up", "west", "east")
        face = cube["uv"].get(face_names[face_index])
        if face is None:
            return None
        u, v = face["uv"]
        width, height = face["uv_size"]
        atlas_origin = (min(u, u + width), min(v, v + height))
        dimensions = (
            max(1, int(round(abs(float(width))))),
            max(1, int(round(abs(float(height))))),
        )
        corner_indices = corner_orders[face_index]
        if width < 0:
            corner_indices = (
                corner_indices[1],
                corner_indices[0],
                corner_indices[3],
                corner_indices[2],
            )
        if height < 0:
            corner_indices = (
                corner_indices[3],
                corner_indices[2],
                corner_indices[1],
                corner_indices[0],
            )
        return atlas_origin, dimensions, corner_indices

    u, v = cube["uv"]
    # Java models commonly use 0.005-thick planes for pages and covers. Their
    # UV layout is still the zero-depth plane layout, while raster iteration
    # needs at least one sample for every face.
    size_x, size_y, size_z = (
        max(0, int(round(abs(float(value)))))
        for value in cube["size"]
    )
    layouts = (
        ((u + size_z, v + size_z), (size_x, size_y), corner_orders[0]),
        (
            (u + (2 * size_z) + size_x, v + size_z),
            (size_x, size_y),
            corner_orders[1],
        ),
        (
            (u + size_z + size_x, v),
            (size_x, size_z),
            corner_orders[2],
        ),
        ((u + size_z, v), (size_x, size_z), corner_orders[3]),
        ((u, v + size_z), (size_z, size_y), corner_orders[4]),
        (
            (u + size_z + size_x, v + size_z),
            (size_z, size_y),
            corner_orders[5],
        ),
    )
    atlas_origin, dimensions, corner_indices = layouts[face_index]
    dimensions = tuple(max(1, value) for value in dimensions)
    if cube.get("mirror"):
        corner_indices = (
            corner_indices[1],
            corner_indices[0],
            corner_indices[3],
            corner_indices[2],
        )
    return atlas_origin, dimensions, corner_indices


def bilinear_quad(corners, horizontal, vertical):
    top_left, top_right, bottom_right, bottom_left = corners
    top = tuple(
        top_left[axis]
        + (top_right[axis] - top_left[axis]) * horizontal
        for axis in range(3)
    )
    bottom = tuple(
        bottom_left[axis]
        + (bottom_right[axis] - bottom_left[axis]) * horizontal
        for axis in range(3)
    )
    return tuple(
        top[axis] + (bottom[axis] - top[axis]) * vertical
        for axis in range(3)
    )


def rotate_x(point, degrees, pivot):
    angle = math.radians(degrees)
    sine, cosine = math.sin(angle), math.cos(angle)
    x, y, z = point
    px, py, pz = pivot
    y -= py
    z -= pz
    return (
        x,
        py + y * cosine - z * sine,
        pz + y * sine + z * cosine,
    )


def rotate_y(point, degrees, pivot):
    angle = math.radians(degrees)
    sine, cosine = math.sin(angle), math.cos(angle)
    x, y, z = point
    px, py, pz = pivot
    x -= px
    z -= pz
    return (
        px + x * cosine + z * sine,
        y,
        pz - x * sine + z * cosine,
    )


def rotate_z(point, degrees, pivot):
    angle = math.radians(degrees)
    sine, cosine = math.sin(angle), math.cos(angle)
    x, y, z = point
    px, py, pz = pivot
    x -= px
    y -= py
    return (
        px + x * cosine - y * sine,
        py + x * sine + y * cosine,
        z,
    )


def apply_rotation(point, rotation, pivot):
    result = rotate_z(point, rotation[2], pivot)
    result = rotate_y(result, rotation[1], pivot)
    # Bedrock entity bones pitch in the opposite direction from the
    # right-handed helper used above. Mirror X here so the offline preview
    # matches the in-game engine instead of the Java model convention.
    return rotate_x(result, -rotation[0], pivot)


def bone_chain(name, bones_by_name):
    chain = []
    current = bones_by_name[name]
    while current is not None:
        chain.append(current)
        current = bones_by_name.get(current.get("parent"))
    return chain


def attachment_focus_bones(entity_bones, attachment_name):
    """Return an attachment and its parent chain in source bone order."""
    bones_by_name = {bone["name"]: bone for bone in entity_bones}
    if attachment_name not in bones_by_name:
        raise ValueError(
            "attachment preview requires a %s bone" % attachment_name
        )
    included = set()
    current = bones_by_name[attachment_name]
    while current is not None:
        included.add(current["name"])
        current = bones_by_name.get(current.get("parent"))
    return [
        bone for bone in entity_bones if bone["name"] in included
    ]


def transformed_point(point, bone_name, bones_by_name, pose):
    result = point
    for bone in bone_chain(bone_name, bones_by_name):
        base = bone.get("rotation", [0, 0, 0])
        pose_value = pose.get(bone["name"], [0, 0, 0])
        if isinstance(pose_value, dict):
            extra = pose_value.get("rotation", [0, 0, 0])
            position = pose_value.get("position", [0, 0, 0])
        else:
            extra = pose_value
            position = [0, 0, 0]
        rotation = [
            float(base[index]) + float(extra[index])
            for index in range(3)
        ]
        result = apply_rotation(result, rotation, bone["pivot"])
        result = tuple(
            result[index] + float(position[index]) for index in range(3)
        )
    return result


def held_item_bones(entity_bones):
    """Build a texture-only mainhand layer on the engine's rightItem bone."""
    attachment = next(
        (bone for bone in entity_bones if bone["name"] == "rightItem"),
        None,
    )
    if attachment is None:
        raise ValueError("held item preview requires a rightItem bone")
    result = []
    for bone in entity_bones:
        copied = {
            key: value
            for key, value in bone.items()
            if key not in ("cubes", "neverRender")
        }
        if bone["name"] == "rightItem":
            x, y, z = (float(value) for value in bone["pivot"])
            copied["cubes"] = [
                {
                    # Bedrock renders the equipped item in front of the arm.
                    # Keep the thin offline proxy just beyond the arm's front
                    # face so the handle-to-hand contact is inspectable.
                    "origin": [x - 8.0, y - 2.0, z - 3.125],
                    "size": [10.0, 10.0, 0.25],
                    "uv": {
                        "north": {"uv": [16, 0], "uv_size": [-16, 16]},
                        "south": {"uv": [16, 0], "uv_size": [-16, 16]},
                    },
                }
            ]
        result.append(copied)
    return result


def preview_layers(overlay_layers, held_layer, pose):
    layers = []
    for bones, overlay_pose, texture in overlay_layers or []:
        # Renderer-owned layers such as HumanoidArmorLayer copy the entity
        # model's current humanoid pose before drawing.  Compose that shared
        # pose here, while retaining any overlay-specific defaults.
        composed_pose = dict(pose)
        composed_pose.update(overlay_pose or {})
        layers.append((bones, composed_pose, texture))
    if held_layer is not None:
        bones, texture = held_layer
        layers.append((bones, pose, texture))
    return layers


def cube_vertices(cube):
    x, y, z = cube["origin"]
    sx, sy, sz = cube["size"]
    return (
        (x, y, z),
        (x + sx, y, z),
        (x, y + sy, z),
        (x + sx, y + sy, z),
        (x, y, z + sz),
        (x + sx, y, z + sz),
        (x, y + sy, z + sz),
        (x + sx, y + sy, z + sz),
    )


def shade(color, factor):
    return tuple(
        max(0, min(255, round(value * factor)))
        for value in color[:3]
    )


def camera_point(point, yaw, pitch):
    x, y, z = rotate_y(point, yaw, (0, 0, 0))
    return rotate_x((x, y, z), pitch, (0, 0, 0))


def perspective_project(point, distance):
    """Project a camera-space point with a pinhole camera.

    The established acceptance renderer is orthographic by default.  A few
    large entities, notably Ur-Ghast, need an explicitly requested perspective
    pass so a high three-quarter view foreshortens limbs below/behind the body
    in the same way as the in-game camera and the public reference render.
    """
    x, y, z = (float(value) for value in point)
    distance = float(distance)
    if distance <= 0.0:
        raise ValueError("perspective distance must be positive")
    denominator = distance + z
    if denominator <= 0.001:
        raise ValueError("point lies on or behind the perspective camera")
    factor = distance / denominator
    return (x * factor, y * factor, z)


def render_view(
    draw,
    panel,
    title,
    bones,
    pose,
    yaw,
    pitch,
    texture,
    overlay_layers=None,
    perspective_distance=None,
    max_texture_samples=8,
):
    faces = []
    projected_vertices = []
    layers = [(bones, pose, texture)] + list(overlay_layers or [])
    for layer_bones, layer_pose, layer_texture in layers:
        bones_by_name = {bone["name"]: bone for bone in layer_bones}
        for bone in layer_bones:
            for cube in bone.get("cubes", []):
                vertices = [
                    transformed_point(
                        point,
                        bone["name"],
                        bones_by_name,
                        layer_pose,
                    )
                    for point in cube_vertices(cube)
                ]
                viewed = [
                    camera_point(point, yaw, pitch) for point in vertices
                ]
                if perspective_distance is not None:
                    viewed = [
                        perspective_project(point, perspective_distance)
                        for point in viewed
                    ]
                projected_vertices.extend(viewed)
                for face_index, _ in enumerate(FACE_INDICES):
                    texture_data = face_texture_data(
                        cube,
                        face_index,
                    )
                    if texture_data is None:
                        continue
                    atlas_origin, dimensions, indices = texture_data
                    points = [viewed[index] for index in indices]
                    faces.append(
                        (
                            sum(point[2] for point in points) / 4.0,
                            face_index,
                            atlas_origin,
                            dimensions,
                            points,
                            layer_texture,
                        )
                    )

    left, top, right, bottom = panel
    width, height = right - left, bottom - top
    min_x = min(point[0] for point in projected_vertices)
    max_x = max(point[0] for point in projected_vertices)
    min_y = min(point[1] for point in projected_vertices)
    max_y = max(point[1] for point in projected_vertices)
    available_width = width - 36
    available_height = height - 64
    scale = min(
        available_width / max(1.0, max_x - min_x),
        available_height / max(1.0, max_y - min_y),
    )
    center_x = left + width / 2.0
    center_y = top + 34 + available_height / 2.0
    model_center_x = (min_x + max_x) / 2.0
    model_center_y = (min_y + max_y) / 2.0

    draw.rectangle(panel, fill=(24, 27, 32), outline=(74, 80, 89), width=2)
    draw.text((left + 12, top + 10), title, fill=(235, 237, 240))

    for _, face_index, atlas_origin, dimensions, points, face_texture in sorted(
        faces,
        key=lambda value: value[0],
        reverse=True,
    ):
        factor = (0.72, 0.88, 1.04, 0.8, 0.94, 0.68)[face_index]
        atlas_u, atlas_v = atlas_origin
        texture_width, texture_height = dimensions
        # A model face may be dozens of texels wide, while a review panel is
        # only a few hundred pixels.  Cap the raster grid at eight samples per
        # axis: this preserves UV placement and transparency at review scale
        # without spending minutes drawing visually indistinguishable
        # sub-pixel quads for every evidence pose.
        sample_limit = max(1, int(max_texture_samples))
        sample_width = min(texture_width, sample_limit)
        sample_height = min(texture_height, sample_limit)
        for row in range(sample_height):
            top = row / sample_height
            bottom_edge = (row + 1) / sample_height
            texture_row = min(
                texture_height - 1,
                int((row + 0.5) * texture_height / sample_height),
            )
            for column in range(sample_width):
                left_edge = column / sample_width
                right_edge = (column + 1) / sample_width
                texture_column = min(
                    texture_width - 1,
                    int((column + 0.5) * texture_width / sample_width),
                )
                pixel_points = (
                    bilinear_quad(points, left_edge, top),
                    bilinear_quad(points, right_edge, top),
                    bilinear_quad(points, right_edge, bottom_edge),
                    bilinear_quad(points, left_edge, bottom_edge),
                )
                screen_points = [
                    (
                        center_x + (point[0] - model_center_x) * scale,
                        center_y - (point[1] - model_center_y) * scale,
                    )
                    for point in pixel_points
                ]
                color = face_texture.getpixel(
                    (
                        int(atlas_u + texture_column),
                        int(atlas_v + texture_row),
                    )
                )
                alpha = color[3] if len(color) == 4 else 255
                if alpha == 0:
                    continue
                draw.polygon(
                    screen_points,
                    fill=shade(color, factor) + (alpha,),
                )


def source_rest_pose(bones):
    """Return a representative evaluated source pose for known models."""
    names = {bone["name"] for bone in bones}
    death_tome_parts = {
        "pages_right",
        "pages_left",
        "cover_right",
        "cover_left",
        "flipping_page_right",
        "flipping_page_left",
    }
    if death_tome_parts.issubset(names):
        open_angle = 1.25 * 51.5662
        page_shift = math.sin(math.radians(open_angle))
        return {
            "root": {"rotation": [0, 90, 0]},
            "book": {
                "position": [0, -8, 0],
                "rotation": [0, 0, -50],
            },
            "paper_storm": {"rotation": [0, 90, 50]},
            "pages_right": {
                "position": [page_shift, 0, 0],
                "rotation": [0, open_angle, 0],
            },
            "pages_left": {
                "position": [page_shift, 0, 0],
                "rotation": [0, -open_angle, 0],
            },
            "cover_right": {"rotation": [0, 180 + open_angle, 0]},
            "cover_left": {"rotation": [0, -open_angle, 0]},
            "flipping_page_right": {
                "position": [page_shift, 0, 0],
                "rotation": [0, open_angle, 0],
            },
            "flipping_page_left": {
                "position": [page_shift, 0, 0],
                "rotation": [0, -open_angle, 0],
            },
            "loose_page_0": {"rotation": [0, 0, 11.4592]},
            "loose_page_1": {"rotation": [0, 0, 128.9155]},
            "loose_page_2": {"rotation": [0, 0, -45.8366]},
            "loose_page_3": {"rotation": [0, 0, 11.4592]},
        }
    shield_parts = {"shield_%d" % index for index in range(6)}
    if shield_parts.issubset(names):
        return {
            "shield_%d" % index: [0, index * 60, 14.3239]
            for index in range(6)
        }
    if {"collar", "cloak", "rightArm", "leftArm"}.issubset(names):
        return {
            "rightArm": [-90, -5.7296, 11.4592],
            "leftArm": [-180, 5.7296, 17.1887],
        }
    return {}


def walk_extreme_pose(bones):
    names = {bone["name"] for bone in bones}
    if {"collar", "cloak", "rightArm", "leftArm"}.issubset(names):
        return {
            "rightLeg": [80.2141, 0, 0],
            "leftLeg": [-80.2141, 0, 0],
        }
    if {
        "rightArm",
        "leftArm",
        "cow_body",
        "leg_1",
        "leg_2",
        "leg_3",
        "leg_4",
    }.issubset(names):
        return {
            "rightArm": [-57.2958, 0, 0],
            "leftArm": [57.2958, 0, 0],
            "leg_1": [80.2141, 0, 0],
            "leg_2": [-80.2141, 0, 0],
            "leg_3": [-80.2141, 0, 0],
            "leg_4": [80.2141, 0, 0],
        }
    if {
        "rightArm",
        "leftArm",
        "rightLeg",
        "leftLeg",
        "hat",
    }.issubset(names):
        return {
            "rightArm": [-57.2958, 0, 0],
            "leftArm": [57.2958, 0, 0],
            "rightLeg": [80.2141, 0, 0],
            "leftLeg": [-80.2141, 0, 0],
        }
    if {"leg_1", "leg_2", "leg_3", "leg_4", "leg_5", "leg_6"}.issubset(
        names
    ):
        return {
            "leg_1": [0, -17.9183, -3.636364],
            "leg_2": [0, 17.9183, 3.636364],
            "leg_3": [0, 29.4183, -7.890909],
            "leg_4": [0, -29.4183, 7.890909],
            "leg_5": [0, -29, -26.554664],
            "leg_6": [0, 29, 26.554664],
        }
    slime_legs = {
        "front_left_leg",
        "front_right_leg",
        "middle_left_leg",
        "middle_right_leg",
        "back_left_leg",
        "back_right_leg",
    }
    if slime_legs.issubset(names):
        return {
            "back_right_leg": [0, -17.9183, -3.636364],
            "back_left_leg": [0, 17.9183, 3.636364],
            "middle_right_leg": [0, 29.4183, -7.890909],
            "middle_left_leg": [0, -29.4183, 7.890909],
            "front_right_leg": [0, -29, -26.554664],
            "front_left_leg": [0, 29, 26.554664],
            "tail1": [8.594367, 0, 0],
            "tail2": [11.459156, 0, 0],
            "slime_center": [14.323945, 0, 0],
        }
    if {"right_leg", "left_leg"}.issubset(names):
        pose = {
            "right_leg": [40.107, 0, 0],
            "left_leg": [-40.107, 0, 0],
        }
        if {"right_arm", "left_arm"}.issubset(names):
            pose["right_arm"] = [0, 0, 90]
            pose["left_arm"] = [0, 0, -90]
        return pose
    return {
        "leg0": [28, 0, 0],
        "leg1": [-28, 0, 0],
        "leg2": [-28, 0, 0],
        "leg3": [28, 0, 0],
    }


def render_single(
    path,
    title,
    bones,
    pose,
    yaw,
    pitch,
    texture,
    overlay_layers=None,
    held_layer=None,
):
    image = Image.new("RGB", (640, 640), (15, 17, 21))
    draw = ImageDraw.Draw(image, "RGBA")
    render_view(
        draw,
        (10, 10, 630, 630),
        title,
        bones,
        pose,
        yaw,
        pitch,
        texture,
        preview_layers(overlay_layers, held_layer, pose),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("geometry", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--texture", required=True, type=Path)
    parser.add_argument("--evidence-dir", type=Path)
    parser.add_argument("--identifier")
    parser.add_argument("--overlay-geometry", type=Path)
    parser.add_argument("--overlay-identifier")
    parser.add_argument("--overlay-texture", type=Path)
    parser.add_argument("--held-item-texture", type=Path)
    args = parser.parse_args()

    geometries = json.loads(args.geometry.read_text(encoding="utf-8"))[
        "minecraft:geometry"
    ]
    if args.identifier:
        geometry = next(
            item
            for item in geometries
            if item["description"]["identifier"] == args.identifier
        )
    else:
        geometry = geometries[0]
    bones = geometry["bones"]
    with Image.open(args.texture) as source_texture:
        texture = source_texture.convert("RGBA")
    overlay_layers = []
    if any(
        value is not None
        for value in (
            args.overlay_geometry,
            args.overlay_identifier,
            args.overlay_texture,
        )
    ):
        if not all(
            value is not None
            for value in (
                args.overlay_geometry,
                args.overlay_identifier,
                args.overlay_texture,
            )
        ):
            parser.error(
                "overlay geometry, identifier and texture must be supplied together"
            )
        overlay_geometries = json.loads(
            args.overlay_geometry.read_text(encoding="utf-8")
        )["minecraft:geometry"]
        overlay_geometry = next(
            item
            for item in overlay_geometries
            if item["description"]["identifier"]
            == args.overlay_identifier
        )
        overlay_bones = overlay_geometry["bones"]
        with Image.open(args.overlay_texture) as source_texture:
            overlay_texture = source_texture.convert("RGBA")
        overlay_layers.append(
            (
                overlay_bones,
                source_rest_pose(overlay_bones),
                overlay_texture,
            )
        )
    held_layer = None
    if args.held_item_texture is not None:
        try:
            item_bones = held_item_bones(bones)
        except ValueError as error:
            parser.error(str(error))
        with Image.open(args.held_item_texture) as source_texture:
            held_texture = source_texture.convert("RGBA")
        held_layer = (item_bones, held_texture)
    image = Image.new("RGB", (1500, 920), (15, 17, 21))
    draw = ImageDraw.Draw(image, "RGBA")
    try:
        draw.font = ImageFont.truetype("arial.ttf", 18)
    except OSError:
        pass

    rest = source_rest_pose(bones)
    walk = dict(rest)
    walk.update(walk_extreme_pose(bones))
    look = dict(rest)
    look["head"] = [20, 35, 0]
    if any(bone["name"] == "hat" for bone in bones):
        look["hat"] = [20, 35, 0]
    panels = (
        ((10, 10, 500, 450), "Rest - left side", rest, 90, -8),
        ((505, 10, 995, 450), "Rest - front", rest, 0, -8),
        ((1000, 10, 1490, 450), "Rest - 3/4", rest, 35, -15),
        (
            (10, 460, 745, 910),
            "Walk extreme (source amplitude)",
            walk,
            55,
            -12,
        ),
        ((755, 460, 1490, 910), "Look extreme (20/35 deg)", look, 35, -15),
    )
    for panel, title, pose, yaw, pitch in panels:
        render_view(
            draw,
            panel,
            title,
            bones,
            pose,
            yaw,
            pitch,
            texture,
            preview_layers(overlay_layers, held_layer, pose),
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
        look_parts = [
            name
            for name in ("head", "hat")
            if any(bone["name"] == name for bone in bones)
        ]
        poses = {
            "rest": rest,
            "walk_extreme": walk,
            "look_up": dict(
                rest,
                **dict((name, [-30, 0, 0]) for name in look_parts),
            ),
            "look_down": dict(
                rest,
                **dict((name, [30, 0, 0]) for name in look_parts),
            ),
        }
        for name, (yaw, pitch) in views.items():
            render_single(
                args.evidence_dir / "views" / ("%s.png" % name),
                "View - %s" % name,
                bones,
                rest,
                yaw,
                pitch,
                texture,
                overlay_layers,
                held_layer,
            )
        for name, pose in poses.items():
            render_single(
                args.evidence_dir / "poses" / ("%s.png" % name),
                "Pose - %s" % name,
                bones,
                pose,
                35,
                -15,
                texture,
                overlay_layers,
                held_layer,
            )
        if held_layer is not None:
            focus_bones = attachment_focus_bones(bones, "rightItem")
            focus_held_layer = (
                held_item_bones(focus_bones),
                held_layer[1],
            )
            attachment_yaw, attachment_pitch = MAINHAND_EVIDENCE_CAMERA
            render_single(
                args.evidence_dir / "attachments" / "mainhand.png",
                "Attachment - mainhand",
                focus_bones,
                rest,
                attachment_yaw,
                attachment_pitch,
                texture,
                None,
                focus_held_layer,
            )
        print(args.evidence_dir)


if __name__ == "__main__":
    main()
