# -*- coding: utf-8 -*-
"""Shared hurt-motion recovery for Twilight Forest flying entities."""

from __future__ import absolute_import


HURT_STABILIZED_FLYERS = frozenset(
    (
        "tf_slice:wraith",
        "tf_slice:raven",
        "tf_slice:tiny_bird",
        "tf_slice:death_tome",
        "tf_slice:knight_phantom",
        "tf_slice:mini_ghast",
        "tf_slice:tower_ghast",
        "tf_slice:ur_ghast",
    )
)


def requires_hurt_stabilization(identifier):
    return str(identifier or "") in HURT_STABILIZED_FLYERS


def stabilized_hurt_motion(motion):
    """Preserve horizontal knockback but remove a persistent upward impulse.

    No-gravity flyers do not naturally decay the positive Y component added
    by Bedrock's hurt knockback. Downward flight is preserved so this helper
    does not pull an entity out of an intentional descent.
    """
    if motion is None or len(motion) < 3:
        return (0.0, 0.0, 0.0)
    return (
        float(motion[0]),
        min(0.0, float(motion[1])),
        float(motion[2]),
    )
