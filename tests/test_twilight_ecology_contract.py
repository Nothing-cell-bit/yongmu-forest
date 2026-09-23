# -*- coding: utf-8 -*-
import importlib.util
import json
import struct
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from TwilightBossSlice import release_metadata

ROOT_BLOCK_IDS = {
    "tf_slice:root_block",
    "tf_slice:liveroot_block",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class MayappleRenderContractTests(unittest.TestCase):
    def test_mayapple_geometry_binds_materials_on_individual_faces(self):
        block = read_json(
            BP / "netease_blocks" / "mayapple.json"
        )["minecraft:block"]
        materials = block["components"]["minecraft:material_instances"]
        geometry = read_json(
            RP / "models" / "blocks" / "mayapple.geo.json"
        )["minecraft:geometry"][0]

        self.assertIn("*", materials)
        for bone in geometry["bones"]:
            for cube in bone.get("cubes", []):
                self.assertNotIn("material_instance", cube)
                self.assertIsInstance(cube["uv"], dict)
                for face in cube["uv"].values():
                    self.assertIn(face["material_instance"], materials)

    def test_mayapple_material_textures_exist_in_the_terrain_atlas(self):
        materials = read_json(
            BP / "netease_blocks" / "mayapple.json"
        )["minecraft:block"]["components"]["minecraft:material_instances"]
        atlas = read_json(
            RP / "textures" / "terrain_texture.json"
        )["texture_data"]

        for material in materials.values():
            texture_name = material["texture"]
            self.assertIn(texture_name, atlas)
            texture_path = atlas[texture_name]["textures"]
            self.assertTrue((RP / (texture_path + ".png")).is_file())


class HollowTwilightOakContractTests(unittest.TestCase):
    def test_hollow_oak_keeps_the_upstream_one_in_35_rarity(self):
        rule = read_json(
            BP
            / "netease_feature_rules"
            / "hollow_tree_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "tf_slice:hollow_tree_chunk_trigger_structure_feature",
            rule["description"]["places_feature"],
        )
        distribution = rule["distribution"]
        self.assertEqual(0, distribution["x"])
        self.assertEqual(0, distribution["z"])
        self.assertIn("/ 32", distribution["y"])
        self.assertIn("query.is_biome", str(distribution["iterations"]))
        self.assertIn("<= 2", str(distribution["iterations"]))
        trigger = read_json(
            BP
            / "netease_features"
            / "hollow_tree_chunk_trigger_structure_feature.json"
        )["netease:structure_feature"]
        self.assertEqual(
            "tf_slice:hollow_tree_chunk_trigger",
            trigger["places_structure"],
        )
        catalog = read_json(
            BP
            / "structures"
            / "tf_slice"
            / "ruins"
            / "structure_catalog_v1.json"
        )
        entry = next(
            item
            for item in catalog["structures"]
            if item["id"] == "leaf_dungeon"
        )
        self.assertEqual(
            {"numerator": 4, "denominator": 35},
            entry["chunkNative"]["cellChance"],
        )
        self.assertEqual([2, 2], entry["chunkNative"]["cellChunks"])

    def test_hollow_oak_has_eight_large_structure_variants(self):
        catalog = read_json(
            BP
            / "structures"
            / "tf_slice"
            / "ruins"
            / "structure_catalog_v1.json"
        )
        entry = next(
            item
            for item in catalog["structures"]
            if item["id"] == "leaf_dungeon"
        )
        self.assertEqual(8, len(entry["variants"]))
        for variant in entry["variants"]:
            self.assertEqual(1, variant["weight"])
            self.assertNotIn("nativeFeature", variant)
            self.assertEqual(4, len(variant["pieces"]))
            self.assertFalse(
                (
                    BP
                    / "structures"
                    / "tf_slice"
                    / "ruins"
                    / "hollow_tree"
                    / (variant["id"] + "_native.mcstructure")
                ).exists()
            )

    def test_hollow_oak_structures_contain_hollow_trunks_and_broad_crowns(self):
        catalog = read_json(
            BP
            / "structures"
            / "tf_slice"
            / "ruins"
            / "structure_catalog_v1.json"
        )
        entry = next(
            item
            for item in catalog["structures"]
            if item["id"] == "leaf_dungeon"
        )
        self.assertEqual(8, len(entry["variants"]))
        for variant in entry["variants"]:
            bounds = variant["bounds"]
            self.assertGreaterEqual(bounds[3] - bounds[0] + 1, 32)
            self.assertGreaterEqual(bounds[4] - bounds[1] + 1, 36)
            self.assertGreater(len(variant["pieces"]), 1)
            data = b"".join(
                (
                    BP
                    / "structures"
                    / (piece["structure"] + ".mcstructure")
                ).read_bytes()
                for piece in variant["pieces"]
            )
            self.assertIn(b"tf_slice:twilight_oak_log", data)
            self.assertIn(b"tf_slice:twilight_oak_leaves", data)
            self.assertIn(b"minecraft:air", data)
            for piece in variant["pieces"]:
                self.assertLessEqual(piece["size"][0], 16)
                self.assertLessEqual(piece["size"][2], 16)


class WoodRootVeinContractTests(unittest.TestCase):
    def test_root_blocks_are_registered_on_both_sides_and_in_the_atlas(self):
        server_ids = {
            read_json(path)["minecraft:block"]["description"]["identifier"]
            for path in (BP / "netease_blocks").glob("*.json")
        }
        client_ids = set(read_json(RP / "blocks.json"))
        atlas = read_json(
            RP / "textures" / "terrain_texture.json"
        )["texture_data"]

        self.assertTrue(ROOT_BLOCK_IDS.issubset(server_ids))
        self.assertTrue(ROOT_BLOCK_IDS.issubset(client_ids))
        self.assertTrue(ROOT_BLOCK_IDS.issubset(atlas))
        self.assertTrue(
            (RP / "textures" / "blocks" / "root.png").is_file()
        )
        self.assertTrue(
            (RP / "textures" / "blocks" / "liveroot_block.png").is_file()
        )

    def test_root_vein_is_a_root_then_liveroot_replacement_sequence(self):
        root = read_json(
            BP / "netease_features" / "wood_root_ore_feature.json"
        )["minecraft:ore_feature"]
        live = read_json(
            BP / "netease_features" / "liveroot_ore_feature.json"
        )["minecraft:ore_feature"]
        sequence = read_json(
            BP / "netease_features" / "wood_root_vein_feature.json"
        )["minecraft:sequence_feature"]

        self.assertEqual(14, root["count"])
        self.assertEqual(
            "tf_slice:root_block",
            root["replace_rules"][0]["places_block"],
        )
        self.assertEqual(2, live["count"])
        self.assertEqual(
            "tf_slice:liveroot_block",
            live["replace_rules"][0]["places_block"],
        )
        self.assertEqual(
            [{"name": "tf_slice:root_block"}],
            live["replace_rules"][0]["may_replace"],
        )
        self.assertEqual(
            [
                "tf_slice:wood_root_ore_feature",
                "tf_slice:liveroot_ore_feature",
            ],
            sequence["features"],
        )

    def test_root_vein_uses_upstream_depth_and_rarity(self):
        rule = read_json(
            BP
            / "netease_feature_rules"
            / "wood_root_vein_feature_rule.json"
        )["minecraft:feature_rules"]
        distribution = rule["distribution"]

        self.assertEqual("underground_pass", rule["conditions"]["placement_pass"])
        self.assertEqual(1, distribution["iterations"])
        self.assertEqual(2.5, distribution["scatter_chance"])
        self.assertEqual(
            {"distribution": "uniform", "extent": [-32, 0]},
            distribution["y"],
        )
        self.assertIn(
            "tf_slice_has_underground_roots",
            json.dumps(rule["conditions"]),
        )


class AmbientFireflyContractTests(unittest.TestCase):
    def test_firefly_particle_is_small_glowing_and_long_lived(self):
        particle = read_json(
            RP / "particles" / "wandering_firefly.json"
        )["particle_effect"]
        components = particle["components"]

        self.assertEqual(
            "tf_slice:wandering_firefly",
            particle["description"]["identifier"],
        )
        self.assertIn("minecraft:particle_appearance_lighting", components)
        self.assertEqual(
            "Math.random(1.5, 2.5)",
            components["minecraft:particle_lifetime_expression"][
                "max_lifetime"
            ],
        )
        self.assertTrue(
            (RP / "textures" / "particle" / "firefly.png").is_file()
        )

    def test_client_spawns_fireflies_only_in_the_twilight_dimension(self):
        source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")

        self.assertIn("def _update_ambient_fireflies", source)
        self.assertIn("GetCurrentDimension", source)
        self.assertIn("config.DIMENSION_ID", source)
        self.assertIn("config.AMBIENT_FIREFLY_PARTICLE", source)
        self.assertIn('AMBIENT_FIREFLY_PARTICLE = "tf_slice:wandering_firefly"', config_source)


class TwilightSkyContractTests(unittest.TestCase):
    def test_twilight_air_fog_does_not_wash_the_sky_out_green(self):
        fog = read_json(
            RP / "fogs" / "twilight_forest.fog.json"
        )["minecraft:fog_settings"]["distance"]

        for medium in ("air", "weather"):
            settings = fog[medium]
            self.assertEqual("#20224A", settings["fog_color"])
            self.assertEqual("render", settings["render_distance_type"])
            self.assertGreaterEqual(settings["fog_start"], 0.8)
            self.assertEqual(1.0, settings["fog_end"])

    def test_target_engine_uses_legacy_sky_instead_of_vibrant_visuals(self):
        manifest = read_json(RP / "manifest.json")
        self.assertNotIn("pbr", manifest.get("capabilities", []))
        self.assertLessEqual(
            manifest["header"]["min_engine_version"],
            [1, 21, 90],
        )

    def test_twilight_stars_use_a_dimension_scoped_static_cubemap(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        self.assertIn("CF.CreateSkyRender(LEVEL_ID)", client_source)
        self.assertIn("def _update_twilight_sky", client_source)
        self.assertIn("GetCurrentDimension()", client_source)
        self.assertIn("config.DIMENSION_ID", client_source)
        self.assertIn("SetSkyTextures(", client_source)
        self.assertIn("ResetSkyTextures()", client_source)
        self.assertIn("TWILIGHT_SKY_TEXTURES", config_source)
        self.assertIn("SetStarBrightness(", client_source)
        self.assertIn(
            "config.TWILIGHT_STAR_BRIGHTNESS",
            client_source,
        )
        self.assertIn("ResetStarBrightness()", client_source)
        self.assertIn(
            "config.TWILIGHT_SKY_REFRESH_TICKS",
            client_source,
        )
        self.assertIn(
            "TWILIGHT_STAR_BRIGHTNESS = 0.0",
            config_source,
        )
        self.assertIn(
            "TWILIGHT_SKY_REFRESH_TICKS = 20",
            config_source,
        )
        for forbidden in (
            "_twilight_starfield",
            "_starfield_model",
            "CreateFreeModel",
            "SetFreeModelPos",
            "SetFreeModelRot",
            "SetFreeModelScale",
            "RemoveFreeModel",
        ):
            self.assertNotIn(forbidden, client_source)
        self.assertNotIn("TWILIGHT_STARFIELD_", config_source)
        self.assertFalse((RP / "materials" / "sky.material").exists())
        self.assertFalse(
            (
                RP
                / "shaders"
                / "glsl"
                / "twilight_stars.fragment"
            ).exists()
        )

        for obsolete in (
            RP / "models" / "netease_models.json",
            RP / "models" / "mesh" / "twilight_stars_mesh.json",
            RP / "models" / "skeleton" / "twilight_stars_skeleton.json",
            RP / "textures" / "models" / "tf_slice" / "twilight_star.png",
            RP / "particles" / "twilight_starfield.json",
            RP / "materials" / "entity.material",
            RP / "materials" / "common.json",
        ):
            self.assertFalse(obsolete.exists(), str(obsolete))

    def test_twilight_star_cubemap_has_all_six_static_faces(self):
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        texture_names = (
            "negative_z",
            "positive_x",
            "positive_z",
            "negative_x",
            "positive_y",
            "negative_y",
        )
        for texture_name in texture_names:
            texture_path = (
                "textures/environment/twilight_sky/"
                + texture_name
            )
            png_path = RP / (texture_path + ".png")
            self.assertTrue(png_path.is_file(), str(png_path))
            self.assertGreater(png_path.stat().st_size, 1024)
            self.assertIn(texture_path, config_source)
        self.assertTrue((ROOT / "tools" / "build_twilight_skybox.py").is_file())

    def test_twilight_star_cubemap_reproduces_upstream_quad_generation(self):
        generator_path = ROOT / "tools" / "build_twilight_skybox.py"
        self.assertTrue(generator_path.is_file())
        spec = importlib.util.spec_from_file_location(
            "build_twilight_skybox",
            generator_path,
        )
        generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generator)

        self.assertEqual(10842, generator.STAR_SEED)
        self.assertEqual(3000, generator.STAR_ATTEMPTS)
        self.assertEqual(0.15, generator.STAR_MIN_SIZE)
        self.assertEqual(0.25, generator.STAR_MAX_SIZE)
        self.assertEqual((32, 34, 74, 255), generator.SKY_COLOR)

        with tempfile.TemporaryDirectory() as directory:
            stats = generator.build_skybox(Path(directory))
            self.assertGreaterEqual(stats["accepted_stars"], 1400)
            self.assertLessEqual(stats["accepted_stars"], 1800)
            for texture_name in generator.FACE_NAMES:
                generated = Path(directory) / (texture_name + ".png")
                committed = (
                    RP
                    / "textures"
                    / "environment"
                    / "twilight_sky"
                    / (texture_name + ".png")
                )
                self.assertEqual(
                    committed.read_bytes(),
                    generated.read_bytes(),
                    texture_name,
                )
                with Image.open(generated) as image:
                    self.assertEqual("RGBA", image.mode)
                    self.assertEqual((512, 512), image.size)

    def test_twilight_sky_uses_the_engine_client_tick(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        init_source = client_source[
            client_source.index("    def __init__") :
            client_source.index("    def Destroy")
        ]
        update_source = client_source[
            client_source.index("    def Update") :
            client_source.index("    def OnScriptTickClient")
        ]

        self.assertIn('"OnScriptTickClient"', init_source)
        self.assertIn("self.OnScriptTickClient", init_source)
        self.assertIn(
            "    def OnScriptTickClient(self):",
            client_source,
        )
        self.assertNotIn(
            "    def OnScriptTickClient(self, args):",
            client_source,
        )
        tick_source = client_source[
            client_source.index("    def OnScriptTickClient") :
            client_source.index("    def OnDimensionChangeClientEvent")
        ]
        self.assertIn("self._update_twilight_sky()", tick_source)
        self.assertIn("self._update_twilight_cloud_layer()", tick_source)
        self.assertNotIn("self._update_twilight_sky()", update_source)

    def test_twilight_sky_resets_across_client_dimension_lifecycle(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        init_source = client_source[
            client_source.index("    def __init__") :
            client_source.index("    def Destroy")
        ]

        self.assertIn('"DimensionChangeClientEvent"', init_source)
        self.assertIn("self.OnDimensionChangeClientEvent", init_source)
        self.assertIn('"DimensionChangeFinishClientEvent"', init_source)
        self.assertIn(
            "self.OnDimensionChangeFinishClientEvent",
            init_source,
        )
        start_source = client_source[
            client_source.index(
                "    def OnDimensionChangeClientEvent"
            ) :
            client_source.index(
                "    def OnDimensionChangeFinishClientEvent"
            )
        ]
        finish_source = client_source[
            client_source.index(
                "    def OnDimensionChangeFinishClientEvent"
            ) :
            client_source.index("    def OnUiInitFinished")
        ]
        self.assertIn("self._reset_twilight_sky()", start_source)
        self.assertIn("self._reset_twilight_cloud_layer()", start_source)
        self.assertIn(
            "self._twilight_sky_ui_ready = False",
            start_source,
        )
        self.assertIn(
            "self._discard_twilight_sky_renderer_candidate()",
            finish_source,
        )
        self.assertIn(
            "self._twilight_sky_render_ready = False",
            finish_source,
        )
        self.assertIn(
            "self._update_twilight_sky()",
            finish_source,
        )

    def test_twilight_rendering_stays_blocked_until_dimension_finish(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        init_source = client_source[
            client_source.index("    def __init__") :
            client_source.index("    def Destroy")
        ]
        start_source = client_source[
            client_source.index("    def OnDimensionChangeClientEvent") :
            client_source.index("    def OnDimensionChangeFinishClientEvent")
        ]
        finish_source = client_source[
            client_source.index("    def OnDimensionChangeFinishClientEvent") :
            client_source.index("    def OnUiInitFinished")
        ]
        sky_source = client_source[
            client_source.index("    def _update_twilight_sky") :
            client_source.index("    def _reset_twilight_cloud_layer")
        ]
        cloud_source = client_source[
            client_source.index("    def _update_twilight_cloud_layer") :
            client_source.index("    def _update_ambient_fireflies")
        ]
        firefly_source = client_source[
            client_source.index("    def _update_ambient_fireflies") :
            client_source.index("    def OnBossSync")
        ]

        self.assertIn("self._twilight_dimension_switching = False", init_source)
        self.assertIn("self._twilight_dimension_switching = True", start_source)
        self.assertIn("self._twilight_dimension_switching = False", finish_source)
        self.assertLess(
            sky_source.index("if self._twilight_dimension_switching:"),
            sky_source.index("GetCurrentDimension()"),
        )
        self.assertLess(
            sky_source.index("if not self._twilight_sky_ui_ready:"),
            sky_source.index("GetCurrentDimension()"),
        )
        self.assertLess(
            cloud_source.index("if self._twilight_dimension_switching:"),
            cloud_source.index("GetCurrentDimension()"),
        )
        self.assertLess(
            cloud_source.index("if not self._twilight_sky_ui_ready:"),
            cloud_source.index("GetCurrentDimension()"),
        )
        self.assertLess(
            cloud_source.index("if not self._twilight_sky_render_ready:"),
            cloud_source.index("GetCurrentDimension()"),
        )
        self.assertLess(
            firefly_source.index("if self._twilight_dimension_switching:"),
            firefly_source.index("GetCurrentDimension()"),
        )
        self.assertLess(
            firefly_source.index("if not self._twilight_sky_ui_ready:"),
            firefly_source.index("GetCurrentDimension()"),
        )
        self.assertLess(
            firefly_source.index("if not self._twilight_sky_render_ready:"),
            firefly_source.index("GetCurrentDimension()"),
        )

    def test_twilight_sky_emits_bounded_runtime_diagnostics(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")

        self.assertIn("import mod_log", client_source)
        self.assertIn(
            "clientApi.SetMcpModLogCanPostDump(True)",
            client_source,
        )
        self.assertIn("clientApi.PostMcpModDump(", client_source)
        self.assertIn("mod_log.logger.info(", client_source)
        self.assertIn("def _log_twilight_sky", client_source)
        self.assertIn("[TF_SKY_DIAG]", client_source)
        self.assertIn("GetUseStarBrightness()", client_source)
        self.assertIn("GetStarBrightness()", client_source)
        self.assertIn("GetSkyTextures()", client_source)
        self.assertIn(
            "TWILIGHT_SKY_DIAGNOSTIC_LIMIT = 12",
            config_source,
        )
        self.assertIn(
            "config.TWILIGHT_SKY_DIAGNOSTIC_LIMIT",
            client_source,
        )

    def test_twilight_sky_waits_for_renderer_and_confirms_the_native_state(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        init_source = client_source[
            client_source.index("    def __init__") :
            client_source.index("    def Destroy")
        ]
        ui_ready_source = client_source[
            client_source.index("    def OnUiInitFinished") :
            client_source.index("    def _ensure_magic_map_ui")
        ]

        self.assertIn("self._sky_render_comp = None", init_source)
        self.assertNotIn("CF.CreateSkyRender(LEVEL_ID)", init_source)
        self.assertNotIn(
            "self._twilight_sky_render_ready = True",
            ui_ready_source,
        )
        self.assertIn(
            "self._twilight_sky_ui_ready = True",
            ui_ready_source,
        )
        self.assertIn(
            "self._reset_twilight_sky()",
            ui_ready_source,
        )
        self.assertIn(
            "self._twilight_sky_override_dirty = False",
            client_source[
                client_source.index("    def _reset_twilight_sky") :
                client_source.index(
                    "    def _ensure_twilight_sky_component"
                )
            ],
        )
        self.assertIn(
            "TWILIGHT_SKY_RENDER_WARMUP_TICKS = 40",
            config_source,
        )
        self.assertNotIn("TWILIGHT_SKY_BOOTSTRAP_WARMUP_TICKS", config_source)
        self.assertIn(
            "def _ensure_twilight_sky_component",
            client_source,
        )
        self.assertIn(
            "if not self._advance_twilight_sky_renderer_warmup():",
            client_source,
        )
        self.assertIn(
            "< warmupTicks",
            client_source,
        )
        self.assertIn(
            "def _twilight_sky_application_succeeded",
            client_source,
        )
        for confirmation in (
            "textureResult is not False",
            "observedTextures == list(config.TWILIGHT_SKY_TEXTURES)",
            "brightnessResult is not False",
            "observedUseBrightness is True",
            "observedBrightness == config.TWILIGHT_STAR_BRIGHTNESS",
        ):
            self.assertIn(confirmation, client_source)
        self.assertNotIn(
            "self._twilight_sky_active = textureResult is not False",
            client_source,
        )
        self.assertIn(
            "self._twilight_sky_override_dirty = True",
            client_source,
        )
        dirty_index = client_source.index(
            "self._twilight_sky_override_dirty = True",
            client_source.index("    def _update_twilight_sky"),
        )
        self.assertLess(
            dirty_index,
            client_source.index("SetSkyTextures(", dirty_index),
        )
        self.assertIn(
            "self._twilight_sky_override_dirty",
            client_source[
                client_source.index("    def _reset_twilight_sky") :
                client_source.index(
                    "    def _ensure_twilight_sky_component"
                )
            ],
        )
        update_source = client_source[
            client_source.index("    def _update_twilight_sky") :
            client_source.index("    def _update_ambient_fireflies")
        ]
        self.assertIn(
            "if not self._twilight_sky_active:",
            update_source,
        )
        self.assertIn(
            "self._discard_twilight_sky_renderer_candidate()",
            update_source,
        )
        discard_source = client_source[
            client_source.index(
                "    def _discard_twilight_sky_renderer_candidate"
            ) :
            client_source.index("    def _ensure_twilight_sky_component")
        ]
        self.assertIn("self._sky_render_comp = None", discard_source)
        self.assertIn(
            "self._twilight_sky_render_ready = False",
            discard_source,
        )

    def test_twilight_sky_waits_for_ui_before_native_renderer_bootstrap(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        ui_ready_source = client_source[
            client_source.index("    def OnUiInitFinished") :
            client_source.index("    def _ensure_magic_map_ui")
        ]
        warmup_source = client_source[
            client_source.index(
                "    def _advance_twilight_sky_renderer_warmup"
            ) :
            client_source.index("    def _update_twilight_sky")
        ]
        update_source = client_source[
            client_source.index("    def _update_twilight_sky") :
            client_source.index("    def _update_ambient_fireflies")
        ]

        self.assertNotIn(
            "self._twilight_sky_render_ready = True",
            ui_ready_source,
        )
        self.assertIn(
            "def _advance_twilight_sky_renderer_warmup",
            client_source,
        )
        self.assertIn(
            "if not self._twilight_sky_ui_ready:\n            return False",
            warmup_source,
        )
        self.assertLess(
            warmup_source.index("if not self._twilight_sky_ui_ready:"),
            warmup_source.index("clientApi.GetLocalPlayerId()"),
        )
        self.assertNotIn("TWILIGHT_SKY_BOOTSTRAP_WARMUP_TICKS", config_source)
        self.assertNotIn("TWILIGHT_SKY_BOOTSTRAP_WARMUP_TICKS", client_source)
        self.assertIn("clientApi.GetLocalPlayerId()", warmup_source)
        self.assertIn("CF.CreatePos(playerId).GetFootPos()", warmup_source)
        self.assertLess(
            update_source.index("if not self._twilight_sky_ui_ready:"),
            update_source.index("GetCurrentDimension()"),
        )
        self.assertIn(
            "self._advance_twilight_sky_renderer_warmup()",
            update_source,
        )
        self.assertIn(
            "self._twilight_sky_render_ready = True",
            client_source[
                client_source.index(
                    "    def _advance_twilight_sky_renderer_warmup"
                ) :
                client_source.index("    def _update_twilight_sky")
            ],
        )

    def test_unstable_native_environment_effects_are_quarantined(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        finish_source = client_source[
            client_source.index("    def OnDimensionChangeFinishClientEvent") :
            client_source.index("    def OnUiInitFinished")
        ]
        component_source = client_source[
            client_source.index("    def _ensure_twilight_sky_component") :
            client_source.index("    def _twilight_sky_application_succeeded")
        ]
        warmup_source = client_source[
            client_source.index(
                "    def _advance_twilight_sky_renderer_warmup"
            ) :
            client_source.index("    def _update_twilight_sky")
        ]
        sky_source = client_source[
            client_source.index("    def _update_twilight_sky") :
            client_source.index("    def _reset_twilight_cloud_layer")
        ]
        cloud_source = client_source[
            client_source.index("    def _update_twilight_cloud_layer") :
            client_source.index("    def _update_ambient_fireflies")
        ]
        firefly_source = client_source[
            client_source.index("    def _update_ambient_fireflies") :
            client_source.index("    def OnBossSync")
        ]
        disabled_guard = (
            "if not config.TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED:"
        )

        self.assertIn(
            "TWILIGHT_NATIVE_ENVIRONMENT_EFFECTS_ENABLED = False",
            config_source,
        )
        self.assertIn("self._twilight_sky_render_ready = False", finish_source)
        self.assertNotIn("self._twilight_sky_render_ready = True", finish_source)
        for source, native_call in (
            (component_source, "CF.CreateSkyRender(LEVEL_ID)"),
            (warmup_source, "clientApi.GetLocalPlayerId()"),
            (sky_source, "GetCurrentDimension()"),
            (cloud_source, "GetCurrentDimension()"),
            (firefly_source, "GetCurrentDimension()"),
        ):
            self.assertLess(
                source.index(disabled_guard),
                source.index(native_call),
            )

    def test_twilight_sky_diagnostic_build_uses_a_fresh_pack_version(self):
        behavior_manifest = read_json(BP / "manifest.json")
        resource_manifest = read_json(RP / "manifest.json")
        expected = list(release_metadata.PACK_VERSION)

        self.assertEqual(expected, behavior_manifest["header"]["version"])
        self.assertEqual(expected, resource_manifest["header"]["version"])
        self.assertIn(
            {
                "uuid": resource_manifest["header"]["uuid"],
                "version": expected,
            },
            behavior_manifest["dependencies"],
        )

    def test_twilight_dimension_uses_a_high_dimension_cloud_renderer(self):
        dimension = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]["components"]
        self.assertEqual(
            "minecraft:overworld",
            dimension["netease:dimension_type"],
        )
        cloud_texture = (
            RP
            / "textures"
            / "environment"
            / "33027004_clouds.png"
        )
        self.assertTrue(cloud_texture.is_file())
        self.assertGreater(cloud_texture.stat().st_size, 1024)

        cloud_particle = read_json(
            RP / "particles" / "twilight_cloud_layer.json"
        )["particle_effect"]
        self.assertEqual(
            "tf_slice:twilight_cloud_layer",
            cloud_particle["description"]["identifier"],
        )
        self.assertEqual(
            "textures/environment/33027004_clouds",
            cloud_particle["description"]["basic_render_parameters"][
                "texture"
            ],
        )
        components = cloud_particle["components"]
        self.assertEqual(
            1,
            components["minecraft:emitter_rate_instant"][
                "num_particles"
            ],
        )
        self.assertTrue(
            components["minecraft:emitter_local_space"]["position"]
        )
        self.assertEqual(
            [768.0, 768.0],
            components["minecraft:particle_appearance_billboard"][
                "size"
            ],
        )
        self.assertEqual(
            "emitter_transform_xz",
            components["minecraft:particle_appearance_billboard"][
                "facing_camera_mode"
            ],
        )

        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        for contract in (
            'TWILIGHT_CLOUD_PARTICLE = "tf_slice:twilight_cloud_layer"',
            "TWILIGHT_CLOUD_HEIGHT = 192.0",
            "TWILIGHT_CLOUD_TILE_SIZE = 768.0",
            "TWILIGHT_CLOUD_GRID_RADIUS = 1",
            "TWILIGHT_CLOUD_UPDATE_TICKS = 2",
            "TWILIGHT_CLOUD_DRIFT_PER_TICK = 0.02",
        ):
            self.assertIn(contract, config_source)
        self.assertIn(
            "self._twilight_cloud_particle_comp = "
            "CF.CreateParticleSystem(None)",
            client_source,
        )
        self.assertIn("def _update_twilight_cloud_layer", client_source)
        self.assertIn("def _reset_twilight_cloud_layer", client_source)
        self.assertIn(
            "self._twilight_cloud_particle_comp.Create(",
            client_source,
        )
        self.assertIn(
            "self._twilight_cloud_particle_comp.SetPos(",
            client_source,
        )
        self.assertIn(
            "self._twilight_cloud_particle_comp.Remove(",
            client_source,
        )

    def test_legacy_sky_is_not_occluded_by_deferred_biome_components(self):
        for path in (RP / "biomes").glob("*.client_biome.json"):
            components = read_json(path)["minecraft:client_biome"][
                "components"
            ]
            for deferred_component in (
                "minecraft:atmosphere_identifier",
                "minecraft:color_grading_identifier",
                "minecraft:lighting_identifier",
                "minecraft:water_identifier",
            ):
                self.assertNotIn(
                    deferred_component,
                    components,
                )

    def test_twilight_time_remains_locally_fixed_at_upstream_time(self):
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        server_source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")

        self.assertIn("TWILIGHT_TIME_OF_DAY = 13000", config_source)
        self.assertIn("SetUseLocalTime", server_source)
        self.assertIn("SetLocalTimeOfDay", server_source)
        self.assertIn("SetLocalDoDayNightCycle", server_source)
        self.assertGreaterEqual(
            server_source.count("self._configure_twilight_time()"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
