"""Contracts reproduced from the NetEase 3.9 startup content log."""

import json
from pathlib import Path
import tempfile
from unittest import mock

from tools import build_public_block_shapes as shapes
from tools import biome_render_compat as render

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_netease_dimension_uses_documented_legacy_client_render_registry():
    expected = {
        read(p)["minecraft:biome"]["description"]["identifier"]
        for p in (BP / "netease_biomes" / "dm33027004").glob("*.json")
    }
    assert not list((RP / "biomes").glob("dm33027004_*.client_biome.json"))
    legacy = read(RP / "biomes_client.json")["biomes"]
    assert set(legacy) == expected
    for identifier, settings in legacy.items():
        profile = read(ROOT / "resource_art" / "biome_profiles" / (identifier + ".client_biome.json"))
        c = profile["minecraft:client_biome"]["components"]
        assert settings["water_surface_color"] == c["minecraft:water_appearance"]["surface_color"]
        assert settings["fog_identifier"] == c["minecraft:fog_appearance"]["fog_identifier"]
        fog = next(read(p)["minecraft:fog_settings"] for p in (RP / "fogs").glob("*.json") if read(p)["minecraft:fog_settings"]["description"]["identifier"] == settings["fog_identifier"])
        assert settings["fog_color"] == fog["distance"]["air"]["fog_color"]
        assert settings["water_fog_color"] == fog["distance"]["water"]["fog_color"]


def test_head_slot_trophies_obey_engine_single_item_stack_limit():
    for name in shapes.TROPHY_SPECS:
        for document in (shapes.trophy_item_document(name), read(BP / "items" / (name + "_trophy.item.json"))):
            c = document["minecraft:item"]["components"]
            assert c["minecraft:wearable"]["slot"] == "slot.armor.head"
            assert c["minecraft:max_stack_size"] == 1, name


def test_canopy_banister_recipe_uses_registered_native_slab():
    for document in (shapes.canopy_recipe_documents()["banister"], read(BP / "recipes" / "canopy_banister.recipe.json")):
        assert document["minecraft:recipe_shaped"]["key"]["-"]["item"] == "minecraft:cherry_slab"


def test_trophy_catalog_normalization_does_not_recreate_migrated_fence_alias():
    with tempfile.TemporaryDirectory() as directory:
        bp = Path(directory)
        path = bp / "item_catalog" / "crafting_item_catalog.json"
        path.parent.mkdir()
        path.write_text(json.dumps({"minecraft:crafting_items_catalog": {"categories": [{"category_name": "construction", "groups": [{"items": ["tf_slice:canopy_fence", "tf_slice:naga_trophy", "tf_slice:canopy_banister"]}]}]}}), encoding="utf-8")
        with mock.patch.object(shapes, "BP", bp):
            shapes.normalize_trophy_creative_catalog()
        items = read(path)["minecraft:crafting_items_catalog"]["categories"][0]["groups"][0]["items"]
        assert items == ["tf_slice:naga_trophy_item", "tf_slice:canopy_banister"]


def test_legacy_render_writer_preserves_profiles_without_registering_vanilla_biomes():
    import shutil
    import pytest

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        shutil.copytree(ROOT / "resource_art" / "biome_profiles", render.profile_directory(root))
        shutil.copytree(RP / "fogs", root / "TwilightBossSliceR" / "fogs")
        identifier = "dm33027004_roofed_forest_mutated"
        profile = read(render.profile_directory(root) / (identifier + ".client_biome.json"))
        render.write_profile(root, profile)
        render.write_legacy_registry(root)
        assert read(root / "TwilightBossSliceR" / "biomes_client.json") == render.legacy_document(ROOT)
        assert read(render.profile_directory(root) / (identifier + ".client_biome.json")) == profile
        assert not (root / "TwilightBossSliceR" / "biomes").exists()
        with pytest.raises(ValueError):
            render.write_profile(root, {"minecraft:client_biome": {"description": {"identifier": "../forest"}}})
        with pytest.raises(ValueError, match="No dimension render profiles"):
            render.legacy_document(root / "empty")


def test_shape_pass_keeps_only_hidden_canopy_fence_for_saved_structures():
    with tempfile.TemporaryDirectory() as directory:
        bp, rp = Path(directory) / "B", Path(directory) / "R"
        client = {"tf_slice:canopy_fence": {}, "cherry_fence": {"textures": "tf_slice:canopy_planks"}}
        # Bitmap baking is external to the block-registration contract.
        with mock.patch.object(shapes, "BP", bp), mock.patch.object(shapes, "RP", rp), mock.patch.object(shapes, "_ensure_item_icon", return_value="textures/test_icon"):
            shapes.build_shape_blocks(client, {})
        block = read(bp / "netease_blocks" / "canopy_fence.json")["minecraft:block"]
        assert block["description"]["register_to_creative_menu"] is False
        assert block["description"]["identifier"] == "tf_slice:canopy_fence"
        assert "tf_slice:canopy_fence" in client
        assert client["cherry_fence"] == {"textures": "tf_slice:canopy_planks"}
