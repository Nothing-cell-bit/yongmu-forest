# -*- coding: utf-8 -*-
"""Player-visible contracts for the public Twilight block catalog."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"


WOOD_FAMILIES = ("dark", "mangrove")
SHAPED_SUFFIXES = (
    "banister",
)
DIRECTIONAL_SUFFIXES = {
    "stairs",
    "button",
    "fence_gate",
    "door",
    "trapdoor",
    "sign",
    "wall_sign",
    "hanging_sign",
    "wall_hanging_sign",
    "banister",
}
CONNECTION_SUFFIXES = {"fence", "banister"}
UPSTREAM_STATIC_ITEM_MODEL_SUFFIXES = set()
UPSTREAM_ITEM_ICON_MODEL_SUFFIXES = set()
VANILLA_ADAPTER_SUFFIXES = set(SHAPED_SUFFIXES)
HOLLOW_SUFFIXES = (
    "hollow_%s_log_horizontal",
    "hollow_%s_log_vertical",
    "hollow_%s_log_climbable",
)
TROPHY_VARIANTS = (
    "naga",
    "lich",
    "hydra",
    "ur_ghast",
    "knight_phantom",
    "minoshroom",
    "quest_ram",
)
TROPHIES = {
    "%s%s_trophy" % (variant, wall): "geometry.tf_slice.%s_trophy" % variant
    for variant in TROPHY_VARIANTS
    for wall in ("", "_wall")
}
HIDDEN_TECHNICAL_BLOCKS = {
    "knight_phantom_boss_spawner",
    "naga_boss_spawner",
    "ur_ghast_boss_spawner",
    "temporary_builder_block",
    "restored_block",
    "reactor_debris",
    "tower_key_door",
    "fake_gold",
    "fake_diamond",
}


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def block(name):
    return load(BP / "netease_blocks" / (name + ".json"))["minecraft:block"]


def geometry_identifiers():
    identifiers = set()
    for path in (RP / "models" / "blocks").glob("*.json"):
        document = load(path)
        for entry in document.get("minecraft:geometry", []):
            identifiers.add(entry["description"]["identifier"])
    return identifiers


def netease_model(identifier):
    path = RP / "models" / "netease_block" / (identifier + ".json")
    return load(path)["netease:block_geometry"]


def model_cubes(model):
    return [cube for bone in model.get("bones", []) for cube in bone.get("cubes", [])]


def expected_uv_size(cube, face):
    x_size, y_size, z_size = cube["size"]
    return {
        "north": [x_size, y_size],
        "south": [x_size, y_size],
        "east": [z_size, y_size],
        "west": [z_size, y_size],
        "up": [x_size, z_size],
        "down": [x_size, z_size],
    }[face]


class PublicBlockImplementationContractTests(unittest.TestCase):
    def test_netease_models_use_block_coordinates_item_icons_and_face_sized_uvs(self):
        atlas = load(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        for path in sorted(
            (RP / "models" / "netease_block").glob("tf_slice_public_*.json")
        ):
            model = load(path)["netease:block_geometry"]
            item_texture = model.get("description", {}).get("item_texture")
            name = path.stem.replace("tf_slice_public_", "")
            adapter_names = {
                "%s_%s" % (family, suffix)
                for family in WOOD_FAMILIES
                for suffix in SHAPED_SUFFIXES
            }
            upstream_static_names = {
                "%s_%s" % (family, suffix)
                for family in WOOD_FAMILIES
                for suffix in UPSTREAM_STATIC_ITEM_MODEL_SUFFIXES
            }
            self.assertIn(item_texture, atlas, path.name)
            item_path = atlas[item_texture]["textures"]
            item_file = RP / (item_path + ".png")
            self.assertTrue(item_file.is_file(), path.name)
            if name in upstream_static_names:
                serialized = json.dumps(model, ensure_ascii=False)
                self.assertNotIn("query.", serialized, path.name)
                self.assertTrue(model_cubes(model), path.name)
            if name not in adapter_names:
                icon = Image.open(item_file).convert("RGBA")
                self.assertEqual((64, 64), icon.size, name)
                opaque_colors = {
                    pixel[:3]
                    for pixel in icon.get_flattened_data()
                    if pixel[3]
                }
                self.assertGreaterEqual(
                    len(opaque_colors), 24, "%s item icon is flat" % name
                )
            for cube in model_cubes(model):
                origin = cube["origin"]
                size = cube["size"]
                if name not in upstream_static_names:
                    self.assertGreaterEqual(origin[0], 0, path.name)
                    self.assertLessEqual(origin[0] + size[0], 16, path.name)
                    self.assertGreaterEqual(origin[2], 0, path.name)
                    self.assertLessEqual(origin[2] + size[2], 16, path.name)
                for face, uv in cube.get("uv", {}).items():
                    expected = expected_uv_size(cube, face)
                    if uv.get("rotation", 0) in (90, 270):
                        expected = list(reversed(expected))
                    self.assertEqual(
                        expected,
                        [abs(value) for value in uv["uv_size"]],
                        "%s %s" % (path.name, face),
                    )

    def test_only_stateful_banisters_remain_as_custom_wood_shapes(self):
        from tools import build_creative_catalog as catalog_builder

        client_blocks = load(RP / "blocks.json")
        for identifier in catalog_builder.PUBLIC_WOOD_SHAPE_IDS:
            name = identifier.split(":", 1)[1]
            payload = block(name)
            self.assertEqual(24, len(payload["permutations"]), name)
            self.assertEqual(
                "tf_slice:%s_planks" % name.split("_", 1)[0],
                client_blocks[identifier]["textures"],
            )
        for identifier in catalog_builder.OBSOLETE_WOOD_BLOCK_IDS:
            self.assertNotIn(identifier, client_blocks)

    def test_item_icon_renderer_maps_each_face_to_its_declared_uv_region(self):
        from tools import build_public_block_shapes as builder

        self.assertEqual(
            [(64.0, 32.0), (192.0, 32.0), (192.0, 80.0), (64.0, 80.0)],
            builder._texture_quad_for_face(
                {"uv": [4, 2], "uv_size": [8, 3]},
                (16, 16),
                256,
            ),
        )
        renderer_source = (
            ROOT / "tools" / "build_public_block_shapes.py"
        ).read_text(encoding="utf-8")
        renderer_source = renderer_source[
            renderer_source.index("def _render_geometry_item_icon") :
            renderer_source.index("def twilight_item_icon_source")
        ]
        self.assertIn("_texture_quad_for_face", renderer_source)
        self.assertNotIn("ImageEnhance.Brightness", renderer_source)
        self.assertNotIn("draw.line", renderer_source)
        self.assertIn("Image.Resampling.NEAREST", renderer_source)

    def test_mangrove_stairs_convert_exact_upstream_java_elements_and_uvs(self):
        from tools import build_public_block_shapes as builder

        geometry = builder.java_item_model_geometry("mangrove_stairs")
        cubes = model_cubes(geometry)
        self.assertEqual(2, len(cubes))
        self.assertEqual([-8.0, 0.0, -8.0], cubes[0]["origin"])
        self.assertEqual([16.0, 8.0, 16.0], cubes[0]["size"])
        self.assertEqual([0, 8], cubes[0]["uv"]["south"]["uv"])
        self.assertEqual([16, 8], cubes[0]["uv"]["south"]["uv_size"])
        self.assertEqual([0.0, 8.0, -8.0], cubes[1]["origin"])
        self.assertEqual([8.0, 8.0, 16.0], cubes[1]["size"])
        self.assertEqual([8, 0], cubes[1]["uv"]["south"]["uv"])
        self.assertEqual([8, 8], cubes[1]["uv"]["south"]["uv_size"])
        self.assertNotIn("query.", json.dumps(geometry, ensure_ascii=False))

    def test_mangrove_stair_icon_resolves_original_java_item_model_chain(self):
        from tools import build_public_block_shapes as builder

        model = builder.resolve_java_wood_item_model("mangrove_stairs")
        self.assertEqual(
            [
                "twilightforest:item/mangrove_stairs",
                "twilightforest:block/wood/stairs/mangrove/mangrove_stairs",
                "minecraft:block/stairs",
                "minecraft:block/block",
            ],
            model["source_chain"],
        )
        self.assertEqual([30, 135, 0], model["display"]["gui"]["rotation"])
        self.assertEqual([0.625, 0.625, 0.625], model["display"]["gui"]["scale"])
        self.assertEqual(2, len(model["elements"]))
        self.assertEqual(
            [0, 8, 16, 16],
            model["elements"][0]["faces"]["south"]["uv"],
        )
        self.assertEqual(
            [8, 0, 16, 8],
            model["elements"][1]["faces"]["south"]["uv"],
        )
        self.assertEqual(
            "twilightforest:block/wood/planks_mangrove_0",
            model["resolved_textures"]["side"],
        )

    def test_java_item_renderer_keeps_models_on_one_gui_canvas(self):
        from tools import build_public_block_shapes as builder

        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            slab_path = directory / "slab.png"
            button_path = directory / "button.png"
            self.assertTrue(
                builder._render_java_item_model_icon(
                    "mangrove_slab", slab_path
                )
            )
            self.assertTrue(
                builder._render_java_item_model_icon(
                    "mangrove_button", button_path
                )
            )
            slab_box = Image.open(slab_path).getchannel("A").getbbox()
            button_box = Image.open(button_path).getchannel("A").getbbox()
            slab_width = slab_box[2] - slab_box[0]
            button_width = button_box[2] - button_box[0]
            self.assertLess(button_width, slab_width * 0.6)

    def test_java_item_renderer_uses_minecraft_directional_shades(self):
        from tools import build_public_block_shapes as builder

        self.assertEqual(1.0, builder._java_gui_face_shade("up", "side"))
        self.assertEqual(0.8, builder._java_gui_face_shade("south", "side"))
        self.assertEqual(0.6, builder._java_gui_face_shade("east", "side"))
        self.assertEqual(0.5, builder._java_gui_face_shade("down", "side"))
        self.assertEqual(1.0, builder._java_gui_face_shade("down", "front"))

    def test_java_gui_rotation_uses_quaternion_xyz_composition(self):
        from tools import build_public_block_shapes as builder

        rotated = builder._rotate_java_gui_point([1, 0, 0], [90, 90, 0])
        for actual, expected in zip(rotated, [0, 1, 0]):
            self.assertAlmostEqual(expected, actual, places=7)

    def test_java_gui_culling_shows_slab_top_and_rejects_underside(self):
        from tools import build_public_block_shapes as builder

        model = builder.resolve_java_wood_item_model("mangrove_slab")
        gui = model["display"]["gui"]
        element = model["elements"][0]

        def transformed(face_name):
            vertices = builder._java_element_face_vertices(
                element, face_name
            )
            result = []
            for point in vertices:
                centered = [
                    (point[index] - 8.0) * gui["scale"][index]
                    for index in range(3)
                ]
                result.append(
                    builder._rotate_java_gui_point(
                        centered, gui["rotation"]
                    )
                )
            return result

        self.assertTrue(builder._java_gui_face_is_visible(transformed("up")))
        self.assertFalse(
            builder._java_gui_face_is_visible(transformed("down"))
        )

    def test_mangrove_inventory_icons_are_upstream_model_renders(self):
        from tools import build_creative_catalog as catalog_builder

        for identifier in catalog_builder.OBSOLETE_WOOD_BLOCK_IDS:
            if not identifier.startswith("tf_slice:mangrove_"):
                continue
            name = identifier.split(":", 1)[1]
            self.assertFalse(
                (RP / "textures" / "blocks" / "item_icons" / (name + ".png")).exists()
            )

    def test_dark_shape_icons_are_rendered_from_dark_upstream_models(self):
        from tools import build_creative_catalog as catalog_builder

        for identifier in catalog_builder.OBSOLETE_WOOD_BLOCK_IDS:
            if not identifier.startswith("tf_slice:dark_"):
                continue
            name = identifier.split(":", 1)[1]
            self.assertFalse(
                (RP / "textures" / "blocks" / "item_icons" / (name + ".png")).exists()
            )

    def test_native_grid_aliases_bind_item_and_model_textures_in_blocks_json(self):
        from tools import build_public_block_shapes as builder

        client_blocks = load(RP / "blocks.json")
        for family, spec in builder.WOOD_FAMILIES.items():
            name = "%s_banister" % family
            self.assertEqual(
                {"textures": spec["planks"], "sound": "wood"},
                client_blocks["tf_slice:" + name],
                name,
            )

    def test_deprecated_icon_builder_cannot_recreate_removed_alias_icons(self):
        from tools import build_locked_wood_inventory_icons as icon_builder

        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual((), icon_builder.build(Path(directory)))
            self.assertEqual((), icon_builder.INVENTORY_ICON_SUFFIXES)

    def test_all_supported_wood_item_models_convert_without_queries(self):
        from tools import build_public_block_shapes as builder

        for family in WOOD_FAMILIES:
            for suffix in UPSTREAM_ITEM_ICON_MODEL_SUFFIXES:
                name = "%s_%s" % (family, suffix)
                geometry = builder.java_item_model_geometry(name)
                self.assertTrue(model_cubes(geometry), name)
                self.assertNotIn(
                    "query.", json.dumps(geometry, ensure_ascii=False), name
                )
                document = builder._netease_model_document(
                    name,
                    geometry,
                    ["tf_slice:%s_planks" % family],
                    None,
                )
                description = document["netease:block_geometry"][
                    "description"
                ]
                self.assertNotIn("item_texture", description, name)
        banister = builder._netease_model_document(
            "mangrove_banister",
            builder.java_item_model_geometry("mangrove_banister"),
            ["tf_slice:mangrove_planks"],
            None,
        )["netease:block_geometry"]
        rotated_faces = [
            face
            for cube in model_cubes(banister)
            for face in cube.get("uv", {}).values()
            if face.get("rotation") == 270
        ]
        self.assertEqual(8, len(rotated_faces))
        fence = builder._netease_model_document(
            "mangrove_fence",
            builder.java_item_model_geometry("mangrove_fence"),
            ["tf_slice:mangrove_planks"],
            None,
        )["netease:block_geometry"]
        fence_cubes = model_cubes(fence)
        self.assertTrue(
            any(cube["origin"][2] == -2 for cube in fence_cubes)
        )
        self.assertTrue(
            any(cube["origin"][2] + cube["size"][2] == 18 for cube in fence_cubes)
        )

    def test_java_item_model_converter_preserves_rotation_and_rejects_guesses(self):
        from tools import build_public_block_shapes as builder

        rotated = {
            "elements": [
                {
                    "from": [0, 0, 0],
                    "to": [4, 8, 4],
                    "rotation": {
                        "origin": [8, 8, 8],
                        "axis": "y",
                        "angle": 22.5,
                    },
                    "faces": {
                        "north": {
                            "uv": [0, 0, 4, 8],
                            "texture": "#texture",
                        }
                    },
                }
            ]
        }
        with mock.patch.object(
            builder, "resolve_java_wood_item_model", return_value=rotated
        ):
            cube = model_cubes(builder.java_item_model_geometry("fixture"))[0]
        self.assertEqual([0.0, 22.5, 0.0], cube["rotation"])
        self.assertEqual([0.0, 8.0, 0.0], cube["pivot"])

        invalid_models = (
            {
                "elements": [
                    {
                        "from": [0, 0, 0],
                        "to": [4, 8, 4],
                        "faces": {"north": {"texture": "#texture"}},
                    }
                ]
            },
            {
                "elements": [
                    {
                        "from": [0, 0, 0],
                        "to": [4, 8, 4],
                        "rotation": {
                            "origin": [8, 8, 8],
                            "axis": "y",
                            "angle": 22.5,
                            "rescale": True,
                        },
                        "faces": {
                            "north": {
                                "uv": [0, 0, 4, 8],
                                "texture": "#texture",
                            }
                        },
                    }
                ]
            },
            {"elements": []},
        )
        for model in invalid_models:
            with mock.patch.object(
                builder,
                "resolve_java_wood_item_model",
                return_value=model,
            ):
                with self.assertRaises(ValueError):
                    builder.java_item_model_geometry("fixture")

    def test_shape_builder_only_emits_stateful_banisters(self):
        from tools import build_public_block_shapes as builder

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            with mock.patch.object(builder, "BP", temporary / "BP"), mock.patch.object(
                builder, "RP", temporary / "RP"
            ), mock.patch.object(
                builder, "_ensure_item_icon", return_value="tf_slice:fixture"
            ):
                client_blocks = {}
                atlas = {}
                builder.build_shape_blocks(client_blocks, atlas)
                for family in WOOD_FAMILIES:
                    path = temporary / "BP" / "netease_blocks" / (
                        family + "_banister.json"
                    )
                    self.assertTrue(path.is_file())
                    self.assertEqual(
                        24,
                        len(load(path)["minecraft:block"]["permutations"]),
                    )
                    self.assertFalse(
                        (
                            temporary
                            / "BP"
                            / "netease_blocks"
                            / (family + "_stairs.json")
                        ).exists()
                    )

    def test_wood_item_model_textures_are_byte_exact_upstream_pngs(self):
        from tools import build_public_block_shapes as builder

        pairs = {
            "block/wood/planks_darkwood_0.png": "dark_planks.png",
            "block/wood/planks_mangrove_0.png": "mangrove_planks.png",
            "block/wood/trapdoor/darkwood_trapdoor.png": "dark_trapdoor.png",
            "block/wood/trapdoor/mangrove_trapdoor.png": "mangrove_trapdoor.png",
        }
        for upstream_name, bundled_name in pairs.items():
            upstream = builder.UPSTREAM_TEXTURES / upstream_name
            bundled = RP / "textures" / "blocks" / bundled_name
            self.assertEqual(
                hashlib.sha256(upstream.read_bytes()).hexdigest(),
                hashlib.sha256(bundled.read_bytes()).hexdigest(),
                bundled_name,
            )

    def test_generator_removes_deprecated_inventory_icons(self):
        source = (
            ROOT / "tools" / "build_public_block_shapes.py"
        ).read_text(encoding="utf-8")
        self.assertIn("remove_obsolete_wood_artifacts", source)

    def test_partial_blocks_have_geometry_matched_aabbs(self):
        for family in WOOD_FAMILIES:
            banister = block(family + "_banister")
            self.assertEqual(24, len(banister["permutations"]))
            self.assertIsInstance(
                banister["components"]["netease:aabb"]["collision"], list
            )
            for template in HOLLOW_SUFFIXES:
                hollow = block(template % family)["components"]["netease:aabb"]
                self.assertIsInstance(hollow["collision"], list)
                self.assertGreaterEqual(len(hollow["collision"]), 4)
                self.assertIsInstance(hollow["clip"], list)

    def test_nagastone_stair_states_select_real_geometry_and_aabbs(self):
        atlas = load(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        self.assertEqual(
            "textures/blocks/nagastone_top_tip",
            atlas["tf_slice:nagastone_top_tip"]["textures"],
        )
        self.assertTrue(
            (RP / "textures" / "blocks" / "nagastone_top_tip.png").is_file()
        )
        names = (
            "nagastone_stairs_left",
            "nagastone_stairs_right",
            "mossy_nagastone_stairs_left",
            "cracked_nagastone_stairs_left",
            "mossy_nagastone_stairs_right",
            "cracked_nagastone_stairs_right",
        )
        geometry_documents = [
            load(RP / "models" / "blocks" / "courtyard.geo.json"),
            load(RP / "models" / "blocks" / "courtyard_blocks.geo.json"),
        ]
        geometries = {
            entry["description"]["identifier"]: entry
            for document in geometry_documents
            for entry in document["minecraft:geometry"]
        }
        for name in names:
            value = block(name)
            encoded = json.dumps(value.get("permutations", []))
            for shape in (
                "straight",
                "inner_left",
                "inner_right",
                "outer_left",
                "outer_right",
            ):
                self.assertIn("tf_slice:shape", encoded, name)
                self.assertIn(shape, encoded, name)
            referenced = {
                permutation.get("components", {}).get("minecraft:geometry")
                for permutation in value.get("permutations", [])
                if permutation.get("components", {}).get("minecraft:geometry")
            }
            self.assertGreaterEqual(len(referenced), 10, name)
            for identifier in referenced:
                self.assertIn(identifier, geometries, name)
            collision = value["components"]["netease:aabb"]["collision"]
            self.assertIsInstance(collision, list, name)
        for identifier, geometry in geometries.items():
            if "stairs" not in identifier:
                continue
            for cube in model_cubes(geometry):
                for face, uv in cube.get("uv", {}).items():
                    self.assertEqual(
                        expected_uv_size(cube, face),
                        [abs(value) for value in uv["uv_size"]],
                        "%s %s" % (identifier, face),
                    )
    def test_public_block_generator_is_idempotent(self):
        from tools import build_public_block_shapes as builder

        self.assertEqual(
            {
                "woodFamilies": 2,
                "treeSaplings": 3,
                "trophies": 14,
                "geometryFiles": 5,
                "neteaseModels": 7,
            },
            builder.build(),
        )
        self.assertFalse(
            (RP / "models" / "blocks" / "public_wood_shapes.geo.json").exists()
        )
        paths = [
            RP / "models" / "blocks" / "public_trophies.geo.json",
            RP / "models" / "blocks" / "wood_sapling.geo.json",
            RP / "textures" / "terrain_texture.json",
            RP / "blocks.json",
        ]
        paths.extend(
            (RP / "models" / "netease_block").glob(
                "tf_slice_public_*.json"
            )
        )
        paths.extend(
            BP / "netease_blocks" / (name + ".json")
            for name in TROPHIES
        )
        before = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        }
        builder.build()
        after = {
            path: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        }
        self.assertEqual(before, after)

    def test_release_gate_rejects_public_block_placeholders(self):
        from tools import validate_slice

        gate = validate_slice.Gate()
        documents = validate_slice.collect_json(gate)
        validate_slice.validate_public_block_implementations(gate, documents)
        self.assertEqual([], gate.failures)
        source = (ROOT / "tools" / "validate_slice.py").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "validate_public_block_implementations(gate, documents)",
            source,
        )

    def test_release_tree_contains_no_deprecated_wood_shape_models(self):
        from tools import build_creative_catalog as catalog_builder

        for identifier in catalog_builder.OBSOLETE_WOOD_BLOCK_IDS:
            name = identifier.split(":", 1)[1]
            self.assertFalse(
                (
                    RP
                    / "models"
                    / "netease_block"
                    / ("tf_slice_public_%s.json" % name)
                ).exists()
            )

    def test_public_wood_base_blocks_are_modern_and_material_closed(self):
        atlas = load(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        names = {
            "dark_log",
            "dark_wood",
            "stripped_dark_log",
            "stripped_dark_wood",
            "dark_leaves",
            "hardened_dark_leaves",
            "darkwood_sapling",
            "dark_planks",
            "mangrove_log",
            "mangrove_wood",
            "stripped_mangrove_log",
            "stripped_mangrove_wood",
            "mangrove_leaves",
            "mangrove_sapling",
            "twilight_oak_sapling",
            "canopy_sapling",
            "rainbow_oak_sapling",
            "mangrove_root",
            "mangrove_planks",
        }
        for name in names:
            payload = load(BP / "netease_blocks" / (name + ".json"))
            self.assertEqual("1.20.60", payload["format_version"], name)
            components = payload["minecraft:block"]["components"]
            self.assertIn("minecraft:geometry", components, name)
            materials = components.get("minecraft:material_instances", {})
            self.assertTrue(materials, name)
            for material in materials.values():
                self.assertIn(material["texture"], atlas, name)
        for name in (
            "darkwood_sapling",
            "mangrove_sapling",
            "twilight_oak_sapling",
            "canopy_sapling",
            "rainbow_oak_sapling",
        ):
            self.assertEqual(
                "geometry.tf_slice.wood_sapling",
                block(name)["components"]["minecraft:geometry"],
                name,
            )
        self.assertNotIn(
            "mazestone",
            json.dumps(atlas["tf_slice:stripped_mangrove_wood"]),
        )

    def test_public_wood_saplings_ship_their_crossed_plane_geometry(self):
        geometry_path = RP / "models" / "blocks" / "wood_sapling.geo.json"
        document = load(geometry_path)
        entries = document["minecraft:geometry"]
        sapling = next(
            entry
            for entry in entries
            if entry["description"]["identifier"]
            == "geometry.tf_slice.wood_sapling"
        )
        self.assertEqual(
            {"cross_a", "cross_b"},
            {bone["name"] for bone in sapling["bones"]},
        )
        self.assertEqual(
            {-45, 45},
            {
                bone["cubes"][0]["rotation"][1]
                for bone in sapling["bones"]
            },
        )
        for name in (
            "darkwood_sapling",
            "mangrove_sapling",
            "twilight_oak_sapling",
            "canopy_sapling",
            "rainbow_oak_sapling",
        ):
            self.assertEqual(
                "geometry.tf_slice.wood_sapling",
                block(name)["components"]["minecraft:geometry"],
                name,
            )

    def test_release_gate_rejects_missing_public_sapling_geometry(self):
        from tools import validate_slice

        geometry_path = RP / "models" / "blocks" / "wood_sapling.geo.json"
        documents = validate_slice.collect_json(validate_slice.Gate())
        documents.pop(geometry_path, None)
        gate = validate_slice.Gate()
        validate_slice.validate_public_block_implementations(gate, documents)
        self.assertTrue(
            any(
                "saplings must ship geometry.tf_slice.wood_sapling"
                in failure
                for failure in gate.failures
            ),
            gate.failures,
        )

    def test_wood_shape_blocks_use_netease_models_and_native_components(self):
        client_blocks = load(RP / "blocks.json")
        for family in WOOD_FAMILIES:
            for suffix in SHAPED_SUFFIXES:
                name = "%s_%s" % (family, suffix)
                payload = load(
                    BP / "netease_blocks" / (name + ".json")
                )
                if suffix == "banister":
                    self.assertEqual("1.21.60", payload["format_version"], name)
                    value = payload["minecraft:block"]
                    self.assertEqual(24, len(value["permutations"]), name)
                    self.assertEqual(
                        "tf_slice:%s_planks" % family,
                        client_blocks["tf_slice:" + name]["textures"],
                    )
                    continue
                self.assertEqual("1.10.0", payload["format_version"], name)
                value = payload["minecraft:block"]
                components = value["components"]
                self.assertNotIn("minecraft:geometry", components, name)
                self.assertNotIn(
                    "minecraft:material_instances", components, name
                )
                self.assertNotIn("states", value["description"], name)
                self.assertNotIn("permutations", value, name)
                model_id = "tf_slice:public_%s" % name
                self.assertEqual(
                    model_id,
                    client_blocks["tf_slice:" + name]["netease_model"],
                    name,
                )
                model = netease_model("tf_slice_public_" + name)
                self.assertEqual(model_id, model["description"]["identifier"])
                self.assertTrue(model["bones"], name)
                if suffix in DIRECTIONAL_SUFFIXES:
                    self.assertEqual(
                        {"type": "direction"},
                        components.get("netease:face_directional"),
                        name,
                    )
                else:
                    self.assertNotIn("netease:face_directional", components, name)
                if suffix in CONNECTION_SUFFIXES:
                    connection = components.get("netease:connection", {})
                    self.assertIn("tf_slice:" + name, connection.get("blocks", []))
                    if suffix in UPSTREAM_STATIC_ITEM_MODEL_SUFFIXES:
                        self.assertNotIn(
                            "query.is_connect", json.dumps(model), name
                        )
                    else:
                        self.assertIn(
                            "query.is_connect", json.dumps(model), name
                        )
                if suffix == "chest":
                    self.assertEqual(
                        {
                            "chest_capacity": 3,
                            "can_pair": True,
                            "mute": False,
                            "can_be_blocked": True,
                        },
                        components.get("netease:block_chest"),
                        name,
                    )

    def test_hollow_logs_use_netease_models_without_fake_block_states(self):
        client_blocks = load(RP / "blocks.json")
        for family in WOOD_FAMILIES:
            for template in HOLLOW_SUFFIXES:
                name = template % family
                payload = load(
                    BP / "netease_blocks" / (name + ".json")
                )
                self.assertEqual("1.10.0", payload["format_version"], name)
                value = payload["minecraft:block"]
                components = value["components"]
                self.assertNotIn("minecraft:geometry", components, name)
                self.assertNotIn("states", value["description"], name)
                model_id = "tf_slice:public_%s" % name
                self.assertEqual(
                    model_id,
                    client_blocks["tf_slice:" + name]["netease_model"],
                )
                self.assertEqual(
                    model_id,
                    netease_model("tf_slice_public_" + name)["description"][
                        "identifier"
                    ],
                )
                self.assertFalse(
                    components["netease:solid"]["value"], name
                )
                if name.endswith(("horizontal", "climbable")):
                    self.assertEqual(
                        {"type": "direction"},
                        components.get("netease:face_directional"),
                    )

    def test_canopy_fence_reuses_the_native_cherry_template(self):
        client_blocks = load(RP / "blocks.json")
        self.assertFalse(
            (BP / "netease_blocks" / "canopy_fence.json").exists()
        )
        self.assertEqual(
            {"textures": "tf_slice:canopy_planks", "sound": "wood"},
            client_blocks["cherry_fence"],
        )
        self.assertNotIn("tf_slice:canopy_fence", client_blocks)
        self.assertFalse(
            (
                RP
                / "models"
                / "netease_block"
                / "tf_slice_public_canopy_fence.json"
            ).exists()
        )
        recipe = load(BP / "recipes" / "canopy_fence.recipe.json")[
            "minecraft:recipe_shaped"
        ]
        self.assertEqual(
            "minecraft:cherry_fence", recipe["result"]["item"]
        )

    def test_trophies_use_source_head_geometry_and_model_textures(self):
        atlas = load(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        known_geometry = geometry_identifiers()
        for name, expected_geometry in TROPHIES.items():
            payload = load(BP / "netease_blocks" / (name + ".json"))
            self.assertEqual("1.20.60", payload["format_version"], name)
            value = payload["minecraft:block"]
            components = value["components"]
            self.assertEqual(
                expected_geometry, components.get("minecraft:geometry"), name
            )
            self.assertIn(expected_geometry, known_geometry, name)
            texture = components["minecraft:material_instances"]["*"][
                "texture"
            ]
            model_name = name.replace("_wall_trophy", "_trophy")
            self.assertEqual("tf_slice:%s_model" % model_name, texture)
            self.assertIn(texture, atlas, name)
            self.assertNotIn(
                "mazestone", json.dumps(atlas[texture]), name
            )
            self.assertFalse(components["netease:solid"]["value"], name)

            collision = components["netease:aabb"]["collision"]
            self.assertNotEqual(
                {"min": [0.125, 0, 0.125], "max": [0.875, 0.875, 0.875]},
                collision,
                name,
            )
            for permutation in value.get("permutations", []):
                self.assertIn(
                    "netease:aabb",
                    permutation.get("components", {}),
                    name,
                )

        server_source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn("_orient_placed_trophy", server_source)
        self.assertIn('states["tf_slice:facing"]', server_source)

    def test_fire_swamp_devices_have_face_and_state_complete_materials(self):
        atlas = load(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        for name in ("smoker", "fire_jet", "encased_smoker", "encased_fire_jet"):
            value = block(name)
            components = value["components"]
            self.assertEqual(
                "geometry.tf_slice.courtyard_cube",
                components.get("minecraft:geometry"),
                name,
            )
            materials = components.get("minecraft:material_instances", {})
            for face in ("side", "top", "bottom"):
                self.assertIn(face, materials, name)
                self.assertIn(materials[face]["texture"], atlas, name)
            encoded = json.dumps(value.get("permutations", []))
            if name == "encased_smoker":
                self.assertIn("tf_slice:active", encoded)
                self.assertIn("encased_smoker_side_on", encoded)
            if name == "encased_fire_jet":
                self.assertIn("tf_slice:jet_state", encoded)
                self.assertIn("encased_fire_jet_side_on", encoded)

        for key in (
            "encased_smoker_side_off",
            "encased_smoker_side_on",
            "encased_smoker_top_off",
            "encased_smoker_top_on",
            "encased_fire_jet_side_off",
            "encased_fire_jet_side_on",
            "encased_fire_jet_top_off",
            "encased_fire_jet_top_on",
        ):
            texture_path = atlas["tf_slice:" + key]["textures"]
            self.assertTrue((RP / (texture_path + ".png")).is_file(), key)

    def test_technical_runtime_blocks_are_hidden_from_creative(self):
        catalog = load(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )
        catalog_text = json.dumps(catalog)
        for name in HIDDEN_TECHNICAL_BLOCKS:
            description = block(name)["description"]
            self.assertFalse(
                description.get("register_to_creative_menu", True), name
            )
            self.assertNotIn("tf_slice:" + name, catalog_text, name)

    def test_huge_lily_pad_is_one_runtime_safe_public_block(self):
        public = block("huge_lily_pad")
        self.assertEqual(
            "geometry.tf_slice.huge_lily_pad_item",
            public["components"]["minecraft:geometry"],
        )
        bounds = public["components"]["netease:aabb"]
        self.assertEqual([0.0, 0.0, 0.0], bounds["collision"]["min"])
        self.assertEqual([1.875, 0.0625, 1.875], bounds["collision"]["max"])
        for quadrant in ("nw", "ne", "se", "sw"):
            value = block("huge_lily_pad_" + quadrant)
            self.assertFalse(
                value["description"]["register_to_creative_menu"]
            )
            collision = value["components"]["netease:aabb"]["collision"]
            self.assertEqual([0.0, 0.0, 0.0], collision["min"])
            self.assertEqual([1.0, 0.0625, 1.0], collision["max"])
        server_source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn("if blockName == HUGE_LILY_PAD_BLOCK:", server_source)
        self.assertIn(
            "_huge_lily_single_footprint_is_available",
            server_source,
        )
        self.assertNotIn(
            "placed = self._place_huge_lily_pad(",
            server_source,
        )
        self.assertIn("_break_huge_lily_pad", server_source)

    def test_reactor_debris_uses_a_bundled_texture(self):
        atlas = load(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        self.assertEqual(
            "textures/blocks/reactor_debris",
            atlas["tf_slice:reactor_debris"]["textures"],
        )
        self.assertTrue(
            (RP / "textures" / "blocks" / "reactor_debris.png").is_file()
        )

    def test_vanilla_behavior_adapters_keep_twilight_wood_textures(self):
        from tools import build_public_block_shapes as builder

        client_blocks = load(RP / "blocks.json")
        atlas = load(RP / "textures" / "terrain_texture.json")[
            "texture_data"
        ]
        expected = {
            "dark_oak_planks": "textures/blocks/dark_planks",
            "wood_big_oak": "textures/blocks/dark_planks",
            "darkoak_sign": "textures/blocks/dark_planks",
            "dark_oak_trapdoor": "textures/blocks/dark_trapdoor",
            "mangrove_planks": "textures/blocks/mangrove_planks",
            "mangrove_sign": "textures/blocks/mangrove_planks",
            "mangrove_trapdoor": "textures/blocks/mangrove_trapdoor",
            "mangrove_door_bottom": "textures/blocks/mangrove_door_lower",
            "mangrove_door_top": "textures/blocks/mangrove_door_upper",
        }
        for key, path in expected.items():
            self.assertEqual(path, atlas[key]["textures"], key)
            self.assertTrue((RP / (path + ".png")).is_file(), key)
        self.assertEqual(
            "dark_oak_trapdoor",
            client_blocks["dark_oak_trapdoor"]["textures"],
        )
        self.assertEqual(
            "mangrove_trapdoor",
            client_blocks["mangrove_trapdoor"]["textures"],
        )
        self.assertEqual(
            "textures/blocks/dark_door_lower",
            atlas["door_lower"]["textures"][5],
        )
        self.assertEqual(
            "textures/blocks/dark_door_upper",
            atlas["door_upper"]["textures"][5],
        )
        self.assertEqual(
            "textures/blocks/dark_door_lower",
            atlas["tf_slice:dark_door_lower"]["textures"],
        )
        self.assertEqual(
            "textures/blocks/mangrove_door_upper",
            atlas["tf_slice:mangrove_door_upper"]["textures"],
        )
        source_pairs = {
            "textures/blocks/dark_planks.png": (
                "block/wood/planks_darkwood_0.png"
            ),
            "textures/blocks/mangrove_planks.png": (
                "block/wood/planks_mangrove_0.png"
            ),
            "textures/blocks/dark_trapdoor.png": (
                "block/wood/trapdoor/darkwood_trapdoor.png"
            ),
            "textures/blocks/mangrove_trapdoor.png": (
                "block/wood/trapdoor/mangrove_trapdoor.png"
            ),
        }
        for target_name, source_name in source_pairs.items():
            target = RP / target_name
            source = builder.UPSTREAM_TEXTURES / source_name
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(),
                hashlib.sha256(target.read_bytes()).hexdigest(),
                target_name,
            )

    def test_vanilla_adapter_blocks_bind_namespaced_twilight_materials(self):
        from tools import build_public_block_shapes as builder

        client_blocks = {}
        builder.ensure_vanilla_adapter_client_blocks(client_blocks)
        for family, texture in (
            ("dark_oak", "tf_slice:dark_planks"),
            ("mangrove", "tf_slice:mangrove_planks"),
        ):
            for suffix in (
                "stairs",
                "slab",
                "button",
                "fence",
                "fence_gate",
                "pressure_plate",
                "sign",
                "wall_sign",
                "hanging_sign",
                "wall_hanging_sign",
            ):
                self.assertEqual(
                    texture,
                    client_blocks["%s_%s" % (family, suffix)]["textures"],
                    "%s_%s" % (family, suffix),
                )
            self.assertEqual(
                "%s_trapdoor" % family,
                client_blocks["%s_trapdoor" % family]["textures"],
            )
            door_prefix = "dark" if family == "dark_oak" else "mangrove"
            self.assertEqual(
                {
                    "up": "tf_slice:%s_door_lower" % door_prefix,
                    "down": "tf_slice:%s_door_lower" % door_prefix,
                    "side": "tf_slice:%s_door_upper" % door_prefix,
                },
                client_blocks["%s_door" % family]["textures"],
            )

    def test_vanilla_adapter_items_use_upstream_twilight_icons(self):
        from tools import build_public_block_shapes as builder

        atlas = load(RP / "textures" / "item_texture.json")[
            "texture_data"
        ]
        expected = {
            "dark_oak_door": ("dark_door", "item/dark_door.png"),
            "sign_darkoak": ("dark_sign", "item/dark_sign.png"),
            "sign_darkoak_hanging": (
                "dark_hanging_sign",
                "item/dark_hanging_sign.png",
            ),
            "mangrove_door": (
                "mangrove_door",
                "item/mangrove_door.png",
            ),
            "mangrove_sign": (
                "mangrove_sign",
                "item/mangrove_sign.png",
            ),
            "sign_mangrove_hanging": (
                "mangrove_hanging_sign",
                "item/mangrove_hanging_sign.png",
            ),
        }
        for key, (target_name, source_name) in expected.items():
            target_path = "textures/items/%s" % target_name
            self.assertEqual(target_path, atlas[key]["textures"], key)
            target = RP / (target_path + ".png")
            source = builder.UPSTREAM_TEXTURES / source_name
            self.assertEqual(
                hashlib.sha256(source.read_bytes()).hexdigest(),
                hashlib.sha256(target.read_bytes()).hexdigest(),
                key,
            )

    def test_public_wood_shapes_keep_vanilla_function_adapters(self):
        from TwilightBossSlice import vanilla_block_adapter_logic

        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"ServerEntityTryPlaceBlockEvent"', source)
        self.assertNotIn('"ServerBlockTryPlaceByPlayerEvent"', source)
        for family in WOOD_FAMILIES:
            for suffix in SHAPED_SUFFIXES:
                if suffix == "banister":
                    self.assertNotIn(
                        "tf_slice:%s_%s" % (family, suffix),
                        vanilla_block_adapter_logic.VANILLA_BLOCK_ADAPTERS,
                    )
                    continue
                vanilla_family = (
                    "mangrove" if family == "mangrove" else "dark_oak"
                )
                target_suffix = suffix
                target = (
                    "minecraft:chest"
                    if suffix == "chest"
                    else "minecraft:%s_sign" % vanilla_family
                    if suffix == "wall_sign"
                    else "minecraft:%s_hanging_sign" % vanilla_family
                    if suffix == "wall_hanging_sign"
                    else "minecraft:%s_%s"
                    % (vanilla_family, target_suffix)
                )
                self.assertEqual(
                    target,
                    vanilla_block_adapter_logic.VANILLA_BLOCK_ADAPTERS[
                        "tf_slice:%s_%s" % (family, suffix)
                    ],
                )
                self.assertIn(
                    "vanilla_block_adapter_logic.adapt_placement_event(args)",
                    source,
                )


if __name__ == "__main__":
    unittest.main()
