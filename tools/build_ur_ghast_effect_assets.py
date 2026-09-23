#!/usr/bin/env python3
"""Build/check source-locked Ur-Ghast and Ghast Trap particle assets."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
def particle(identifier, material, texture, components):
    return {
        "format_version": "1.10.0",
        "particle_effect": {
            "description": {
                "identifier": "tf_slice:" + identifier,
                "basic_render_parameters": {
                    "material": material,
                    "texture": texture,
                },
            },
            "components": components,
        },
    }


def billboard(
    size,
    texture_width=16,
    texture_height=16,
    facing_camera_mode="lookat_xyz",
):
    return {
        "size": size,
        "facing_camera_mode": facing_camera_mode,
        "uv": {
            "texture_width": texture_width,
            "texture_height": texture_height,
            "uv": [0, 0],
            "uv_size": [texture_width, texture_height],
        },
    }


def documents():
    # Ur-Ghast tantrum uses NetEase dimension-local native rain/thunder.  These
    # generated assets are only the boss-local lightning and trap presentation;
    # neither Java's private rain path nor the acid-rain texture is consumed.
    firefly_texture = "textures/particle/firefly"
    return {
        "ur_ghast_tear.json": particle(
            "ur_ghast_tear",
            "particles_alpha",
            "textures/items/fiery_tears",
            {
                "minecraft:emitter_rate_instant": {"num_particles": 1},
                "minecraft:emitter_lifetime_once": {},
                "minecraft:emitter_shape_point": {
                    "direction": [
                        "Math.random(-0.04, 0.04)",
                        -1.0,
                        "Math.random(-0.04, 0.04)",
                    ]
                },
                "minecraft:particle_initial_speed": 2.0,
                "minecraft:particle_lifetime_expression": {
                    "max_lifetime": "Math.random(3.2, 4.0)"
                },
                "minecraft:particle_motion_dynamic": {
                    "linear_acceleration": [0, -3.0, 0],
                    "linear_drag_coefficient": 0.02,
                },
                "minecraft:particle_appearance_billboard": billboard(
                    [0.4, 0.54]
                ),
                "minecraft:particle_appearance_lighting": {},
            },
        ),
        "ur_ghast_lightning.json": particle(
            "ur_ghast_lightning",
            "particles_add",
            firefly_texture,
            {
                "minecraft:emitter_rate_instant": {"num_particles": 32},
                "minecraft:emitter_lifetime_once": {},
                "minecraft:emitter_shape_sphere": {
                    "radius": 2.5,
                    "direction": "outwards",
                },
                "minecraft:particle_initial_speed": "Math.random(1.0, 4.0)",
                "minecraft:particle_lifetime_expression": {
                    "max_lifetime": "Math.random(0.12, 0.3)"
                },
                "minecraft:particle_motion_dynamic": {
                    "linear_acceleration": [0, -0.4, 0],
                    "linear_drag_coefficient": 0.12,
                },
                "minecraft:particle_appearance_billboard": billboard([0.16, 0.16]),
                "minecraft:particle_appearance_tinting": {
                    "color": [0.88, 0.94, 1.0, 0.95]
                },
                "minecraft:particle_appearance_lighting": {},
            },
        ),
        "ghast_trap_mote.json": particle(
            "ghast_trap_mote",
            "particles_add",
            firefly_texture,
            {
                "minecraft:emitter_rate_instant": {"num_particles": 1},
                "minecraft:emitter_lifetime_once": {},
                "minecraft:emitter_shape_point": {
                    "direction": [
                        "Math.random(-0.08, 0.08)",
                        "Math.random(-0.08, 0.08)",
                        "Math.random(-0.08, 0.08)",
                    ]
                },
                "minecraft:particle_initial_speed": 0.08,
                "minecraft:particle_lifetime_expression": {
                    "max_lifetime": "Math.random(0.35, 0.65)"
                },
                "minecraft:particle_motion_dynamic": {
                    "linear_acceleration": [0, -0.03, 0],
                    "linear_drag_coefficient": 0.18,
                },
                "minecraft:particle_appearance_billboard": billboard([0.13, 0.13]),
                "minecraft:particle_appearance_tinting": {
                    "color": [0.62, 0.28, 1.0, 0.9]
                },
                "minecraft:particle_appearance_lighting": {},
            },
        ),
        "ghast_trap_beam.json": particle(
            "ghast_trap_beam",
            "particles_add",
            firefly_texture,
            {
                "minecraft:emitter_rate_instant": {"num_particles": 16},
                "minecraft:emitter_lifetime_once": {},
                "minecraft:emitter_shape_box": {
                    "half_dimensions": [0.3, 10.0, 0.3],
                    "direction": [0, 0, 0],
                },
                "minecraft:particle_initial_speed": 0.0,
                "minecraft:particle_lifetime_expression": {"max_lifetime": 0.28},
                "minecraft:particle_appearance_billboard": billboard([0.15, 0.5]),
                "minecraft:particle_appearance_tinting": {
                    "color": [0.45, 0.16, 0.92, 0.7]
                },
                "minecraft:particle_appearance_lighting": {},
            },
        ),
    }


def encoded(document):
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def check():
    errors = []
    for name, document in documents().items():
        path = RP / "particles" / name
        if not path.is_file() or path.read_text(encoding="utf-8") != encoded(document):
            errors.append("generated particle is missing or changed: " + name)
    return errors


def build():
    particle_dir = RP / "particles"
    particle_dir.mkdir(parents=True, exist_ok=True)
    for name, document in documents().items():
        (particle_dir / name).write_text(encoded(document), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        errors = check()
        for error in errors:
            print("ERROR:", error)
        return 1 if errors else 0
    build()
    print("built 4 Ur-Ghast/Ghast Trap particle assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
