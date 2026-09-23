#!/usr/bin/env python3
"""Build the locked 4.3.2508 Lich and Death Tome visual resources."""

from __future__ import annotations

import argparse
import copy
from io import BytesIO
import json
import math
from pathlib import Path
import re

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = (
    ROOT / "model_acceptance" / "source_snapshots" / "lich_models.json"
)
GEOMETRY_PATH = (
    ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich_entities.geo.json"
)
PROJECTILE_GEOMETRY_PATH = (
    ROOT
    / "TwilightBossSliceR"
    / "models"
    / "entity"
    / "lich_projectiles.geo.json"
)
GEOMETRY_OUTPUT_PATHS = {
    "geometry.tf_slice.lich": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich.geo.json"
    ),
    "geometry.tf_slice.lich_shadow_clone": (
        ROOT
        / "TwilightBossSliceR"
        / "models"
        / "entity"
        / "lich_shadow_clone.geo.json"
    ),
    "geometry.tf_slice.death_tome": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "death_tome.geo.json"
    ),
    "geometry.tf_slice.lich_shields": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich_shields.geo.json"
    ),
    "geometry.tf_slice.lich_bolt": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich_bolt.geo.json"
    ),
    "geometry.tf_slice.lich_bomb": (
        ROOT / "TwilightBossSliceR" / "models" / "entity" / "lich_bomb.geo.json"
    ),
}
LEGACY_ANIMATION_PATH = (
    ROOT
    / "TwilightBossSliceR"
    / "animations"
    / "lich_entities.animation.json"
)
LICH_ANIMATION_PATH = (
    ROOT / "TwilightBossSliceR" / "animations" / "lich.animation.json"
)
ZOMBIE_ANIMATION_PATH = (
    ROOT / "TwilightBossSliceR" / "animations" / "zombie.animation.json"
)
DEATH_TOME_ANIMATION_PATH = (
    ROOT / "TwilightBossSliceR" / "animations" / "death_tome.animation.json"
)
FORTIFICATION_ANIMATION_PATH = (
    ROOT
    / "TwilightBossSliceR"
    / "animations"
    / "fortification_shields.animation.json"
)
LICH_TEXTURE_PATH = (
    ROOT
    / "TwilightBossSliceR"
    / "textures"
    / "entity"
    / "tf_slice"
    / "twilightlich64.png"
)
CLONE_TEXTURE_PATH = LICH_TEXTURE_PATH.with_name("twilightlich64_clone.png")

COMPATIBILITY_ENTITY_GROUPS = {
    Path("TwilightBossSliceR/entity/lich.entity.json"): (
        "animation.tf_slice.lich.move",
        "animation.tf_slice.lich.source_pose",
        "animation.tf_slice.lich.shields",
    ),
    Path("TwilightBossSliceR/entity/lich_shadow_clone.entity.json"): (
        "animation.tf_slice.lich.move",
        "animation.tf_slice.lich.source_pose",
    ),
    Path("TwilightBossSliceR/entity/lich_minion.entity.json"): (
        "animation.tf_slice.zombie.move",
        "animation.tf_slice.zombie.look",
    ),
    Path("TwilightBossSliceR/entity/loyal_zombie.entity.json"): (
        "animation.tf_slice.zombie.move",
        "animation.tf_slice.zombie.look",
    ),
    Path("TwilightBossSliceR/entity/death_tome.entity.json"): (
        "animation.tf_slice.death_tome.fly",
    ),
    Path("TwilightBossSliceR/entity/fortification_shield_visual.entity.json"): (
        "animation.tf_slice.fortification_shields",
    ),
}
ANIMATION_OUTPUT_GROUPS = {
    LICH_ANIMATION_PATH: (
        "animation.tf_slice.lich.move",
        "animation.tf_slice.lich.source_pose",
        "animation.tf_slice.lich.shields",
    ),
    ZOMBIE_ANIMATION_PATH: (
        "animation.tf_slice.zombie.move",
        "animation.tf_slice.zombie.look",
    ),
    DEATH_TOME_ANIMATION_PATH: ("animation.tf_slice.death_tome.fly",),
    FORTIFICATION_ANIMATION_PATH: (
        "animation.tf_slice.fortification_shields",
    ),
}
RETIRED_GENERATED_FILES = (
    LEGACY_ANIMATION_PATH,
    GEOMETRY_PATH,
    PROJECTILE_GEOMETRY_PATH,
)
TRANSFORM_CHANNELS = ("position", "rotation", "scale")
COMPATIBILITY_ANIMATION_PREFIX = "animation.tf_slice.compat."
COMPATIBILITY_ALIAS_PREFIX = "checker_compat_"
COMPATIBILITY_CHANNEL_AMPLITUDES = {
    "position": 4096,
    "rotation": 180,
}


