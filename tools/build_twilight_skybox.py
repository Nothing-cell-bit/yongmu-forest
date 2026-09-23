#!/usr/bin/env python3
"""Build the Twilight Forest 4.3.2508-style deterministic star cubemap.

The upstream renderer builds untextured white quads on a radius-100 sphere.
NetEase SkyRender accepts only six static cubemap faces, so this projects the
same seeded sphere sampling onto those faces and rasterizes the tiny quads.
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

from PIL import Image, ImageDraw


STAR_SEED = 10842
STAR_ATTEMPTS = 3000
STAR_MIN_SIZE = 0.15
STAR_MAX_SIZE = 0.25
SKY_COLOR = (32, 34, 74, 255)
STAR_COLOR = (255, 255, 255, 255)
FACE_SIZE = 512
SUPERSAMPLE = 4
FACE_NAMES = (
    "negative_z",
    "positive_x",
    "positive_z",
    "negative_x",
    "positive_y",
    "negative_y",
)


class JavaRandom(object):
    """java.util.Random-compatible stream used by RandomSource.create(seed)."""

    _MULTIPLIER = 0x5DEECE66D
    _ADDEND = 0xB
    _MASK = (1 << 48) - 1

    def __init__(self, seed):
        self._seed = (int(seed) ^ self._MULTIPLIER) & self._MASK

    def _next(self, bits):
        self._seed = (
            self._seed * self._MULTIPLIER + self._ADDEND
        ) & self._MASK
        return self._seed >> (48 - bits)

    def next_float(self):
        return self._next(24) / float(1 << 24)

    def next_double(self):
        high = self._next(26)
        low = self._next(27)
        return ((high << 27) + low) / float(1 << 53)


def _normalize(vector):
    length = math.sqrt(sum(value * value for value in vector))
    return tuple(value / length for value in vector)


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _face_for(direction):
    x, y, z = direction
    dominant = max(abs(x), abs(y), abs(z))
    if dominant == abs(x):
        return "positive_x" if x >= 0.0 else "negative_x"
    if dominant == abs(y):
        return "positive_y" if y >= 0.0 else "negative_y"
    return "positive_z" if z >= 0.0 else "negative_z"


def _project(face, point):
    x, y, z = point
    if face == "positive_x":
        denominator = x
        u, v = -z / denominator, -y / denominator
    elif face == "negative_x":
        denominator = -x
        u, v = z / denominator, -y / denominator
    elif face == "positive_y":
        denominator = y
        u, v = x / denominator, z / denominator
    elif face == "negative_y":
        denominator = -y
        u, v = x / denominator, -z / denominator
    elif face == "positive_z":
        denominator = z
        u, v = x / denominator, -y / denominator
    else:
        denominator = -z
        u, v = -x / denominator, -y / denominator
    scale = (FACE_SIZE - 1) * 0.5 * SUPERSAMPLE
    return ((u + 1.0) * scale, (v + 1.0) * scale)


def _star_quad(direction, size, angle):
    center = tuple(value * 100.0 for value in direction)
    reference_up = (0.0, 1.0, 0.0)
    right = _cross(reference_up, direction)
    if sum(value * value for value in right) < 1.0e-10:
        right = (1.0, 0.0, 0.0)
    else:
        right = _normalize(right)
    tangent_up = _normalize(_cross(direction, right))
    cosine = math.cos(angle)
    sine = math.sin(angle)
    axis_u = tuple(
        right[index] * cosine + tangent_up[index] * sine
        for index in range(3)
    )
    axis_v = tuple(
        -right[index] * sine + tangent_up[index] * cosine
        for index in range(3)
    )
    corners = ((1.0, -1.0), (1.0, 1.0), (-1.0, 1.0), (-1.0, -1.0))
    return [
        tuple(
            center[index]
            + size * (u_sign * axis_u[index] + v_sign * axis_v[index])
            for index in range(3)
        )
        for u_sign, v_sign in corners
    ]


def build_skybox(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    canvas_size = FACE_SIZE * SUPERSAMPLE
    images = {
        name: Image.new("RGBA", (canvas_size, canvas_size), SKY_COLOR)
        for name in FACE_NAMES
    }
    draws = {name: ImageDraw.Draw(image) for name, image in images.items()}
    face_counts = {name: 0 for name in FACE_NAMES}
    random_source = JavaRandom(STAR_SEED)
    accepted = 0

    for _ in range(STAR_ATTEMPTS):
        sample = tuple(
            random_source.next_float() * 2.0 - 1.0
            for _axis in range(3)
        )
        size = STAR_MIN_SIZE + random_source.next_float() * (
            STAR_MAX_SIZE - STAR_MIN_SIZE
        )
        length_squared = sum(value * value for value in sample)
        if length_squared <= 0.010000001 or length_squared >= 1.0:
            continue
        direction = _normalize(sample)
        angle = random_source.next_double() * math.pi * 2.0
        face = _face_for(direction)
        quad = _star_quad(direction, size, angle)
        draws[face].polygon(
            [_project(face, point) for point in quad],
            fill=STAR_COLOR,
        )
        face_counts[face] += 1
        accepted += 1

    resampling = getattr(Image, "Resampling", Image).LANCZOS
    for name in FACE_NAMES:
        image = images[name].resize(
            (FACE_SIZE, FACE_SIZE),
            resampling,
        )
        image.save(
            output_dir / (name + ".png"),
            format="PNG",
            optimize=True,
        )

    return {
        "accepted_stars": accepted,
        "face_counts": face_counts,
    }


def main():
    default_output = (
        Path(__file__).resolve().parents[1]
        / "TwilightBossSliceR"
        / "textures"
        / "environment"
        / "twilight_sky"
    )
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help="directory receiving the six PNG faces",
    )
    args = parser.parse_args()
    stats = build_skybox(args.output)
    print(
        "built %d accepted stars from %d attempts in %s"
        % (stats["accepted_stars"], STAR_ATTEMPTS, args.output)
    )


if __name__ == "__main__":
    main()
