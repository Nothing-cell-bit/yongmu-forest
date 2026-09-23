# -*- coding: utf-8 -*-
"""Runtime parity checks for Transformation Powder entity interaction."""

from __future__ import unicode_literals

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
SCRIPT_ROOT = BP / "TwilightBossSlice"
sys.path.insert(0, str(BP))

from TwilightBossSlice import transformation_logic  # noqa: E402


EXPECTED_PAIRS = {
    "tf_slice:bighorn_sheep": "minecraft:sheep",
    "tf_slice:boar": "minecraft:pig",
    "tf_slice:deer": "minecraft:cow",
    "tf_slice:dwarf_rabbit": "minecraft:rabbit",
    "tf_slice:hedge_spider": "minecraft:spider",
    "tf_slice:hostile_wolf": "minecraft:wolf",
    "tf_slice:maze_slime": "minecraft:slime",
    "tf_slice:minotaur": "minecraft:zombie_pigman",
    "tf_slice:penguin": "minecraft:chicken",
    "tf_slice:raven": "minecraft:bat",
    "tf_slice:skeleton_druid": "minecraft:witch",
    "tf_slice:swarm_spider": "minecraft:cave_spider",
    "tf_slice:tiny_bird": "minecraft:parrot",
    "tf_slice:towerwood_borer": "minecraft:silverfish",
    "tf_slice:wraith": "minecraft:vex",
}


def test_upstream_supported_pairs_are_available_in_both_directions():
    assert transformation_logic.TRANSFORMATION_PAIRS == EXPECTED_PAIRS
    for source, target in EXPECTED_PAIRS.items():
        assert transformation_logic.target_for_entity(source) == target
        assert transformation_logic.target_for_entity(target) == source


def test_unsupported_or_empty_entity_does_not_transform():
    assert transformation_logic.target_for_entity(None) is None
    assert transformation_logic.target_for_entity("") is None
    assert transformation_logic.target_for_entity("minecraft:creeper") is None


def test_reverse_wolf_conversion_requires_the_interacting_owner():
    assert transformation_logic.owner_allows_transform(
        "minecraft:wolf", "player-a", "player-a"
    )
    assert not transformation_logic.owner_allows_transform(
        "minecraft:wolf", "player-a", "player-b"
    )
    assert not transformation_logic.owner_allows_transform(
        "minecraft:wolf", None, "player-a"
    )
    assert transformation_logic.owner_allows_transform(
        "tf_slice:hostile_wolf", None, "player-a"
    )


def test_every_custom_transformation_source_is_registered_in_behavior_pack():
    for source in EXPECTED_PAIRS:
        entity_name = source.split(":", 1)[1]
        assert (BP / "entities" / (entity_name + ".entity.json")).is_file()


def test_server_routes_entity_interaction_through_transactional_transform():
    source = (SCRIPT_ROOT / "serverSystem.py").read_text(encoding="utf-8")
    handler = source[
        source.index("    def OnPlayerDoInteractServerEvent") :
        source.index("    def OnMagicMapCraftingInputChanged")
    ]
    assert "_try_transformation_powder(args)" in handler

    transform = source[
        source.index("    def _try_transformation_powder") :
        source.index("    def OnPlayerDoInteractServerEvent")
    ]
    assert "transformation_logic.target_for_entity" in transform
    assert "transformation_logic.owner_allows_transform" in transform
    assert "IsEntityAlive" in transform
    assert "_consume_one_carried_item" in transform
    assert "CreateEngineEntityByTypeStr" in transform
    assert "DestroyEntity" in transform
    assert "_set_carried_item(playerId, original)" in transform
    assert 'args["cancel"] = True' in transform