def load_source():
    return json.loads(SOURCE_PATH.read_text(encoding="utf-8"))


def clean_number(value):
    value = round(float(value), 6)
    if abs(value) < 0.0000005:
        return 0
    if abs(value - round(value)) < 0.00001:
        return int(round(value))
    return value


def add_vectors(left, right):
    return [clean_number(left[index] + right[index]) for index in range(3)]


def java_part_pivot(pivot, y_base=24):
    """Convert a Java ModelPart pivot into Bedrock model coordinates."""
    return [
        clean_number(pivot[0]),
        clean_number(y_base - pivot[1]),
        clean_number(pivot[2]),
    ]


def java_part_cube(part_pivot, cube, y_base=24):
    """Convert one Java-local cube after applying its ModelPart translation."""
    local = cube["origin"]
    size = cube["size"]
    result = {
        "origin": [
            clean_number(part_pivot[0] + local[0]),
            clean_number(y_base - (part_pivot[1] + local[1] + size[1])),
            clean_number(part_pivot[2] + local[2]),
        ],
        "size": [clean_number(value) for value in size],
        "uv": list(cube["uv"]),
    }
    for key in ("mirror", "inflate"):
        if key in cube:
            result[key] = cube[key]
    return result


def radians_to_degrees(values):
    return [clean_number(math.degrees(value)) for value in values]


def convert_part(part):
    value = {
        "name": part["name"],
        "parent": part["parent"],
        "pivot": java_part_pivot(part["pivot"]),
    }
    if "rotation_radians" in part:
        value["rotation"] = radians_to_degrees(part["rotation_radians"])
    if part.get("cubes"):
        value["cubes"] = [
            java_part_cube(part["pivot"], cube) for cube in part["cubes"]
        ]
    return value


def geometry_entry(model, root_pivot):
    bounds_width, bounds_height, bounds_offset = model["visible_bounds"]
    width, height = model["texture_size"]
    return {
        "description": {
            "identifier": model["identifier"],
            "texture_width": width,
            "texture_height": height,
            "visible_bounds_width": bounds_width,
            "visible_bounds_height": bounds_height,
            "visible_bounds_offset": bounds_offset,
        },
        "bones": [
            {"name": "root", "pivot": root_pivot},
            *[convert_part(part) for part in model["parts"]],
        ],
    }


def build_geometry(source):
    models = source["models"]
    lich = geometry_entry(models["lich"], [0, 0, 0])
    lich["bones"].extend(
        (
            {
                "name": "rightItem",
                "parent": "rightArm",
                "pivot": source["render_layers"]["held_item"][
                    "right_item_pivot"
                ],
                "neverRender": True,
            },
            {
                "name": "leftItem",
                "parent": "leftArm",
                "pivot": [6, 13, 1],
                "neverRender": True,
            },
        )
    )
    shadow_clone = copy.deepcopy(lich)
    shadow_clone["description"]["identifier"] = (
        "geometry.tf_slice.lich_shadow_clone"
    )
    shadow_clone["bones"] = [
        bone
        for bone in shadow_clone["bones"]
        if bone["name"] not in ("collar", "cloak")
    ]
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            lich,
            shadow_clone,
            geometry_entry(models["death_tome"], [0, 24, 0]),
            lich_shield_geometry(),
        ],
    }


def projectile_sprite_geometry(identifier):
    """Build the half-block plane used with Bedrock's camera billboard."""
    face_uv = {
        "north": {"uv": [0, 0], "uv_size": [16, 16]},
        "south": {"uv": [16, 0], "uv_size": [-16, 16]},
    }
    planes = [
        {
            "name": "sprite_0",
            "parent": "root",
            "pivot": [0, 2, 0],
            "cubes": [
                {
                    "origin": [-4, -2, 0],
                    "size": [8, 8, 0],
                    "uv": copy.deepcopy(face_uv),
                }
            ],
        }
    ]
    return {
        "description": {
            "identifier": identifier,
            "texture_width": 16,
            "texture_height": 16,
            "visible_bounds_width": 0.8,
            "visible_bounds_height": 0.8,
            "visible_bounds_offset": [0, 0.125, 0],
        },
        "bones": [{"name": "root", "pivot": [0, 2, 0]}] + planes,
    }


