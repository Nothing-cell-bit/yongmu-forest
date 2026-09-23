# -*- coding: utf-8 -*-
"""Source-parity contracts for the in-scope Twilight trophies."""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image, ImageChops


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
if str(BP) not in sys.path:
    sys.path.insert(0, str(BP))

from tools import build_public_block_shapes as builder
from TwilightBossSlice import release_metadata


IN_SCOPE_TROPHIES = (
    "naga",
    "lich",
    "hydra",
    "ur_ghast",
    "knight_phantom",
    "minoshroom",
    "quest_ram",
)


class TrophyModelParityTests(unittest.TestCase):
    def test_trophy_runtime_cache_generation_is_0_11_99(self):
        """Collision-free items and break effects must not reuse 0.11.98."""
        self.assertEqual((0, 12, 0), release_metadata.PACK_VERSION)

    def test_trophy_only_rebuild_refreshes_creative_item_aliases(self):
        self.assertTrue(hasattr(builder, "normalize_trophy_creative_catalog"))
        source = (ROOT / "tools" / "build_public_block_shapes.py").read_text(
            encoding="utf-8"
        )
        section = source[source.index("def build_trophy_resources") :]
        section = section[: section.index("def build()")]
        self.assertIn("normalize_trophy_creative_catalog()", section)

    def test_trophy_only_rebuild_entrypoint_avoids_unrelated_public_blocks(self):
        terrain = {"texture_data": {}}
        item_atlas = {"texture_data": {}}
        client_blocks = {}
        creative_catalog = {
            "minecraft:crafting_items_catalog": {"categories": []}
        }
        trophy_geometry = {
            "format_version": "1.12.0",
            "minecraft:geometry": [
                {"description": {"identifier": "geometry.tf_slice.naga_trophy"}}
            ],
        }
        with mock.patch.object(
            builder,
            "load_json",
            side_effect=[terrain, item_atlas, client_blocks, creative_catalog],
        ), mock.patch.object(
            builder,
            "trophy_geometry_document",
            return_value=trophy_geometry,
        ), mock.patch.object(
            builder,
            "trophy_wearable_geometry_document",
            return_value={"format_version": "1.12.0", "minecraft:geometry": []},
        ), mock.patch.object(
            builder,
            "trophy_floor_rotation_geometry_document",
            return_value={"format_version": "1.12.0", "minecraft:geometry": []},
        ), mock.patch.object(
            builder,
            "trophy_wearable_animation_document",
            return_value={"format_version": "1.8.0", "animations": {}},
        ), mock.patch.object(
            builder,
            "ur_ghast_trophy_visual_geometry_document",
            return_value={"format_version": "1.12.0", "minecraft:geometry": []},
        ), mock.patch.object(
            builder,
            "ur_ghast_trophy_visual_animation_document",
            return_value={"format_version": "1.8.0", "animations": {}},
        ), mock.patch.object(
            builder,
            "ur_ghast_trophy_visual_client_document",
            return_value={"format_version": "1.10.0", "minecraft:client_entity": {}},
        ), mock.patch.object(
            builder,
            "ur_ghast_trophy_visual_behavior_document",
            return_value={"format_version": "1.20.0", "minecraft:entity": {}},
        ), mock.patch.object(
            Path,
            "exists",
            return_value=False,
        ), mock.patch.object(builder, "write_json") as write_json, mock.patch.object(
            builder, "build_trophies"
        ) as build_trophies:
            result = builder.build_trophy_resources()
        build_trophies.assert_called_once()
        written = {call.args[0] for call in write_json.call_args_list}
        self.assertEqual(
            {
                builder.RP / "models" / "blocks" / "public_trophies.geo.json",
                builder.RP
                / "models"
                / "blocks"
                / "trophy_floor_rotations.geo.json",
                builder.RP
                / "models"
                / "entity"
                / "ur_ghast_trophy_visual.geo.json",
                builder.RP / "animations" / "trophy.animation.json",
                builder.RP / "models" / "entity" / "wearable_trophies.geo.json",
                *(builder.RP / "attachables" / (name + "_trophy.attachable.json") for name in IN_SCOPE_TROPHIES),
                *(builder.BP / "items" / (name + "_trophy.item.json") for name in IN_SCOPE_TROPHIES),
                builder.RP / "entity" / "ur_ghast_trophy_visual.entity.json",
                builder.BP / "entities" / "ur_ghast_trophy_visual.entity.json",
                builder.RP / "textures" / "terrain_texture.json",
                builder.RP / "textures" / "item_texture.json",
                builder.RP / "blocks.json",
                builder.BP
                / "item_catalog"
                / "crafting_item_catalog.json",
            },
            written,
        )
        self.assertEqual(len(builder.INTERNAL_TROPHY_BLOCK_IDS), result["trophies"])

    def test_locked_upstream_trophy_geometry_has_exact_part_coverage(self):
        expected = {
            "naga": (2, {"root", "head", "tongue"}, (64, 32)),
            "lich": (2, {"root", "head", "crown"}, (64, 64)),
            "hydra": (16, {"root", "head", "jaw", "frill"}, (512, 256)),
            "ur_ghast": (
                37,
                {"root", "body"}
                | {
                    "tentacle_%d_%s" % (index, suffix)
                    for index in range(9)
                    for suffix in ("base", "extension", "extension_2", "tip")
                },
                (64, 32),
            ),
            "knight_phantom": (
                6,
                {
                    "root",
                    "head",
                    "helmet",
                    "right_horn_1",
                    "right_horn_2",
                    "left_horn_1",
                    "left_horn_2",
                },
                (128, 32),
            ),
            "minoshroom": (
                6,
                {
                    "root",
                    "head",
                    "snout",
                    "right_horn_1",
                    "right_horn_2",
                    "left_horn_1",
                    "left_horn_2",
                },
                (128, 32),
            ),
            "quest_ram": (16, {"root", "head", "nose"}, (128, 128)),
        }
        document = builder.trophy_geometry_document()
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in document["minecraft:geometry"]
        }
        self.assertEqual(
            {
                "geometry.tf_slice.%s_trophy" % name
                for name in IN_SCOPE_TROPHIES
            },
            set(geometries),
        )
        for name, (cube_count, bones, texture_size) in expected.items():
            geometry = geometries["geometry.tf_slice.%s_trophy" % name]
            self.assertEqual(
                cube_count,
                sum(len(bone.get("cubes", [])) for bone in geometry["bones"]),
                name,
            )
            self.assertEqual(bones, {bone["name"] for bone in geometry["bones"]}, name)
            self.assertEqual(texture_size[0], geometry["description"]["texture_width"], name)
            self.assertEqual(texture_size[1], geometry["description"]["texture_height"], name)

    def test_trophy_specs_use_locked_original_model_and_item_textures(self):
        self.assertEqual(set(IN_SCOPE_TROPHIES), set(builder.TROPHY_SPECS))
        expected_models = {
            "naga": ("model/nagahead.png",),
            "lich": ("model/twilightlich64.png",),
            "hydra": ("model/hydra4.png",),
            "ur_ghast": ("model/towerboss.png",),
            "knight_phantom": (
                "model/phantomskeleton.png",
                "armor/phantom_1.png",
            ),
            "minoshroom": ("model/minoshroomtaur.png",),
            "quest_ram": ("model/questram.png",),
        }
        expected_items = {
            "naga": "item/naga_trophy.png",
            "lich": "item/lich_trophy.png",
            "hydra": "item/hydra_trophy.png",
            "ur_ghast": "item/ur_ghast_trophy.png",
            "knight_phantom": "item/trophy_minor.png",
            "minoshroom": "item/trophy_minor.png",
            "quest_ram": "item/trophy_quest.png",
        }
        for name in IN_SCOPE_TROPHIES:
            spec = builder.TROPHY_SPECS[name]
            self.assertEqual(expected_models[name], tuple(spec["model_textures"]), name)
            self.assertEqual(expected_items[name], spec["item_texture"], name)
            for source in spec["model_textures"]:
                self.assertTrue((builder.UPSTREAM_TEXTURES / source).is_file(), source)
            self.assertTrue(
                (builder.UPSTREAM_TEXTURES / spec["item_texture"]).is_file(),
                spec["item_texture"],
            )
        self.assertEqual(
            {
                "knight_phantom": 32,
                "minoshroom": 32,
                "quest_ram": 16,
            },
            {
                name: builder.TROPHY_SPECS[name]["icon_foreground_size"]
                for name in ("knight_phantom", "minoshroom", "quest_ram")
            },
        )

    def test_generated_trophy_icons_use_upstream_major_or_composited_minor_art(self):
        for name in ("naga", "lich", "hydra", "ur_ghast"):
            source = builder.UPSTREAM_TEXTURES / builder.TROPHY_SPECS[name][
                "item_texture"
            ]
            target = builder.RP / "textures" / "blocks" / (name + "_trophy.png")
            self.assertEqual(source.read_bytes(), target.read_bytes(), name)
        for name in ("knight_phantom", "minoshroom", "quest_ram"):
            source = builder.UPSTREAM_TEXTURES / builder.TROPHY_SPECS[name][
                "item_texture"
            ]
            target = builder.RP / "textures" / "blocks" / (name + "_trophy.png")
            self.assertNotEqual(source.read_bytes(), target.read_bytes(), name)
            image = Image.open(target).convert("RGBA")
            expected_size = 16 if name == "quest_ram" else 32
            self.assertEqual((expected_size, expected_size), image.size, name)
            self.assertIsNotNone(image.getbbox(), name)
            self.assertTrue(
                {alpha for _red, _green, _blue, alpha in image.getdata()}
                <= {0, 255},
                name,
            )
        self.assertIn(
            "output_size",
            builder._render_geometry_item_icon.__code__.co_varnames[
                : builder._render_geometry_item_icon.__code__.co_argcount
            ],
        )
        self.assertIn(
            "projection_mode",
            builder._render_geometry_item_icon.__code__.co_varnames[
                : builder._render_geometry_item_icon.__code__.co_argcount
            ],
        )
        composite_source = (ROOT / "tools" / "build_public_block_shapes.py").read_text(
            encoding="utf-8"
        )
        composite_source = composite_source[
            composite_source.index("def _build_composited_trophy_item_icon") :
        ]
        composite_source = composite_source[: composite_source.index("def trophy_item_document")]
        self.assertIn('projection_mode="front"', composite_source)
        self.assertIn("output_size=foreground_size", composite_source)
        self.assertIn('Image.new("RGBA", (canvas_size, canvas_size)', composite_source)
        self.assertIn("ImageFilter.MaxFilter", composite_source)

    def test_obsolete_slanted_trophy_item_visual_geometry_is_retired(self):
        self.assertFalse(hasattr(builder, "trophy_item_icon_geometry_document"))

    def test_scaled_trophies_preserve_unscaled_box_uv_extents(self):
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in builder.trophy_geometry_document()["minecraft:geometry"]
        }
        expected = {
            "naga": {
                "bone": "head",
                "cube": 0,
                "north": [16.0, 16.0],
                "east": [16.0, 16.0],
                "up": [-16.0, -16.0],
            },
            "hydra": {
                "bone": "head",
                "cube": 0,
                "north": [32.0, 24.0],
                "east": [32.0, 24.0],
                "up": [-32.0, -32.0],
            },
            "ur_ghast": {
                "bone": "body",
                "cube": 0,
                "north": [16.0, 16.0],
                "east": [16.0, 16.0],
                "up": [-16.0, -16.0],
            },
            "quest_ram": {
                "bone": "head",
                "cube": 0,
                "north": [12.0, 9.0],
                "east": [15.0, 9.0],
                "up": [-12.0, -15.0],
            },
        }
        for name, case in expected.items():
            geometry = geometries["geometry.tf_slice.%s_trophy" % name]
            bone = next(value for value in geometry["bones"] if value["name"] == case["bone"])
            cube = bone["cubes"][case["cube"]]
            self.assertIsInstance(cube["uv"], dict, name)
            for face in ("north", "east", "up"):
                self.assertEqual(case[face], cube["uv"][face]["uv_size"], (name, face))

    def test_item_icon_renderer_applies_parented_bone_rotation(self):
        texture = Image.new("RGBA", (16, 16), (255, 255, 255, 255))
        base = {
            "description": {"texture_width": 16, "texture_height": 16},
            "bones": [
                {"name": "root", "pivot": [0, 0, 0]},
                {
                    "name": "arm",
                    "parent": "root",
                    "pivot": [0, 0, 0],
                    "cubes": [{"origin": [1, 0, 0], "size": [4, 1, 1], "uv": [0, 0]}],
                },
            ],
        }
        rotated = json.loads(json.dumps(base))
        rotated["bones"][1]["rotation"] = [0, 0, 90]
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            texture_path = directory / "texture.png"
            plain_path = directory / "plain.png"
            rotated_path = directory / "rotated.png"
            texture.save(texture_path)
            builder._render_geometry_item_icon(base, texture_path, plain_path)
            builder._render_geometry_item_icon(rotated, texture_path, rotated_path)
            plain = Image.open(plain_path).convert("RGBA")
            rotated_image = Image.open(rotated_path).convert("RGBA")
            self.assertIsNotNone(ImageChops.difference(plain, rotated_image).getbbox())

    def test_every_trophy_icon_renders_without_degenerate_projected_faces(self):
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in builder.trophy_geometry_document()["minecraft:geometry"]
        }
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            for name in IN_SCOPE_TROPHIES:
                target = directory / (name + ".png")
                texture = (
                    builder.RP
                    / "textures"
                    / "entity"
                    / "tf_slice"
                    / "trophies"
                    / (name + ".png")
                )
                builder._render_geometry_item_icon(
                    geometries["geometry.tf_slice.%s_trophy" % name],
                    texture,
                    target,
                )
                image = Image.open(target).convert("RGBA")
                self.assertEqual((64, 64), image.size, name)
                self.assertIsNotNone(image.getbbox(), name)
                if name == "naga":
                    red_eye_pixels = sum(
                        1
                        for red, green, blue, alpha in image.get_flattened_data()
                        if alpha
                        and red > 100
                        and red > green * 1.4
                        and red > blue * 1.4
                    )
                    self.assertGreater(red_eye_pixels, 0)
                if name == "lich":
                    opaque_pixels = sum(
                        1
                        for _red, _green, _blue, alpha in image.get_flattened_data()
                        if alpha
                    )
                    self.assertGreater(opaque_pixels, 800)

    def test_knight_phantom_combined_atlas_preserves_both_original_textures(self):
        combined = Image.open(
            builder.RP
            / "textures"
            / "entity"
            / "tf_slice"
            / "trophies"
            / "knight_phantom.png"
        ).convert("RGBA")
        self.assertEqual((128, 32), combined.size)
        sources = (
            (0, "model/phantomskeleton.png"),
            (64, "armor/phantom_1.png"),
        )
        for x_offset, source_name in sources:
            source = Image.open(
                builder.UPSTREAM_TEXTURES / source_name
            ).convert("RGBA")
            self.assertEqual(
                source.tobytes(),
                combined.crop((x_offset, 0, x_offset + 64, 32)).tobytes(),
                source_name,
            )

    def test_trophy_wearables_preserve_player_rendering_and_equipment(self):
        animation = builder.trophy_animation_document()["animations"]
        self.assertIn(
            "animation.tf_slice.trophy_wearable.hide_first_person", animation
        )
        server = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            encoding="utf-8"
        )
        self.assertTrue("def _try_equip_trophy" in server)
        self.assertTrue("def _queue_trophy_equip" in server)
        self.assertFalse("def _restore_trophies_from_armor" in server)
        ready = server[server.index("    def OnClientReady") :]
        ready = ready[: ready.index("    def OnDimensionChangeServerEvent")]
        self.assertNotIn("self._restore_trophies_from_armor", ready)

    def test_floor_trophy_rotations_are_baked_without_illegal_transformations(self):
        entries = builder.trophy_floor_rotation_geometry_document()[
            "minecraft:geometry"
        ]
        self.assertEqual(29, len(entries))
        self.assertEqual(
            {
                "geometry.tf_slice.%s_trophy_rotation_%d" % (name, rotation)
                for name in IN_SCOPE_TROPHIES
                for rotation in (0, 4, 8, 12)
            },
            {
                entry["description"]["identifier"]
                for entry in entries
                if entry["description"]["identifier"]
                != "geometry.tf_slice.ur_ghast_trophy_body"
            },
        )
        self.assertIn(
            "geometry.tf_slice.ur_ghast_trophy_body",
            {entry["description"]["identifier"] for entry in entries},
        )
        sample = next(
            entry
            for entry in entries
            if entry["description"]["identifier"]
            == "geometry.tf_slice.naga_trophy_rotation_4"
        )
        root = next(bone for bone in sample["bones"] if bone["name"] == "root")
        self.assertEqual([0.0, 90.0, 0.0], root["rotation"])

        geometries = {
            entry["description"]["identifier"]: entry
            for entry in builder.trophy_geometry_document()["minecraft:geometry"]
        }
        for name in IN_SCOPE_TROPHIES:
            block = builder.trophy_document(
                "%s_trophy" % name,
                "%s_trophy" % name,
                "geometry.tf_slice.%s_trophy" % name,
                geometries["geometry.tf_slice.%s_trophy" % name],
                wall=False,
            )["minecraft:block"]
            self.assertEqual(8, len(block["permutations"]), name)
            for permutation in block["permutations"]:
                self.assertNotIn(
                    "minecraft:transformation", permutation["components"], name
                )
                self.assertIn("minecraft:geometry", permutation["components"], name)

    def test_ur_ghast_trophy_uses_animated_visual_entity(self):
        geometry = next(
            entry
            for entry in builder.trophy_geometry_document()["minecraft:geometry"]
            if entry["description"]["identifier"]
            == "geometry.tf_slice.ur_ghast_trophy"
        )
        for wall, expected_permutations in ((False, 8), (True, 8)):
            name = "ur_ghast_%strophy" % ("wall_" if wall else "")
            block = builder.trophy_document(
                name,
                "ur_ghast_trophy",
                "geometry.tf_slice.ur_ghast_trophy",
                geometry,
                wall=wall,
            )["minecraft:block"]
            self.assertNotIn(
                "tf_slice:animation_frame", block["description"]["states"]
            )
            self.assertEqual(
                {"tick": True, "movable": False},
                block["components"]["netease:block_entity"],
            )
            self.assertEqual(
                {"value": True},
                block["components"].get("netease:listen_block_remove"),
            )
            self.assertEqual(expected_permutations, len(block["permutations"]))

        visual_geometry = builder.ur_ghast_trophy_visual_geometry_document()[
            "minecraft:geometry"
        ][0]
        visual_bones = {bone["name"]: bone for bone in visual_geometry["bones"]}
        self.assertTrue(visual_bones["body"].get("cubes", []))
        self.assertEqual(
            36,
            sum(
                1
                for name in visual_bones
                if name.startswith("tentacle_")
            ),
        )
        base_pivots = {
            tuple(visual_bones["tentacle_%d_base" % index]["pivot"])
            for index in range(9)
        }
        trophy_bones = {bone["name"]: bone for bone in geometry["bones"]}
        self.assertEqual(
            {
                tuple(trophy_bones["tentacle_%d_base" % index]["pivot"])
                for index in range(9)
            },
            base_pivots,
        )
        for index in range(9):
            expected_rotation = trophy_bones[
                "tentacle_%d_base" % index
            ].get("rotation")
            if index >= 5:
                expected_rotation = {
                    5: [0.0, 0.0, 45.0],
                    6: [0.0, 0.0, 60.0],
                    7: [0.0, 0.0, -45.0],
                    8: [0.0, 0.0, -60.0],
                }[index]
            self.assertEqual(
                expected_rotation,
                visual_bones["tentacle_%d_base" % index].get("rotation"),
            )
            self.assertEqual(
                "tentacle_%d_extension" % index,
                visual_bones["tentacle_%d_extension_2" % index]["parent"],
            )
            self.assertEqual(
                "tentacle_%d_extension_2" % index,
                visual_bones["tentacle_%d_tip" % index]["parent"],
            )
        animation = builder.ur_ghast_trophy_visual_animation_document()[
            "animations"
        ]["animation.tf_slice.ur_ghast_trophy_visual.idle"]
        shipped_animation = json.loads(
            (builder.RP / "animations/trophy.animation.json").read_text("utf-8")
        )["animations"]["animation.tf_slice.ur_ghast_trophy_visual.idle"]
        self.assertEqual(animation, shipped_animation)
        self.assertTrue(animation["loop"])
        self.assertEqual(36, len(animation["bones"]))
        self.assertTrue(
            animation["bones"]["tentacle_0_base"]["rotation"][0].startswith(
                "11.4592 +"
            )
        )
        for index in range(5, 9):
            side_rotation = animation["bones"][
                "tentacle_%d_base" % index
            ]["rotation"]
            self.assertIn("* 8.5944", side_rotation[0])
            self.assertIn("math.sin", side_rotation[1])
            self.assertIn("* 22.9183", side_rotation[1])
            self.assertEqual(
                0.0,
                side_rotation[2],
            )
        client = builder.ur_ghast_trophy_visual_client_document()[
            "minecraft:client_entity"
        ]["description"]
        self.assertEqual(
            "animation.tf_slice.ur_ghast_trophy_visual.idle",
            client["animations"]["idle"],
        )
        behavior = builder.ur_ghast_trophy_visual_behavior_document()[
            "minecraft:entity"
        ]
        self.assertIn("minecraft:persistent", behavior["components"])

        anchor = builder._ur_ghast_trophy_body_geometry(geometry)
        anchor_cubes = [
            cube
            for bone in anchor["bones"]
            for cube in bone.get("cubes", [])
        ]
        self.assertEqual(1, len(anchor_cubes))
        self.assertEqual([1.0, 1.0, 1.0], anchor_cubes[0]["size"])

        server = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def _ensure_ur_ghast_trophy_visual", server)
        self.assertIn('"tf_slice:ur_ghast_trophy_visual"', server)
        ensure = server[server.index("    def _ensure_ur_ghast_trophy_visual") :]
        ensure = ensure[: ensure.index("    def _register_ur_ghast_trophy_visual")]
        self.assertIn("GetBlockStates", ensure)
        self.assertIn("self._ur_ghast_trophy_visual_yaw", ensure)
        self.assertIn("ur_ghast_trophy_entity_yaw", server)
        self.assertIn("CF.CreateRot(visualId).SetRot((0.0, yaw))", ensure)
        self.assertLess(ensure.index("GetBlockStates"), ensure.index("SetRot((0.0, yaw))"))
        self.assertIn("effective_trophy_rotation", server)
        self.assertIn("effective_trophy_facing", server)
        self.assertIn("def _remove_ur_ghast_trophy_visuals", server)
        add_entity = server[server.index("    def OnAddEntity") :]
        add_entity = add_entity[: add_entity.index("    def OnRemoveEntity")]
        self.assertIn("UR_GHAST_TROPHY_VISUAL", add_entity)
        self.assertIn("self._register_ur_ghast_trophy_visual", add_entity)
        self.assertIn("def _purge_orphaned_ur_ghast_trophy_visuals", server)
        update = server[server.index("    def Update(self):") :]
        self.assertIn("self._purge_orphaned_ur_ghast_trophy_visuals()", update)
        destroy = server[server.index("    def OnServerPlayerTryDestroyBlockEvent") :]
        destroy = destroy[: destroy.index("    def OnBlockRemoveServerEvent")]
        self.assertNotIn("self._remove_ur_ghast_trophy_visuals", destroy)
        self.assertNotIn('"TrophyBreakEffect"', destroy)
        remove = server[server.index("    def OnBlockRemoveServerEvent") :]
        remove = remove[: remove.index("    def OnBlockRandomTickServerEvent")]
        self.assertIn("self._broadcast_trophy_break_effect", remove)
        self.assertIn("def _broadcast_trophy_break_effect", server)
        client = (BP / "TwilightBossSlice" / "clientSystem.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"TrophyBreakEffect"', client)
        self.assertIn("def OnTrophyBreakEffect", client)
        break_handler = client[client.index("    def OnTrophyBreakEffect") :]
        self.assertIn("tf_slice:ur_ghast_trophy_break", break_handler)
        handler = server[server.index("    def OnNagaSpawnerBlockEntityTick") :]
        handler = handler[: handler.index("    def OnChunkGeneratedServerEvent")]
        self.assertLess(
            handler.index("self._ensure_ur_ghast_trophy_visual"),
            handler.index("self._tick_dark_tower_block_entity"),
        )

    def test_lich_crown_naga_height_and_knight_horns_have_clear_silhouettes(self):
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in builder.trophy_geometry_document()["minecraft:geometry"]
        }
        lich = {bone["name"]: bone for bone in geometries[
            "geometry.tf_slice.lich_trophy"
        ]["bones"]}
        self.assertEqual(
            lich["head"]["cubes"][0]["origin"][1] + 4.0,
            lich["crown"]["cubes"][0]["origin"][1],
        )
        naga = geometries["geometry.tf_slice.naga_trophy"]
        naga_bottom = min(
            cube["origin"][1]
            for bone in naga["bones"]
            for cube in bone.get("cubes", [])
        )
        self.assertEqual(0.0, naga_bottom)
        bones = {bone["name"]: bone for bone in geometries[
            "geometry.tf_slice.knight_phantom_trophy"
        ]["bones"]}
        armor_document = json.loads(
            (builder.RP / "models" / "entity" / "phantom_armor.geo.json").read_text(
                encoding="utf-8"
            )
        )
        armor = next(
            entry
            for entry in armor_document["minecraft:geometry"]
            if entry["description"]["identifier"] == "geometry.tf_slice.phantom_helmet"
        )
        armor_bones = {bone["name"]: bone for bone in armor["bones"]}
        for name in ("right_horn_1", "right_horn_2", "left_horn_1", "left_horn_2"):
            self.assertEqual(armor_bones[name]["rotation"], bones[name]["rotation"], name)
            self.assertEqual(
                armor_bones[name]["pivot"][1] - 22,
                bones[name]["pivot"][1],
                name,
            )

        minoshroom = {bone["name"]: bone for bone in geometries[
            "geometry.tf_slice.minoshroom_trophy"
        ]["bones"]}
        self.assertEqual([0, -25, 10], minoshroom["right_horn_1"]["rotation"])
        self.assertEqual([0, -15, 45], minoshroom["right_horn_2"]["rotation"])
        self.assertEqual([0, 25, -10], minoshroom["left_horn_1"]["rotation"])
        self.assertEqual([0, 15, -45], minoshroom["left_horn_2"]["rotation"])

    def test_placement_captures_yaw_and_retries_orientation(self):
        source = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            encoding="utf-8"
        )
        placement = source[source.index("    def OnServerEntityTryPlaceBlockEvent") :]
        placement = placement[: placement.index("    def _orient_placed_trophy")]
        self.assertIn('"yaw": self._get_rotation(playerId)[1]', placement)
        self.assertIn("for delay in (0.05, 0.15, 0.3):", placement)
        orient = source[source.index("    def _orient_placed_trophy") :]
        orient = orient[: orient.index("    def _activate_placed_trophy")]
        self.assertIn('yaw = float(data.get("yaw", 0.0))', orient)
        self.assertNotIn("self._get_rotation(playerId)", orient)

    def test_floor_and_wall_documents_match_upstream_states_and_bounds(self):
        geometries = {
            entry["description"]["identifier"]: entry
            for entry in builder.trophy_geometry_document()["minecraft:geometry"]
        }
        for name in IN_SCOPE_TROPHIES:
            identifier = "geometry.tf_slice.%s_trophy" % name
            geometry = geometries[identifier]
            floor = builder.trophy_document(
                "%s_trophy" % name,
                "%s_trophy" % name,
                identifier,
                geometry,
                wall=False,
            )["minecraft:block"]
            self.assertFalse(
                floor["description"]["register_to_creative_menu"], name
            )
            self.assertEqual(
                [0, 4, 8, 12],
                floor["description"]["states"]["tf_slice:rotation"],
                name,
            )
            self.assertEqual(
                [False, True],
                floor["description"]["states"]["tf_slice:powered"],
                name,
            )
            self.assertEqual(
                ["minecraft:cardinal_direction"],
                floor["description"]["traits"]["minecraft:placement_direction"][
                    "enabled_states"
                ],
                name,
            )
            self.assertEqual(8, len(floor["permutations"]), name)
            bounds_geometry = next(
                entry
                for entry in builder.trophy_floor_rotation_geometry_document()[
                    "minecraft:geometry"
                ]
                if entry["description"]["identifier"]
                == "geometry.tf_slice.%s_trophy_rotation_0" % name
            )
            expected_floor = (
                builder._trophy_source_box(name, wall=False)
                if name == "ur_ghast"
                else builder._geometry_bounds(bounds_geometry)
            )
            self.assertEqual(
                expected_floor,
                floor["components"]["netease:aabb"]["collision"],
                name,
            )
            self.assertEqual(
                expected_floor,
                floor["permutations"][0]["components"]["netease:aabb"]["collision"],
                name,
            )

            wall = builder.trophy_document(
                "%s_wall_trophy" % name,
                "%s_trophy" % name,
                identifier,
                geometry,
                wall=True,
            )["minecraft:block"]
            self.assertFalse(
                wall["description"]["register_to_creative_menu"], name
            )
            self.assertEqual(
                ["north", "east", "south", "west"],
                wall["description"]["states"]["tf_slice:facing"],
                name,
            )
            self.assertEqual(
                [False, True],
                wall["description"]["states"]["tf_slice:powered"],
                name,
            )
            self.assertEqual(
                ["minecraft:cardinal_direction"],
                wall["description"]["traits"]["minecraft:placement_direction"][
                    "enabled_states"
                ],
                name,
            )
            self.assertEqual(8, len(wall["permutations"]), name)

    def test_native_cardinal_fallback_faces_back_towards_the_player(self):
        geometry = builder.trophy_geometry_document()["minecraft:geometry"][0]
        floor = builder.trophy_document(
            "naga_trophy",
            "naga_trophy",
            "geometry.tf_slice.naga_trophy",
            geometry,
            wall=False,
        )["minecraft:block"]
        floor_expected = {"south": 0, "west": 4, "north": 8, "east": 12}
        for permutation in floor["permutations"][-4:]:
            condition = permutation["condition"]
            cardinal = next(value for value in floor_expected if "'%s'" % value in condition)
            self.assertTrue(
                permutation["components"]["minecraft:geometry"].endswith(
                    "_rotation_%d" % floor_expected[cardinal]
                ),
                cardinal,
            )

        wall = builder.trophy_document(
            "naga_wall_trophy",
            "naga_trophy",
            "geometry.tf_slice.naga_trophy",
            geometry,
            wall=True,
        )["minecraft:block"]
        wall_expected = {
            "south": [0, 0, 0],
            "west": [0, 90, 0],
            "north": [0, 180, 0],
            "east": [0, -90, 0],
        }
        for permutation in wall["permutations"][-4:]:
            condition = permutation["condition"]
            cardinal = condition.split(
                "minecraft:cardinal_direction') == '", 1
            )[1].split("'", 1)[0]
            self.assertEqual(
                wall_expected[cardinal],
                permutation["components"]["minecraft:transformation"]["rotation"],
                cardinal,
            )

    def test_all_in_scope_floor_and_wall_ids_are_registered_for_runtime_and_creative(self):
        public_item_ids = {
            "tf_slice:%s_trophy_item" % name for name in IN_SCOPE_TROPHIES
        }
        block_ids = {
            "tf_slice:%s%s_trophy" % (name, wall)
            for name in IN_SCOPE_TROPHIES
            for wall in ("", "_wall")
        }
        self.assertEqual(public_item_ids, set(builder.PUBLIC_TROPHY_ITEM_IDS))
        self.assertEqual(
            block_ids, set(builder.INTERNAL_TROPHY_BLOCK_IDS)
        )

        server = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("trophy_block_for_face", server)
        self.assertIn('args["fullName"] = trophyBlock', server)
        trophy_block_section = server[server.index("TROPHY_BLOCKS = frozenset(") :]
        trophy_block_section = trophy_block_section[: trophy_block_section.index("\n)") + 2]
        for identifier in block_ids:
            self.assertIn('"%s"' % identifier, trophy_block_section)

        creative_source = (ROOT / "tools" / "build_creative_catalog.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("PUBLIC_TROPHY_IDS", creative_source)
        validator_source = (ROOT / "tools" / "validate_slice.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("PUBLIC_TROPHY_IDS", validator_source)
        self.assertIn("| PUBLIC_TROPHY_IDS", validator_source)

        catalog = json.loads(
            (
                BP / "item_catalog" / "crafting_item_catalog.json"
            ).read_text(encoding="utf-8")
        )
        catalog_ids = {
            identifier
            for category in catalog["minecraft:crafting_items_catalog"][
                "categories"
            ]
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        }
        self.assertTrue(public_item_ids.issubset(catalog_ids))
        self.assertFalse(
            {
                identifier
                for identifier in block_ids
                if "_wall_trophy" in identifier
            }
            & catalog_ids
        )

    def test_trophy_items_use_distinct_ids_and_collision_free_block_placer(self):
        self.assertTrue(hasattr(builder, "trophy_item_document"))
        for name in IN_SCOPE_TROPHIES:
            identifier = "tf_slice:%s_trophy" % name
            item_identifier = identifier + "_item"
            geometry = next(
                entry
                for entry in builder.trophy_geometry_document()["minecraft:geometry"]
                if entry["description"]["identifier"]
                == "geometry.tf_slice.%s_trophy" % name
            )
            block = builder.trophy_document(
                "%s_trophy" % name,
                "%s_trophy" % name,
                geometry["description"]["identifier"],
                geometry,
                wall=False,
            )
            self.assertNotIn(
                "minecraft:item_visual",
                block["minecraft:block"]["components"],
            )
            item = builder.trophy_item_document(name)["minecraft:item"]
            self.assertEqual(item_identifier, item["description"]["identifier"])
            self.assertEqual(
                item_identifier,
                item["components"]["minecraft:icon"]["textures"]["default"],
            )
            self.assertEqual(
                identifier,
                item["components"]["minecraft:block_placer"]["block"],
            )
            self.assertNotIn(
                "replace_block_item",
                item["components"]["minecraft:block_placer"],
            )
            self.assertEqual(
                item_identifier,
                builder.trophy_loot_document(name)["pools"][0]["entries"][0]["name"],
            )
    def test_generated_flat_trophy_items_match_builder(self):
        for name in IN_SCOPE_TROPHIES:
            generated = BP / "items" / (name + "_trophy.item.json")
            self.assertEqual(
                builder.trophy_item_document(name),
                json.loads(generated.read_text(encoding="utf-8")),
            )

    def test_server_uses_engine_placement_without_manual_duplicate_path(self):
        server = (BP / "TwilightBossSlice" / "serverSystem.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("def _try_place_trophy_item", server)
        self.assertNotIn("self._recent_trophy_item_placements = {}", server)
        handler = server[server.index("    def OnServerItemUseOnEvent") :]
        handler = handler[: handler.index("    def _activate_ghast_trap")]
        self.assertNotIn("self._try_place_trophy_item", handler)
        knight_source = (ROOT / "tools" / "build_knight_stronghold_content.py").read_text(
            encoding="utf-8"
        )
        dark_tower_source = (ROOT / "tools" / "build_dark_tower_content.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"knight_phantom_trophy": (1, None, None)', knight_source)
        self.assertNotIn('"ur_ghast_trophy": (64, False)', dark_tower_source)


if __name__ == "__main__":
    unittest.main()