def build_projectile_geometry():
    return {
        "format_version": "1.12.0",
        "minecraft:geometry": [
            projectile_sprite_geometry("geometry.tf_slice.lich_bolt"),
            projectile_sprite_geometry("geometry.tf_slice.lich_bomb"),
        ],
    }


def split_geometry_payloads(*payloads):
    entries = {}
    format_version = None
    for payload in payloads:
        current_version = payload["format_version"]
        if format_version is None:
            format_version = current_version
        elif current_version != format_version:
            raise ValueError("geometry format versions do not match")
        for geometry in payload["minecraft:geometry"]:
            identifier = geometry["description"]["identifier"]
            if identifier in entries:
                raise ValueError("duplicate geometry identifier: %s" % identifier)
            entries[identifier] = geometry
    missing = set(GEOMETRY_OUTPUT_PATHS) - set(entries)
    unknown = set(entries) - set(GEOMETRY_OUTPUT_PATHS)
    if missing or unknown:
        raise ValueError(
            "geometry output mismatch; missing=%s unknown=%s"
            % (sorted(missing), sorted(unknown))
        )
    return {
        path: {
            "format_version": format_version,
            "minecraft:geometry": [entries[identifier]],
        }
        for identifier, path in GEOMETRY_OUTPUT_PATHS.items()
    }


def lich_shield_geometry():
    """Build the six item-layer planes rendered by locked ShieldLayer."""
    shield_uv = {
        "north": {"uv": [0, 0], "uv_size": [16, 16]},
        "south": {"uv": [16, 0], "uv_size": [-16, 16]},
    }
    bones = [{"name": "root", "pivot": [0, 16, 0]}]
    for index in range(6):
        bones.append(
            {
                "name": "shield_%d" % index,
                "parent": "root",
                "pivot": [0, 16, 0],
                "cubes": [
                    {
                        "origin": [-8, 8, -11.2],
                        "size": [16, 16, 0],
                        "uv": shield_uv,
                    }
                ],
            }
        )
    return {
        "description": {
            "identifier": "geometry.tf_slice.lich_shields",
            "texture_width": 16,
            "texture_height": 16,
            "visible_bounds_width": 3.5,
            "visible_bounds_height": 4.0,
            "visible_bounds_offset": [0, 1.5, 0],
        },
        "bones": bones,
    }


def lich_attack_expressions():
    attack_sine = "math.sin(variable.attack_time * 180)"
    eased_sine = (
        "math.sin((1 - (1 - variable.attack_time) * "
        "(1 - variable.attack_time)) * 180)"
    )
    arm_wave = "math.sin(query.life_time * 191.3679) * 8.5944"
    arm_roll = "math.cos(query.life_time * 297.9389) * 8.5944 + 2.8648"
    attack_pitch = "%s * 68.7549 - %s * 22.9183" % (
        attack_sine,
        eased_sine,
    )
    attack_yaw = "%s * 34.3775" % attack_sine
    return {
        "rightArm": {
            "rotation": [
                "-90 - %s + %s" % (attack_pitch, arm_wave),
                "-5.7296 + %s" % attack_yaw,
                arm_roll,
            ]
        },
        "leftArm": {
            "rotation": [
                "-180 - %s - %s" % (attack_pitch, arm_wave),
                "5.7296 - %s" % attack_yaw,
                "28.6479 - (%s)" % arm_roll,
            ]
        },
    }


def death_tome_animation():
    open_angle = (
        "(math.sin(query.life_time * 458.3662) * 0.3 + 1.25) * 51.5662"
    )
    return {
        "loop": True,
        "bones": {
            "root": {"rotation": [0, 90, 0]},
            "book": {
                "position": [
                    0,
                    "-8 - math.sin(query.life_time * 343.7747) * 2",
                    0,
                ],
                "rotation": [0, 0, -50],
            },
            "paper_storm": {
                "rotation": [0, "query.life_time * 20 + 90", 50]
            },
            "pages_right": {
                "position": ["math.sin((%s) * 0.017453292)" % open_angle, 0, 0],
                "rotation": [0, open_angle, 0],
            },
            "pages_left": {
                "position": ["math.sin((%s) * 0.017453292)" % open_angle, 0, 0],
                "rotation": [0, "-(%s)" % open_angle, 0],
            },
            "cover_right": {"rotation": [0, "180 + (%s)" % open_angle, 0]},
            "cover_left": {"rotation": [0, "-(%s)" % open_angle, 0]},
            "flipping_page_right": {
                "position": ["math.sin((%s) * 0.017453292)" % open_angle, 0, 0],
                "rotation": [
                    0,
                    "(%s) * math.sin(query.life_time * 720 + 90)" % open_angle,
                    0,
                ],
            },
            "flipping_page_left": {
                "position": ["math.sin((%s) * 0.017453292)" % open_angle, 0, 0],
                "rotation": [
                    0,
                    "(%s) * math.sin(query.life_time * 720 + 270)" % open_angle,
                    0,
                ],
            },
            "loose_page_0": {
                "rotation": [
                    "math.sin(query.life_time * 229.1831) * 19.0986",
                    "query.life_time * 286.4789",
                    "math.cos(query.life_time * 229.1831) * 11.4592",
                ]
            },
            "loose_page_1": {
                "rotation": [
                    "math.sin(query.life_time * 229.1831) * 19.0986",
                    "query.life_time * 381.9719",
                    "math.cos(query.life_time * 229.1831) * 14.3239 + 114.5916",
                ]
            },
            "loose_page_2": {
                "rotation": [
                    "-math.sin(query.life_time * 229.1831) * 19.0986",
                    "query.life_time * 286.4789",
                    "math.cos(query.life_time * 229.1831) * 11.4592 - 57.2958",
                ]
            },
            "loose_page_3": {
                "rotation": [
                    "-math.sin(query.life_time * 572.9578) * 14.3239",
                    "query.life_time * 286.4789",
                    "math.cos(query.life_time * 163.7022) * 11.4592",
                ]
            },
        },
    }


def build_source_animations():
    source_pose = lich_attack_expressions()
    source_pose["head"] = {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0]}
    source_pose["hat"] = {"rotation": ["query.target_x_rotation", "query.target_y_rotation", 0]}
    return {
        "format_version": "1.8.0",
        "animations": {
            "animation.tf_slice.lich.move": {
                "loop": True,
                "bones": {
                    "rightLeg": {
                        "rotation": [
                            "math.cos(query.modified_distance_moved * 38.17) * 34.377 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                    "leftLeg": {
                        "rotation": [
                            "math.cos(query.modified_distance_moved * 38.17 + 180) * 34.377 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                },
            },
            "animation.tf_slice.lich.source_pose": {
                "loop": True,
                "bones": source_pose,
            },
            "animation.tf_slice.zombie.move": {
                "loop": True,
                "bones": {
                    "rightArm": {
                        "rotation": [
                            "-80 + math.cos(query.modified_distance_moved * 38.17 + 180) * 14 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                    "leftArm": {
                        "rotation": [
                            "-80 + math.cos(query.modified_distance_moved * 38.17) * 14 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                    "rightLeg": {
                        "rotation": [
                            "math.cos(query.modified_distance_moved * 38.17) * 34.377 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                    "leftLeg": {
                        "rotation": [
                            "math.cos(query.modified_distance_moved * 38.17 + 180) * 34.377 * query.modified_move_speed",
                            0,
                            0,
                        ]
                    },
                },
            },
            "animation.tf_slice.zombie.look": {
                "loop": True,
                "bones": {
                    "head": {
                        "rotation": [
                            "query.target_x_rotation",
                            "query.target_y_rotation",
                            0,
                        ]
                    }
                },
            },
            "animation.tf_slice.death_tome.fly": death_tome_animation(),
            "animation.tf_slice.fortification_shields": (
                fortification_shield_animation()
            ),
            "animation.tf_slice.lich.shields": lich_shield_animation(),
        },
    }


def lich_shield_animation():
    bones = {}
    count = "math.max(query.variant, 1)"
    for index in range(6):
        bones["shield_%d" % index] = {
            "rotation": [
                "math.sin(query.life_time * 229.1831) * 14.3239",
                "query.life_time * 229.1831 + %d * (360 / %s)"
                % (index, count),
                "math.cos(query.life_time * 229.1831) * 14.3239",
            ]
        }
    return {"loop": True, "bones": bones}


def fortification_shield_animation():
    bones = {
        "root": {
            "position": [
                "query.mod.tf_fortification_dx",
                "query.mod.tf_fortification_dy",
                "query.mod.tf_fortification_dz",
            ]
        }
    }
    count = "math.max(query.mod.tf_fortification_shields, 1)"
    clock = "query.mod.tf_fortification_time * 229.1831"
    for index in range(6):
        bones["shield_%d" % index] = {
            "rotation": [
                "math.sin(%s) * 14.3239" % clock,
                "%s + %d * (360 / %s)" % (clock, index, count),
                "math.cos(%s) * 14.3239" % clock,
            ]
        }
    return {"loop": True, "bones": bones}


def compatibility_slug(value):
    value = value.removeprefix("animation.tf_slice.")
    return re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()


def compatibility_alias(helper_id):
    helper_name = helper_id.removeprefix(COMPATIBILITY_ANIMATION_PREFIX)
    return COMPATIBILITY_ALIAS_PREFIX + compatibility_slug(helper_name)


def compatibility_basis(expression, channel_name):
    amplitude = COMPATIBILITY_CHANNEL_AMPLITUDES[channel_name]
    if channel_name == "rotation":
        # Rotation components are equivalent modulo 360 degrees. Keeping the
        # value in [-180, 180) lets both blend weights remain in [0, 1].
        value = "math.mod(math.mod((%s), 360) + 540, 360) - 180" % expression
    else:
        value = "(%s)" % expression
    weight = "math.clamp(((%s) + %d) / %d, 0, 1)" % (
        value,
        amplitude,
        amplitude * 2,
    )
    return (-amplitude, weight, amplitude * 2)


def build_compatible_animations(source):
    """Move Molang out of transform arrays without changing its expression.

    The NetEase cloud packager rejects Molang while converting the animation
    JSON, including scalar ``blend_weight`` values. Each unique expression
    becomes a numeric-only helper animation. The expression is returned with
    the helper id so client entities can apply it through ``scripts.animate``.
    Bedrock adds animation channels component-wise, so activating the base and
    weighted helpers together preserves the original symbolic transform.
    """
    result = {
        "format_version": source["format_version"],
        "animations": {},
    }
    companions = {}
    for animation_id, source_animation in source["animations"].items():
        base_animation = copy.deepcopy(source_animation)
        expression_bones = {}
        for bone_name, source_bone in source_animation.get("bones", {}).items():
            base_bone = base_animation["bones"][bone_name]
            for channel_name in TRANSFORM_CHANNELS:
                source_channel = source_bone.get(channel_name)
                if not isinstance(source_channel, list):
                    continue
                if channel_name == "scale" and any(
                    isinstance(value, str) for value in source_channel
                ):
                    raise ValueError(
                        "dynamic scale needs a dedicated multiplicative conversion"
                    )
                for axis, value in enumerate(source_channel):
                    if not isinstance(value, str):
                        continue
                    base_value, weight, basis_value = compatibility_basis(
                        value, channel_name
                    )
                    base_bone[channel_name][axis] = base_value
                    helper_bones = expression_bones.setdefault(weight, {})
                    helper_bone = helper_bones.setdefault(bone_name, {})
                    helper_channel = helper_bone.setdefault(
                        channel_name, [0] * len(source_channel)
                    )
                    helper_channel[axis] = basis_value

        result["animations"][animation_id] = base_animation
        helper_ids = []
        source_slug = compatibility_slug(animation_id)
        for index, (weight, bones) in enumerate(expression_bones.items(), 1):
            helper_id = "%s%s.%02d" % (
                COMPATIBILITY_ANIMATION_PREFIX,
                source_slug,
                index,
            )
            result["animations"][helper_id] = {
                "loop": True,
                "bones": bones,
            }
            helper_ids.append((helper_id, weight))
        companions[animation_id] = helper_ids
    return result, companions


def build_animations():
    return build_compatible_animations(build_source_animations())[0]


def split_animations(animations, companions):
    outputs = {}
    assigned = set()
    for path, base_ids in ANIMATION_OUTPUT_GROUPS.items():
        definitions = {}
        for animation_id in base_ids:
            definitions[animation_id] = animations["animations"][animation_id]
            assigned.add(animation_id)
            for helper_id, unused_weight in companions[animation_id]:
                definitions[helper_id] = animations["animations"][helper_id]
                assigned.add(helper_id)
        outputs[path] = {
            "format_version": animations["format_version"],
            "animations": definitions,
        }
    missing = set(animations["animations"]) - assigned
    if missing:
        raise ValueError("unassigned animation definitions: %s" % sorted(missing))
    return outputs


def build_compatible_client_entity(path, companions):
    payload = json.loads(path.read_text(encoding="utf-8"))
    description = payload["minecraft:client_entity"]["description"]
    animations = description["animations"]
    animate = description["scripts"]["animate"]

    stale_aliases = {
        alias
        for alias, animation_id in animations.items()
        if alias.startswith(COMPATIBILITY_ALIAS_PREFIX)
        or (
            isinstance(animation_id, str)
            and animation_id.startswith(COMPATIBILITY_ANIMATION_PREFIX)
        )
    }
    for alias in stale_aliases:
        animations.pop(alias, None)
    animate[:] = [
        entry
        for entry in animate
        if (
            entry if isinstance(entry, str)
            else next(iter(entry), None) if isinstance(entry, dict)
            else None
        ) not in stale_aliases
    ]

    for animation_id in COMPATIBILITY_ENTITY_GROUPS[path.relative_to(ROOT)]:
        for helper_id, weight in companions[animation_id]:
            alias = compatibility_alias(helper_id)
            animations[alias] = helper_id
            animate.append({alias: weight})
    return payload


def serialize(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def build_clone_texture(source):
    """Bake the source RGB tint without unstable per-cube alpha blending."""
    multiplier = source["render_layers"]["shadow_clone"]["color_multiplier"]
    with Image.open(LICH_TEXTURE_PATH) as texture:
        clone = texture.convert("RGBA")
    pixels = list(clone.get_flattened_data())
    clone.putdata(
        [
            tuple(
                int(round(channel * multiplier[index]))
                for index, channel in enumerate(pixel[:3])
            )
            + (pixel[3],)
            for pixel in pixels
        ]
    )
    output = BytesIO()
    clone.save(output, format="PNG", compress_level=9, optimize=False)
    return output.getvalue()


def generated_files():
    source = load_source()
    animations, companions = build_compatible_animations(build_source_animations())
    outputs = {
        CLONE_TEXTURE_PATH: build_clone_texture(source),
    }
    geometry_outputs = split_geometry_payloads(
        build_geometry(source), build_projectile_geometry()
    )
    for path, payload in geometry_outputs.items():
        outputs[path] = serialize(payload)
    for path, payload in split_animations(animations, companions).items():
        outputs[path] = serialize(payload)
    for relative_path in COMPATIBILITY_ENTITY_GROUPS:
        path = ROOT / relative_path
        outputs[path] = serialize(build_compatible_client_entity(path, companions))
    return outputs


def write_outputs(outputs):
    for path, content in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        print("WROTE: %s" % path.relative_to(ROOT))
    for path in RETIRED_GENERATED_FILES:
        if path.is_file() and path not in outputs:
            path.unlink()
            print("REMOVED: %s" % path.relative_to(ROOT))


def check_outputs(outputs):
    stale = []
    for path, content in outputs.items():
        actual = None
        if path.is_file():
            if isinstance(content, bytes):
                actual = path.read_bytes()
            else:
                actual = path.read_text(encoding="utf-8")
        if actual != content:
            stale.append(path)
    stale.extend(
        path
        for path in RETIRED_GENERATED_FILES
        if path.is_file() and path not in outputs
    )
    if stale:
        for path in stale:
            print("STALE: %s" % path.relative_to(ROOT))
        return 1
    print("PASS: lich model resources are reproducible")
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail when generated resources differ from the locked source snapshot",
    )
    args = parser.parse_args()
    outputs = generated_files()
    if args.check:
        return check_outputs(outputs)
    write_outputs(outputs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
