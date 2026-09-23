import json
import math
import pathlib
import random
import subprocess
import sys
import unittest

from tools import build_ruin_structures as structure_builder
from tools import validate_slice as release_validator


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
CATALOG_PATH = BP / "structures" / "tf_slice" / "ruins" / "structure_catalog_v1.json"
CURRENT_NETEASE_BLOCK_VERSION = 0x01153C21

SMALL_RARITIES = {
    "monolith": 90,
    "stone_circle": 105,
    "well": 80,
    "foundation": 90,
    "druid_hut": 105,
    "outside_stalagmite": 77,
    "hollow_stump": 80,
    "fallen_hollow_log": 85,
    "grove_ruins": 110,
}
SMALL_VERTICAL_OFFSETS = {
    "well": -20,
    "druid_hut": -12,
    "foundation": -2,
    "hollow_stump": -9,
}
NATIVE_VERTICAL_OFFSETS = dict(SMALL_VERTICAL_OFFSETS, graveyard=-2)

EXPECTED_IDS = set(SMALL_RARITIES) | {
    "leaf_dungeon",
    "graveyard",
    "hedge_maze",
    "naga_courtyard",
    "mushroom_tower",
    "hollow_hill",
    "quest_grove",
    "lich_tower",
    "labyrinth",
    "hydra_lair",
    "knight_stronghold",
    "dark_tower",
}
RUIN_MOBS = {
    "raven",
    "skeleton_druid",
    "swarm_spider",
    "hedge_spider",
    "hostile_wolf",
    "wraith",
    "rising_zombie",
    "redcap",
    "redcap_sapper",
    "kobold",
    "slime_beetle",
    "fire_beetle",
    "pinch_beetle",
}
RUIN_LOOT_TABLES = {
    "well",
    "foundation_basement",
    "druid_hut",
    "tree_cache",
    "graveyard",
    "hedge_maze",
    "hollow_hill_small",
    "hollow_hill_medium",
    "hollow_hill_large",
}


def load_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_mcstructure_palette(path):
    from tools import validate_slice

    return validate_slice._read_mcstructure_palette(path)


def catalog_structure_path(catalog, reference):
    resolved = structure_builder.resolve_ruin_structure_reference(
        reference,
        catalog.get("structureAliases", {}),
    )
    return BP / "structures" / (resolved + ".mcstructure")


class RuinCatalogContractTests(unittest.TestCase):
    def setUp(self):
        self.catalog = load_json(CATALOG_PATH)
        self.entries = {
            entry["id"]: entry for entry in self.catalog["structures"]
        }

    def test_catalog_is_closed_over_the_4_3_2508_ruin_set(self):
        self.assertEqual(self.catalog["sourceVersion"], "4.3.2508")
        self.assertEqual(set(self.entries), EXPECTED_IDS)
        self.assertNotIn("camp", self.entries)

    def test_structure_builder_rejects_a_parallel_process(self):
        child_script = (
            "import tools.build_ruin_structures as b; "
            "c=b._exclusive_build_lock(); c.__enter__()"
        )
        with structure_builder._exclusive_build_lock():
            child = subprocess.run(
                [sys.executable, "-c", child_script],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(child.returncode, 0)
        self.assertIn(
            "another ruin structure build is already running",
            child.stdout + child.stderr,
        )

    def test_small_ruins_keep_upstream_chunk_rarities(self):
        for ruin_id, denominator in SMALL_RARITIES.items():
            entry = self.entries[ruin_id]
            self.assertEqual(entry["strategy"], "native_feature")
            self.assertEqual(entry["rarity"], {"numerator": 1, "denominator": denominator})
            self.assertEqual(
                entry["biomeTags"],
                ["dm33027004", "tf_slice_small_ruins"],
            )

    def test_version_specific_corrections_are_encoded(self):
        for variant in self.entries["monolith"]["variants"]:
            monolith_path = BP / "structures" / (
                variant["pieces"][0]["structure"] + ".mcstructure"
            )
            self.assertEqual(
                monolith_path.read_bytes().count(b"tf_slice:raven"),
                2,
            )

        fallen = self.entries["fallen_hollow_log"]
        self.assertEqual(fallen["postProcessors"], [])
        self.assertNotIn("chest", json.dumps(fallen))
        self.assertNotIn("spawner", json.dumps(fallen))

        stalagmite = self.entries["outside_stalagmite"]
        self.assertEqual(stalagmite["palette"], ["minecraft:stone"])

        leaf = self.entries["leaf_dungeon"]
        self.assertEqual(leaf["strategy"], "hollow_tree_attachment")
        self.assertEqual(leaf["attachmentChance"], {"numerator": 1, "denominator": 8})
        self.assertEqual(leaf["parentRarity"], {"numerator": 1, "denominator": 35})
        dungeon_variants = 0
        for variant in leaf["variants"]:
            data = b"".join(
                (
                    BP / "structures" / (piece["structure"] + ".mcstructure")
                ).read_bytes()
                for piece in variant["pieces"]
            )
            if b"tf_slice:swarm_spider" in data:
                dungeon_variants += 1
        self.assertEqual(dungeon_variants, 1)

    def test_hollow_hills_have_size_specific_speleothems_and_resources(self):
        small = structure_builder.hollow_hill(
            36,
            structure_builder.HOLLOW_HILL_VARIANT_SEEDS[36],
        )
        medium = structure_builder.hollow_hill(
            68,
            structure_builder.HOLLOW_HILL_VARIANT_SEEDS[68],
        )
        large = structure_builder.hollow_hill(
            100,
            structure_builder.HOLLOW_HILL_VARIANT_SEEDS[100],
        )

        small_blocks = {block[0] for block in small.blocks.values()}
        medium_blocks = {block[0] for block in medium.blocks.values()}
        large_blocks = {block[0] for block in large.blocks.values()}

        self.assertIn("minecraft:glowstone", small_blocks)
        self.assertIn("minecraft:raw_copper_block", small_blocks)
        self.assertIn("minecraft:raw_iron_block", small_blocks)
        self.assertNotIn("minecraft:gold_ore", small_blocks)
        self.assertIn("minecraft:gold_ore", medium_blocks)
        self.assertIn("minecraft:redstone_ore", medium_blocks)
        self.assertNotIn("minecraft:diamond_ore", medium_blocks)
        self.assertIn("minecraft:diamond_ore", large_blocks)
        self.assertIn("minecraft:emerald_ore", large_blocks)
        self.assertIn("minecraft:lapis_ore", large_blocks)
        for structure in (small, medium, large):
            blocks = {block[0] for block in structure.blocks.values()}
            self.assertIn("minecraft:cobblestone", blocks)
            self.assertIn("minecraft:chest", blocks)
            self.assertIn("minecraft:mob_spawner", blocks)

    def test_hollow_hill_ore_spikes_are_volumetric_not_single_block_lines(self):
        hill = structure_builder.hollow_hill(
            68,
            structure_builder.HOLLOW_HILL_VARIANT_SEEDS[68],
        )
        ore_positions = {
            position
            for position, block in hill.blocks.items()
            if block[0].endswith("_ore")
        }
        horizontal_neighbors = 0
        for x, y, z in ore_positions:
            if (
                (x + 1, y, z) in ore_positions
                or (x - 1, y, z) in ore_positions
                or (x, y, z + 1) in ore_positions
                or (x, y, z - 1) in ore_positions
            ):
                horizontal_neighbors += 1
        self.assertGreater(horizontal_neighbors, 500)

    def test_hedge_maze_uses_upstream_hedge_roots_and_lights(self):
        maze = structure_builder.hedge_maze(0)
        block_names = {block[0] for block in maze.blocks.values()}

        self.assertIn("tf_slice:hedge", block_names)
        self.assertIn("tf_slice:mazestone", block_names)
        self.assertIn("tf_slice:firefly", block_names)
        self.assertNotIn("minecraft:oak_leaves", block_names)

        facing_offsets = {
            "north": (0, 0, -1),
            "south": (0, 0, 1),
            "west": (-1, 0, 0),
            "east": (1, 0, 0),
        }
        fireflies = 0
        for position, block in maze.blocks.items():
            if block[0] != "tf_slice:firefly":
                continue
            fireflies += 1
            offset = facing_offsets[block[1]["tf_slice:facing"]]
            # Hedge-maze lights use the state to select the visible mount
            # face, so it points from the firefly block back to its hedge.
            # Generic tree and mushroom decorators retain their existing
            # support-to-firefly convention and shared block model.
            support = (
                position[0] + offset[0],
                position[1] + offset[1],
                position[2] + offset[2],
            )
            self.assertEqual("tf_slice:hedge", maze.blocks[support][0])
        self.assertEqual(24, fireflies)

    def test_hedge_maze_variants_have_four_connected_two_block_exits(self):
        passable_blocks = {"minecraft:air", "tf_slice:firefly"}
        entrance_columns = (
            ((26, 27), range(0, 4)),
            ((26, 27), range(47, 50)),
        )
        entrance_rows = (
            (range(0, 4), (26, 27)),
            (range(47, 50), (26, 27)),
        )
        entrance_floor = (
            ((26, 27), (1, 49)),
            ((1, 49), (26, 27)),
        )

        for seed in range(structure_builder.HEDGE_MAZE_VARIANT_COUNT):
            maze = structure_builder.hedge_maze(seed)
            for xs, zs in entrance_columns:
                for x in xs:
                    for z in zs:
                        for y in range(1, 4):
                            with self.subTest(seed=seed, x=x, y=y, z=z):
                                block = maze.blocks.get(
                                    (x, y, z),
                                    ("minecraft:air",),
                                )[0]
                                self.assertIn(block, passable_blocks)
            for xs, zs in entrance_floor:
                for x in xs:
                    for z in zs:
                        with self.subTest(seed=seed, x=x, y=0, z=z):
                            self.assertEqual(
                                "minecraft:grass_block",
                                maze.blocks[(x, 0, z)][0],
                            )
            for xs, zs in entrance_rows:
                for x in xs:
                    for z in zs:
                        for y in range(1, 4):
                            with self.subTest(seed=seed, x=x, y=y, z=z):
                                block = maze.blocks.get(
                                    (x, y, z),
                                    ("minecraft:air",),
                                )[0]
                                self.assertIn(block, passable_blocks)

    def test_hollow_hill_layers_carve_before_placing_interior_features(self):
        for diameter in (36, 68, 100):
            shell, interior = structure_builder.hollow_hill(
                diameter,
                structure_builder.HOLLOW_HILL_VARIANT_SEEDS[diameter],
                split_layers=True,
            )
            shell_blocks = {block[0] for block in shell.blocks.values()}
            interior_blocks = {
                block[0] for block in interior.blocks.values()
            }
            self.assertNotIn("minecraft:air", shell_blocks)
            self.assertNotIn("minecraft:air", interior_blocks)
            self.assertTrue(
                any(name.endswith("_ore") for name in interior_blocks)
            )
            self.assertIn("minecraft:stone", interior_blocks)
            self.assertIn("minecraft:chest", interior_blocks)
            self.assertIn("minecraft:mob_spawner", interior_blocks)

    def test_surface_native_hollow_hills_include_a_buried_dome(self):
        kinds = {
            36: ("small_hill", 6),
            68: ("medium_hill", 8),
            100: ("large_hill", 10),
        }
        for diameter, (kind, minimum_roof) in kinds.items():
            terrain_seed = structure_builder.HOLLOW_HILL_TERRAIN_SEEDS[
                diameter
            ]
            shell, interior = structure_builder.hollow_hill(
                diameter,
                structure_builder.HOLLOW_HILL_VARIANT_SEEDS[diameter],
                split_layers=True,
                terrain_seed=terrain_seed,
            )
            combined = structure_builder.SparseStructure(shell.size, kind)
            combined.merge(shell)
            combined.merge(interior)
            envelope = structure_builder._surface_native_envelope(
                combined,
                kind,
                terrain_seed,
            )

            terrain_surface = {
                (x, z): y
                for (x, y, z), block in envelope.blocks.items()
                if block[0]
                in ("minecraft:grass_block", "minecraft:moss_block")
            }
            terrain_diameter = structure_builder.ruin_logic.HOLLOW_HILL_KIND_DATA[
                kind
            ][2]
            terrain_radius = terrain_diameter / 2.0
            center = (terrain_diameter - 1) / 2.0
            margin = structure_builder.SURFACE_NATIVE_EDGE_BLEND_WIDTH
            rim_heights = []
            for x in range(terrain_diameter):
                for z in range(terrain_diameter):
                    distance = math.sqrt(
                        (x - center) ** 2 + (z - center) ** 2
                    )
                    if distance > terrain_radius:
                        continue
                    if not any(
                        math.sqrt(
                            (neighbor_x - center) ** 2
                            + (neighbor_z - center) ** 2
                        )
                        > terrain_radius
                        for neighbor_x, neighbor_z in (
                            (x - 1, z),
                            (x + 1, z),
                            (x, z - 1),
                            (x, z + 1),
                        )
                    ):
                        continue
                    rim_heights.append(
                        terrain_surface[(x + margin, z + margin)]
                    )
            resources = [
                (x, y, z)
                for (x, y, z), block in envelope.blocks.items()
                if block[0].endswith("_ore")
                or block[0]
                in (
                    "minecraft:glowstone",
                    "minecraft:raw_copper_block",
                    "minecraft:raw_iron_block",
                )
            ]
            roof_gaps = [
                terrain_surface[(x, z)] - y
                for x, y, z in resources
                if (x, z) in terrain_surface
            ]
            self.assertTrue(terrain_surface, kind)
            self.assertTrue(rim_heights, kind)
            self.assertEqual(
                {structure_builder.SURFACE_NATIVE_GROUND_Y},
                set(rim_heights),
                kind,
            )
            self.assertTrue(resources, kind)
            self.assertIn(
                "minecraft:air",
                {block[0] for block in envelope.blocks.values()},
            )
            self.assertGreaterEqual(min(roof_gaps), minimum_roof, kind)

    def test_surface_native_large_hill_keeps_cavity_sparse_and_under_budget(self):
        diameter = 100
        terrain_seed = structure_builder.HOLLOW_HILL_TERRAIN_SEEDS[
            diameter
        ]
        shell, _unused = structure_builder.hollow_hill(
            diameter,
            structure_builder.HOLLOW_HILL_CONTENT_SEEDS[diameter][0],
            split_layers=True,
            terrain_seed=terrain_seed,
        )
        _unused, interior = structure_builder.hollow_hill(
            diameter,
            structure_builder.HOLLOW_HILL_CONTENT_SEEDS[diameter][6],
            split_layers=True,
            terrain_seed=terrain_seed,
        )
        combined = structure_builder.SparseStructure(
            shell.size,
            "large_hill_v06_budget",
        )
        combined.merge(shell)
        combined.merge(interior)

        envelope = structure_builder._surface_native_envelope(
            combined,
            "large_hill",
            terrain_seed,
        )
        margin = structure_builder.SURFACE_NATIVE_WORLDGEN_MARGIN
        center_x = margin + combined.size[0] // 2
        center_z = margin + combined.size[2] // 2

        self.assertEqual(
            "minecraft:air",
            envelope.blocks[(center_x, 5, center_z)][0],
            "native terrain below the shared ground still needs an explicit cave carve",
        )
        self.assertNotIn(
            (center_x, structure_builder.SURFACE_NATIVE_GROUND_Y, center_z),
            envelope.blocks,
            "pre-vegetation air above the shared ground must stay sparse instead of being refilled",
        )
        self.assertNotIn(
            (center_x, 0, center_z),
            envelope.blocks,
            "native terrain below the authored cave floor must not be serialized as a deep stone column",
        )
        self.assertLessEqual(
            len(envelope.blocks),
            310000,
            "one landmark region is expanded synchronously and needs a hard native-worldgen budget",
        )

    def test_surface_native_landmarks_bake_a_surface_pass_beard_transition(self):
        structure = structure_builder.SparseStructure(
            (16, 6, 16),
            "low_landmark",
        )
        structure.set(0, 0, 0, "minecraft:diamond_block")
        structure.set(1, 0, 1, "minecraft:grass_block")

        envelope = structure_builder._surface_native_envelope(
            structure,
            "hedge_maze",
        )

        margin = 24
        terrain_clearance = (
            structure_builder.SURFACE_NATIVE_TRANSITION_MAX_DEVIATION
        )
        self.assertEqual(
            margin,
            structure_builder.SURFACE_NATIVE_WORLDGEN_MARGIN,
        )
        self.assertEqual(16 + margin * 2, envelope.size[0])
        self.assertEqual(16 + margin * 2, envelope.size[2])
        self.assertEqual(
            envelope.size[1],
            structure_builder.SURFACE_NATIVE_GROUND_Y
            + terrain_clearance
            + 1,
        )
        self.assertEqual(
            "minecraft:diamond_block",
            envelope.blocks[
                (
                    margin,
                    structure_builder.SURFACE_NATIVE_GROUND_Y,
                    margin,
                )
            ][0],
        )
        self.assertEqual(
            "minecraft:air",
            envelope.blocks[
                (
                    margin,
                    structure_builder.SURFACE_NATIVE_GROUND_Y
                    + terrain_clearance,
                    margin,
                )
            ][0],
        )
        self.assertEqual(
            structure_builder.LANDMARK_PROTECTED_GRASS_BLOCK,
            envelope.blocks[
                (
                    margin + 1,
                    structure_builder.SURFACE_NATIVE_GROUND_Y,
                    margin + 1,
                )
            ][0],
        )
        center_z = margin + structure.size[2] // 2
        inner_ring_y = max(
            y
            for (x, y, z), block in envelope.blocks.items()
            if x == margin - 1
            and z == center_z
            and block[0]
            in structure_builder.SURFACE_NATIVE_GRASS_BLOCKS
            | {structure_builder.LANDMARK_PROTECTED_GRASS_BLOCK}
        )
        middle_ring_y = max(
            y
            for (x, y, z), block in envelope.blocks.items()
            if x == margin // 2
            and z == center_z
            and block[0]
            in structure_builder.SURFACE_NATIVE_GRASS_BLOCKS
            | {structure_builder.LANDMARK_PROTECTED_GRASS_BLOCK}
        )
        self.assertGreater(inner_ring_y, middle_ring_y)
        self.assertLessEqual(
            inner_ring_y,
            structure_builder.SURFACE_NATIVE_GROUND_Y,
        )
        transition_seed = structure_builder._surface_environment_seed(
            "hedge_maze",
            "terrain_transition",
            0,
        )
        middle_deviation = (
            structure_builder._surface_native_transition_deviation_field(
                structure,
                margin,
                None,
                transition_seed,
            )[(margin // 2, center_z)]
        )
        self.assertNotIn(
            (
                margin // 2,
                structure_builder.SURFACE_NATIVE_GROUND_Y
                + middle_deviation,
                center_z,
            ),
            envelope.blocks,
            "middle transition band must preserve nearby native terrain",
        )
        self.assertEqual(
            "minecraft:air",
            envelope.blocks[
                (
                    margin // 2,
                    structure_builder.SURFACE_NATIVE_GROUND_Y
                    + middle_deviation
                    + 1,
                    center_z,
                )
            ][0],
        )
        self.assertFalse(
            any(x == 0 and z == center_z for x, _y, z in envelope.blocks),
            "outer transition boundary must leave native terrain untouched",
        )
        self.assertNotIn(
            "minecraft:moss_block",
            {block[0] for block in envelope.blocks.values()},
        )

    def test_surface_beard_profile_never_jumps_more_than_one_block(self):
        width = structure_builder.SURFACE_NATIVE_WORLDGEN_MARGIN
        deviations = [
            structure_builder._surface_native_transition_deviation(
                distance,
                width,
            )
            for distance in range(width + 1)
        ]
        self.assertEqual(24, width)
        self.assertEqual(0, deviations[0])
        self.assertEqual(
            structure_builder.SURFACE_NATIVE_TRANSITION_MAX_DEVIATION,
            deviations[-1],
        )
        self.assertLessEqual(
            max(
                right - left
                for left, right in zip(deviations, deviations[1:])
            ),
            1,
        )

    def test_surface_beard_contours_are_seeded_natural_and_slope_limited(self):
        structure = structure_builder.SparseStructure(
            (64, 6, 64),
            "wide_landmark",
        )
        margin = structure_builder.SURFACE_NATIVE_WORLDGEN_MARGIN

        first = structure_builder._surface_native_transition_deviation_field(
            structure,
            margin,
            None,
            918273,
        )
        repeated = (
            structure_builder._surface_native_transition_deviation_field(
                structure,
                margin,
                None,
                918273,
            )
        )
        alternate = (
            structure_builder._surface_native_transition_deviation_field(
                structure,
                margin,
                None,
                918274,
            )
        )

        self.assertEqual(first, repeated)
        self.assertNotEqual(first, alternate)
        for position, deviation in first.items():
            self.assertGreaterEqual(deviation, 0, position)
            self.assertLessEqual(
                deviation,
                structure_builder.SURFACE_NATIVE_TRANSITION_MAX_DEVIATION,
                position,
            )
            x, z = position
            for neighbor in ((x + 1, z), (x, z + 1)):
                if neighbor not in first:
                    continue
                self.assertLessEqual(
                    abs(deviation - first[neighbor]),
                    1,
                    (position, neighbor),
                )

        # A fixed deviation contour along a long straight wall must meander
        # instead of reproducing one perfectly parallel rectangular ring.
        crossing_distances = []
        for z in range(margin, margin + structure.size[2]):
            candidates = [
                margin - x
                for x in range(1, margin)
                if first.get((x, z), -1) >= 6
            ]
            self.assertTrue(candidates, z)
            crossing_distances.append(min(candidates))
        self.assertGreaterEqual(len(set(crossing_distances)), 4)

    def test_before_surface_naga_beard_clears_prevegetation_transition(self):
        structure = structure_builder.SparseStructure(
            (16, 6, 16),
            "naga_core",
        )
        structure.set(0, 0, 0, "minecraft:diamond_block")

        envelope = structure_builder._surface_native_envelope(
            structure,
            "naga_courtyard",
        )

        margin = structure_builder.SURFACE_NATIVE_WORLDGEN_MARGIN
        center_z = margin + structure.size[2] // 2
        ring_blocks = [
            block[0]
            for (x, _y, z), block in envelope.blocks.items()
            if x == margin - 1 and z == center_z
        ]
        self.assertIn("minecraft:grass_block", ring_blocks)
        self.assertIn("minecraft:air", ring_blocks)
        self.assertFalse(
            any(
                block[0] == "minecraft:air"
                and y
                > structure_builder.SURFACE_NATIVE_GROUND_Y
                + structure_builder.SURFACE_NATIVE_TRANSITION_MAX_DEVIATION
                for (_x, y, _z), block in envelope.blocks.items()
            ),
        )

    def test_tall_surface_landmark_does_not_clear_air_to_source_roof(self):
        structure = structure_builder.SparseStructure(
            (16, 96, 16),
            "sparse_tall_landmark",
        )
        structure.set(8, 95, 8, "minecraft:diamond_block")

        envelope = structure_builder._surface_native_envelope(
            structure,
            "lich_tower",
        )

        terrain_clear_height = (
            structure_builder.SURFACE_NATIVE_GROUND_Y
            + structure_builder.SURFACE_NATIVE_TRANSITION_MAX_DEVIATION
            + 1
        )
        self.assertGreater(
            envelope.size[1],
            terrain_clear_height,
            "the template must still contain the authored tower roof",
        )
        self.assertFalse(
            any(
                block[0] == "minecraft:air" and y >= terrain_clear_height
                for (_x, y, _z), block in envelope.blocks.items()
            ),
            "terrain adaptation must not bake air columns up to a tall "
            "landmark's roof",
        )

    def test_surface_environment_is_left_to_native_biome_passes(self):
        structure = structure_builder.SparseStructure(
            (40, 8, 40),
            "synthetic_lich_tower",
        )
        for x in range(16, 24):
            for z in range(16, 24):
                for y in range(8):
                    structure.set(x, y, z, "minecraft:stone_bricks")

        envelope = structure_builder._surface_native_envelope(
            structure,
            "lich_tower",
            environment_seed=123456,
        )
        self.assertFalse(
            {
                block[0]
                for block in envelope.blocks.values()
            }.intersection(
                {
                    "tf_slice:twilight_oak_log",
                    "tf_slice:twilight_oak_leaves",
                    "tf_slice:canopy_log",
                    "tf_slice:canopy_leaves",
                    "minecraft:short_grass",
                    "minecraft:fern",
                    "minecraft:dandelion",
                    "minecraft:poppy",
                    "minecraft:brown_mushroom",
                    "minecraft:red_mushroom",
                }
            )
        )
        self.assertEqual(
            "native_biome_decorations",
            envelope.environment_integration["mode"],
        )
        self.assertEqual(
            "surface_pass",
            envelope.environment_integration["landmarkPass"],
        )
        self.assertEqual(
            "after_surface_pass",
            envelope.environment_integration["treePass"],
        )
        self.assertEqual(
            ["after_surface_pass"],
            envelope.environment_integration["groundcoverPasses"],
        )
        self.assertEqual(0, envelope.environment_integration["bakedTrees"])
        self.assertEqual(0, envelope.environment_integration["bakedGroundcover"])

        margin = structure_builder.SURFACE_NATIVE_WORLDGEN_MARGIN
        for x in range(16, 24):
            for z in range(16, 24):
                self.assertEqual(
                    "minecraft:stone_bricks",
                    envelope.blocks[
                        (
                            x + margin,
                            structure_builder.SURFACE_NATIVE_GROUND_Y,
                            z + margin,
                        )
                    ][0],
                )

    def test_hollow_hill_roof_remains_native_tree_substrate(self):
        diameter = 36
        kind = "small_hill"
        terrain_seed = structure_builder.HOLLOW_HILL_TERRAIN_SEEDS[
            diameter
        ]
        shell, interior = structure_builder.hollow_hill(
            diameter,
            structure_builder.HOLLOW_HILL_CONTENT_SEEDS[diameter][0],
            split_layers=True,
            terrain_seed=terrain_seed,
        )
        combined = structure_builder.SparseStructure(shell.size, kind)
        combined.merge(shell)
        combined.merge(interior)
        envelope = structure_builder._surface_native_envelope(
            combined,
            kind,
            terrain_seed,
            environment_seed=987654,
        )

        self.assertNotIn(
            "tf_slice:landmark_protected_grass",
            {block[0] for block in envelope.blocks.values()},
        )
        self.assertGreater(
            sum(
                1
                for block in envelope.blocks.values()
                if block[0] == "minecraft:grass_block"
            ),
            100,
        )

    def test_labyrinth_mound_uses_biome_grass_and_trims_high_terrain(self):
        structure = structure_builder.SparseStructure(
            (40, 42, 40),
            "labyrinth_surface_mound",
        )
        ground_y = structure_builder.LABYRINTH_SURFACE_GROUND_Y
        center = 20
        structure.set(center, ground_y, center, "minecraft:grass_block")
        structure.surface_ground_y = ground_y
        structure.surface_columns = {(center, center): ground_y}
        structure.surface_core_radius = 1

        envelope = structure_builder._surface_native_envelope(
            structure,
            "labyrinth",
        )

        margin = structure_builder.SURFACE_NATIVE_WORLDGEN_MARGIN
        self.assertEqual(
            "minecraft:grass_block",
            envelope.blocks[(margin + center, ground_y, margin + center)][0],
            "the swamp mound must keep biome-tinted vanilla grass",
        )
        self.assertNotIn(
            structure_builder.LANDMARK_PROTECTED_GRASS_BLOCK,
            {block[0] for block in envelope.blocks.values()},
        )
        self.assertEqual(
            ground_y
            + 12
            + 1,
            envelope.size[1],
        )

        transition_seed = structure_builder._surface_environment_seed(
            "labyrinth",
            "terrain_transition",
            0,
        )
        field = structure_builder._surface_native_transition_deviation_field(
            structure,
            margin,
            None,
            transition_seed,
        )
        inner_position = min(field, key=field.get)
        self.assertEqual(
            "minecraft:air",
            envelope.blocks[
                (
                    inner_position[0],
                    ground_y + 12,
                    inner_position[1],
                )
            ][0],
            "the high-side transition must clear the 12-block budget",
        )

    def test_naga_surface_uses_protected_grass_to_preserve_open_arena(self):
        structure = structure_builder.SparseStructure(
            (32, 6, 32),
            "naga_open_arena",
        )
        for x in range(structure.size[0]):
            for z in range(structure.size[2]):
                structure.set(x, 0, z, "minecraft:grass_block")
        envelope = structure_builder._surface_native_envelope(
            structure,
            "naga_courtyard",
            environment_seed=24680,
        )
        protected = structure_builder.LANDMARK_PROTECTED_GRASS_BLOCK
        self.assertGreater(
            sum(1 for block in envelope.blocks.values() if block[0] == protected),
            structure.size[0] * structure.size[2],
        )
        self.assertEqual(
            protected,
            envelope.environment_integration["protectedSurfaceBlock"],
        )
        self.assertEqual(
            structure_builder.SURFACE_VEGETATION_EXCLUSION_RADIUS,
            envelope.environment_integration["protectionRadius"],
        )

    def test_dark_tower_surface_preserves_native_terrain_and_tree_shapes(self):
        structure = structure_builder.SparseStructure((8, 4, 8), "dark_tower")
        structure.surface_ground_y = structure_builder.SURFACE_NATIVE_GROUND_Y
        envelope = structure_builder._surface_native_envelope(
            structure,
            "dark_tower",
            environment_seed=13579,
        )
        protected = structure_builder.LANDMARK_PROTECTED_GRASS_BLOCK
        integration = envelope.environment_integration
        self.assertEqual(16, integration["protectionRadius"])
        self.assertEqual(0, integration["protectedColumns"])
        self.assertEqual(0, envelope.worldgen_margin)
        self.assertEqual({}, envelope.blocks)
        self.assertNotIn(
            protected,
            {block[0] for block in envelope.blocks.values()},
        )

    def test_hollow_hill_variants_match_documented_treasure_counts(self):
        expected_chests = {36: 3, 68: 6, 100: 12}
        expected_custom_mobs = {
            36: {"tf_slice:redcap", "tf_slice:swarm_spider"},
            68: {"tf_slice:redcap", "tf_slice:swarm_spider"},
            100: {
                "tf_slice:slime_beetle",
                "tf_slice:fire_beetle",
                "tf_slice:pinch_beetle",
                "tf_slice:wraith",
            },
        }
        for diameter in (36, 68, 100):
            hill = structure_builder.hollow_hill(
                diameter,
                structure_builder.HOLLOW_HILL_VARIANT_SEEDS[diameter],
            )
            chests = [
                block
                for block in hill.blocks.values()
                if block[0] == "minecraft:chest"
            ]
            spawner_mobs = {
                block[2].get("EntityIdentifier")
                for block in hill.blocks.values()
                if block[0] == "minecraft:mob_spawner"
            }
            self.assertEqual(expected_chests[diameter], len(chests))
            self.assertTrue(
                expected_custom_mobs[diameter].issubset(spawner_mobs)
            )

    def test_hollow_hill_tiles_are_anchored_below_the_surface(self):
        variants = self.entries["hollow_hill"]["variants"]
        expected_offsets = {
            "small_hill": -5,
            "medium_hill": -7,
            "large_hill": -9,
        }
        for variant in variants:
            self.assertEqual(
                {piece["offset"][1] for piece in variant["pieces"]},
                {expected_offsets[variant["landmarkKind"]]},
            )
            layers = [piece["layer"] for piece in variant["pieces"]]
            first_interior = layers.index("interior")
            self.assertEqual(
                {"shell"},
                set(layers[:first_interior]),
            )
            self.assertEqual(
                {"interior"},
                set(layers[first_interior:]),
            )
            for piece in variant["pieces"][:first_interior]:
                self.assertFalse(piece["removeBlock"])
                structure_path = catalog_structure_path(
                    self.catalog,
                    piece["structure"],
                )
                self.assertNotIn(
                    b"minecraft:air",
                    structure_path.read_bytes(),
                    "hollow-hill shell must preserve the terrain roof",
                )
            for piece in variant["pieces"][first_interior:]:
                self.assertFalse(piece["removeBlock"])

    def test_large_landmarks_have_seeded_layout_and_content_pools(self):
        expected_minimums = {
            "hedge_maze": 8,
            "naga_courtyard": 8,
            "mushroom_tower": 8,
            "hollow_hill": 24,
        }
        for ruin_id, minimum in expected_minimums.items():
            variants = self.entries[ruin_id]["variants"]
            self.assertGreaterEqual(len(variants), minimum)
            self.assertEqual(
                len({variant["layoutSeed"] for variant in variants}),
                len(variants),
            )

        hill_variants = self.entries["hollow_hill"]["variants"]
        for landmark_kind in ("small_hill", "medium_hill", "large_hill"):
            matching = [
                variant
                for variant in hill_variants
                if variant["landmarkKind"] == landmark_kind
            ]
            self.assertGreaterEqual(len(matching), 8)
            shell_sets = [
                tuple(
                    piece["structure"]
                    for piece in variant["pieces"]
                    if piece["layer"] == "shell"
                )
                for variant in matching
            ]
            interior_sets = [
                tuple(
                    piece["structure"]
                    for piece in variant["pieces"]
                    if piece["layer"] == "interior"
                )
                for variant in matching
            ]
            self.assertEqual(1, len(set(shell_sets)))
            self.assertEqual(len(matching), len(set(interior_sets)))

    def test_large_structures_are_split_into_at_most_sixteen_block_tiles(self):
        for ruin_id in (
            "hedge_maze",
            "naga_courtyard",
            "mushroom_tower",
            "hollow_hill",
            "quest_grove",
        ):
            entry = self.entries[ruin_id]
            self.assertEqual(entry["strategy"], "landmark_service")
            self.assertGreater(len(entry["pieces"]), 1)
            for variant in entry["variants"]:
                self.assertEqual(
                    variant["bounds"],
                    [
                        min(
                            piece["offset"][0]
                            for piece in variant["pieces"]
                        ),
                        min(
                            piece["offset"][1]
                            for piece in variant["pieces"]
                        ),
                        min(
                            piece["offset"][2]
                            for piece in variant["pieces"]
                        ),
                        max(
                            piece["offset"][0] + piece["size"][0] - 1
                            for piece in variant["pieces"]
                        ),
                        max(
                            piece["offset"][1] + piece["size"][1] - 1
                            for piece in variant["pieces"]
                        ),
                        max(
                            piece["offset"][2] + piece["size"][2] - 1
                            for piece in variant["pieces"]
                        ),
                    ],
                )
                for piece in variant["pieces"]:
                    self.assertLessEqual(piece["size"][0], 16)
                    self.assertLessEqual(piece["size"][2], 16)

    def test_hollow_tree_crown_is_tiled_and_has_no_detached_leaf_components(self):
        tree = structure_builder.hollow_tree(0, True)
        self.assertGreater(tree.size[0], 16)
        self.assertGreater(tree.size[2], 16)

        wood_or_leaf = {
            position
            for position, block in tree.blocks.items()
            if block[0]
            in (
                "tf_slice:twilight_oak_log",
                "tf_slice:twilight_oak_leaves",
            )
        }
        leaves = {
            position
            for position in wood_or_leaf
            if tree.blocks[position][0] == "tf_slice:twilight_oak_leaves"
        }
        logs = wood_or_leaf - leaves
        self.assertGreater(len(leaves), 300)
        self.assertGreater(
            len(
                {
                    (x, z)
                    for x, y, z in logs
                    if y >= tree.size[1] - 14
                }
            ),
            20,
        )

        remaining = set(leaves)
        while remaining:
            start = remaining.pop()
            frontier = [start]
            component = {start}
            touches_log = False
            while frontier:
                x, y, z = frontier.pop()
                for neighbor in (
                    (x + 1, y, z),
                    (x - 1, y, z),
                    (x, y + 1, z),
                    (x, y - 1, z),
                    (x, y, z + 1),
                    (x, y, z - 1),
                ):
                    if neighbor in logs:
                        touches_log = True
                    elif neighbor in remaining:
                        remaining.remove(neighbor)
                        component.add(neighbor)
                        frontier.append(neighbor)
            self.assertTrue(
                touches_log,
                "detached leaf component at %r (%d blocks)"
                % (start, len(component)),
            )

        entry = self.entries["leaf_dungeon"]
        for variant in entry["variants"]:
            self.assertGreater(len(variant["pieces"]), 1)
            for piece in variant["pieces"]:
                self.assertLessEqual(piece["size"][0], 16)
                self.assertLessEqual(piece["size"][2], 16)

    def test_hollow_tree_root_buttresses_are_embedded_in_the_surface(self):
        rule = load_json(
            BP / "netease_feature_rules" / "hollow_tree_feature_rule.json"
        )["minecraft:feature_rules"]
        center_x = "(math.floor(variable.originx / 32) * 32 + 16)"
        center_z = "(math.floor(variable.originz / 32) * 32 + 16)"
        self.assertEqual(
            "(query.get_height_at(%s, %s) - 10)" % (center_x, center_z),
            rule["distribution"]["y"],
        )

    def test_hollow_tree_restores_source_style_descending_roots(self):
        for seed in range(8):
            tree = structure_builder.hollow_tree(seed)
            radius = 2 + seed % 3
            center = tree.size[0] // 2
            surface_y = structure_builder.HOLLOW_ROOT_SUBSURFACE_DEPTH
            exposed_roots = {
                position
                for position, block in tree.blocks.items()
                if block[0] == "tf_slice:twilight_oak_log"
                and position[1] <= surface_y + 4
                and math.hypot(position[0] - center, position[2] - center)
                > radius + 0.25
            }
            buried_roots = {
                position
                for position, block in tree.blocks.items()
                if block[0] == "tf_slice:root_block"
            }
            self.assertGreaterEqual(len(exposed_roots), 4, seed)
            self.assertGreaterEqual(len(buried_roots), 20, seed)
            self.assertTrue(all(y >= surface_y for _x, y, _z in exposed_roots))
            self.assertTrue(all(y < surface_y for _x, y, _z in buried_roots))
            self.assertNotIn(
                "minecraft:dirt",
                {block[0] for block in tree.blocks.values()},
            )

            root_network = exposed_roots | buried_roots
            for x, y, z in root_network:
                neighbors = {
                    (x + 1, y, z),
                    (x - 1, y, z),
                    (x, y + 1, z),
                    (x, y - 1, z),
                    (x, y, z + 1),
                    (x, y, z - 1),
                }
                self.assertTrue(
                    neighbors.intersection(root_network)
                    or math.hypot(x - center, z - center) <= radius + 0.25,
                    (seed, (x, y, z)),
                )

    def test_hollow_stump_has_source_style_subsurface_base_and_roots(self):
        self.assertEqual(
            -structure_builder.HOLLOW_ROOT_SUBSURFACE_DEPTH,
            structure_builder.SMALL_VERTICAL_OFFSETS["hollow_stump"],
        )
        for seed in range(8):
            stump = structure_builder.hollow_stump(seed)
            surface_y = structure_builder.HOLLOW_ROOT_SUBSURFACE_DEPTH
            root_positions = {
                position
                for position, block in stump.blocks.items()
                if block[0] == "tf_slice:root_block"
            }
            log_positions = {
                position
                for position, block in stump.blocks.items()
                if block[0] == "tf_slice:twilight_oak_log"
            }
            self.assertTrue(root_positions, seed)
            self.assertEqual(surface_y, min(y for _x, y, _z in log_positions))
            self.assertTrue(all(y < surface_y for _x, y, _z in root_positions))
            self.assertTrue(
                all(
                    any(y == surface_y - depth for _x, y, _z in root_positions)
                    for depth in range(1, 5)
                ),
                seed,
            )
            self.assertNotIn(
                "minecraft:dirt",
                {block[0] for block in stump.blocks.values()},
            )

        rule = structure_builder._feature_rule(
            "tf_slice:hollow_stump_feature_rule",
            "tf_slice:hollow_stump_scatter_feature",
            "tf_slice_small_ruins",
            structure_builder.SMALL_VERTICAL_OFFSETS["hollow_stump"],
            structure_builder.POST_LANDMARK_PLACEMENT_PASS,
        )
        self.assertEqual(
            "query.get_height_at(variable.worldx, variable.worldz) - 9",
            rule["minecraft:feature_rules"]["distribution"]["y"],
        )

    def test_every_catalog_piece_has_a_real_mcstructure(self):
        for entry in self.entries.values():
            references = list(entry.get("pieces", []))
            for variant in entry.get("variants", []):
                references.extend(variant.get("pieces", []))
            for piece in references:
                self.assertLessEqual(piece["size"][0], 16)
                self.assertLessEqual(piece["size"][2], 16)
                structure_path = catalog_structure_path(
                    self.catalog,
                    piece["structure"],
                )
                self.assertTrue(structure_path.is_file(), structure_path)
                self.assertGreater(structure_path.stat().st_size, 64)


class RuntimeBlockCompatibilityTests(unittest.TestCase):
    def test_custom_logs_use_registered_stateless_axis_variants(self):
        for source, target in (
            ("twilight_oak", "twilight_oak"),
            ("canopy", "canopy"),
        ):
            java_name = "twilightforest:%s_log" % source
            for axis, suffix in (("x", "_x"), ("y", ""), ("z", "_z")):
                self.assertEqual(
                    ("tf_slice:%s_log%s" % (target, suffix), {}),
                    structure_builder._bedrock_block(
                        java_name,
                        {"axis": axis},
                    ),
                )

    def test_manual_rotation_updates_stateless_log_identifiers(self):
        self.assertEqual(
            ("tf_slice:twilight_oak_log_z", {}),
            structure_builder._rotated_block(
                "tf_slice:twilight_oak_log_x",
                {},
                1,
            ),
        )
        self.assertEqual(
            ("tf_slice:canopy_log_x", {}),
            structure_builder._rotated_block(
                "tf_slice:canopy_log_z",
                {},
                3,
            ),
        )
        self.assertEqual(
            ("tf_slice:twilight_oak_log_x", {}),
            structure_builder._rotated_block(
                "tf_slice:twilight_oak_log_x",
                {},
                2,
            ),
        )

    def test_generated_structure_palettes_only_use_declared_custom_states(self):
        schemas = {}
        for path in (BP / "netease_blocks").glob("*.json"):
            block = load_json(path).get("minecraft:block", {})
            description = block.get("description", {})
            identifier = description.get("identifier")
            if isinstance(identifier, str) and identifier.startswith("tf_slice:"):
                schemas[identifier] = description.get("states", {})

        offenders = {}
        for path in (BP / "structures").rglob("*.mcstructure"):
            for entry in load_mcstructure_palette(path):
                identifier = entry.get("name")
                if not isinstance(identifier, str) or not identifier.startswith(
                    "tf_slice:"
                ):
                    continue
                declared = schemas.get(identifier)
                invalid = sorted(
                    state
                    for state in entry.get("states", {})
                    if declared is None or state not in declared
                )
                if invalid:
                    offenders.setdefault(str(path.relative_to(BP)), []).append(
                        (identifier, invalid)
                    )

        self.assertEqual({}, offenders)

    def test_tick_sensitive_blocks_remain_in_the_real_ruin_structures(self):
        payload = b"".join(
            path.read_bytes()
            for path in (
                BP / "structures" / "tf_slice" / "ruins"
            ).rglob("*.mcstructure")
        )
        expected = {
            b"minecraft:fire",
            b"minecraft:redstone_wire",
            b"minecraft:redstone_torch",
            b"minecraft:unlit_redstone_torch",
            b"minecraft:unpowered_repeater",
            b"minecraft:sticky_piston",
            b"minecraft:dispenser",
            b"minecraft:chest",
            b"minecraft:barrel",
            b"minecraft:flower_pot",
            b"minecraft:vine",
        }
        self.assertEqual(
            set(),
            {
                block_id.decode("ascii")
                for block_id in expected
                if block_id not in payload
            },
        )

    def test_java_only_structure_blocks_map_to_registered_netease_ids(self):
        expected = {
            "minecraft:bricks": "minecraft:brick_block",
            "minecraft:cobblestone_stairs": "minecraft:stone_stairs",
            "minecraft:magma_block": "minecraft:magma",
            "minecraft:oak_trapdoor": "minecraft:trapdoor",
            "minecraft:redstone_wall_torch": "minecraft:redstone_torch",
            "minecraft:potted_dead_bush": "minecraft:flower_pot",
            "minecraft:piston_head": "minecraft:piston_arm_collision",
            "minecraft:cobweb": "minecraft:web",
            "minecraft:tripwire": "minecraft:stone_pressure_plate",
        }
        for java_name, expected_name in expected.items():
            actual_name, unused_states = structure_builder._bedrock_block(
                java_name,
                {},
            )
            self.assertEqual(expected_name, actual_name, java_name)

        self.assertEqual(
            "minecraft:powered_repeater",
            structure_builder._bedrock_block(
                "minecraft:repeater",
                {"powered": "true"},
            )[0],
        )
        self.assertEqual(
            "minecraft:unpowered_repeater",
            structure_builder._bedrock_block(
                "minecraft:repeater",
                {"powered": "false"},
            )[0],
        )

    def test_directional_java_states_are_converted_to_bedrock_states(self):
        stair_name, stair_states = structure_builder._bedrock_block(
            "minecraft:cobblestone_stairs",
            {"facing": "north", "half": "top"},
        )
        self.assertEqual("minecraft:stone_stairs", stair_name)
        self.assertEqual(3, stair_states["weirdo_direction"])
        self.assertTrue(stair_states["upside_down_bit"])

        trapdoor_name, trapdoor_states = structure_builder._bedrock_block(
            "minecraft:oak_trapdoor",
            {"facing": "north", "half": "top", "open": "false"},
        )
        self.assertEqual("minecraft:trapdoor", trapdoor_name)
        self.assertEqual(2, trapdoor_states["direction"])
        self.assertTrue(trapdoor_states["upside_down_bit"])
        self.assertFalse(trapdoor_states["open_bit"])

        repeater_name, repeater_states = structure_builder._bedrock_block(
            "minecraft:repeater",
            {"powered": "false", "facing": "east", "delay": "2"},
        )
        self.assertEqual("minecraft:unpowered_repeater", repeater_name)
        self.assertEqual(3, repeater_states["direction"])
        self.assertEqual(2, repeater_states["repeater_delay"])

        torch_name, torch_states = structure_builder._bedrock_block(
            "minecraft:redstone_wall_torch",
            {"lit": "false", "facing": "west"},
        )
        self.assertEqual("minecraft:unlit_redstone_torch", torch_name)
        self.assertEqual("west", torch_states["torch_facing_direction"])

        piston_name, piston_states = structure_builder._bedrock_block(
            "minecraft:piston_head",
            {"type": "sticky", "facing": "north"},
        )
        self.assertEqual("minecraft:sticky_piston_arm_collision", piston_name)
        self.assertEqual(2, piston_states["facing_direction"])

        for source_name in ("minecraft:ladder", "twilightforest:iron_ladder"):
            ladder_name, ladder_states = structure_builder._bedrock_block(
                source_name,
                {"facing": "east", "waterlogged": "false"},
            )
            self.assertEqual("minecraft:ladder", ladder_name)
            self.assertEqual(5, ladder_states["facing_direction"])

        chest_name, chest_states = structure_builder._bedrock_block(
            "minecraft:chest",
            {"facing": "west", "type": "single", "waterlogged": "false"},
        )
        self.assertEqual("minecraft:chest", chest_name)
        self.assertEqual(4, chest_states["facing_direction"])

        barrel_name, barrel_states = structure_builder._bedrock_block(
            "minecraft:barrel",
            {"facing": "up", "open": "true"},
        )
        self.assertEqual("minecraft:barrel", barrel_name)
        self.assertEqual(1, barrel_states["facing_direction"])
        self.assertTrue(barrel_states["open_bit"])

        dispenser_name, dispenser_states = structure_builder._bedrock_block(
            "minecraft:dispenser",
            {"facing": "down", "triggered": "true"},
        )
        self.assertEqual("minecraft:dispenser", dispenser_name)
        self.assertEqual(0, dispenser_states["facing_direction"])
        self.assertTrue(dispenser_states["triggered_bit"])

        hopper_name, hopper_states = structure_builder._bedrock_block(
            "minecraft:hopper",
            {"facing": "down", "enabled": "false"},
        )
        self.assertEqual("minecraft:hopper", hopper_name)
        self.assertEqual(0, hopper_states["facing_direction"])
        self.assertTrue(hopper_states["toggle_bit"])

        sticky_name, sticky_states = structure_builder._bedrock_block(
            "minecraft:sticky_piston",
            {"facing": "north", "extended": "true"},
        )
        self.assertEqual("minecraft:sticky_piston", sticky_name)
        self.assertEqual(2, sticky_states["facing_direction"])

        door_name, door_states = structure_builder._bedrock_block(
            "minecraft:spruce_door",
            {
                "facing": "east",
                "half": "upper",
                "hinge": "right",
                "open": "true",
            },
        )
        self.assertEqual("minecraft:spruce_door", door_name)
        self.assertEqual(3, door_states["direction"])
        self.assertTrue(door_states["upper_block_bit"])
        self.assertTrue(door_states["door_hinge_bit"])
        self.assertTrue(door_states["open_bit"])

        hook_name, hook_states = structure_builder._bedrock_block(
            "minecraft:tripwire_hook",
            {"facing": "west", "attached": "true", "powered": "true"},
        )
        self.assertEqual("minecraft:tripwire_hook", hook_name)
        self.assertEqual(1, hook_states["direction"])
        self.assertTrue(hook_states["attached_bit"])
        self.assertTrue(hook_states["powered_bit"])

        _, vine_states = structure_builder._bedrock_block(
            "minecraft:vine",
            {
                "east": "false",
                "north": "true",
                "south": "false",
                "up": "false",
                "west": "true",
            },
        )
        self.assertEqual(6, vine_states["vine_direction_bits"])

        _, wall_states = structure_builder._bedrock_block(
            "minecraft:cobblestone_wall",
            {
                "east": "low",
                "north": "tall",
                "south": "none",
                "up": "true",
                "west": "low",
            },
        )
        self.assertEqual(
            {
                "wall_connection_type_east": "short",
                "wall_connection_type_north": "tall",
                "wall_connection_type_south": "none",
                "wall_connection_type_west": "short",
                "wall_post_bit": True,
            },
            wall_states,
        )

    def test_manual_template_rotation_updates_every_directional_state(self):
        rotated = structure_builder._rotated_states(
            {
                "weirdo_direction": 0,
                "direction": 0,
                "facing_direction": 2,
                "torch_facing_direction": "north",
                "vine_direction_bits": 4,
                "wall_connection_type_east": "short",
                "wall_connection_type_north": "tall",
                "wall_connection_type_south": "none",
                "wall_connection_type_west": "short",
            },
            1,
        )
        self.assertEqual(2, rotated["weirdo_direction"])
        self.assertEqual(1, rotated["direction"])
        self.assertEqual(5, rotated["facing_direction"])
        self.assertEqual("east", rotated["torch_facing_direction"])
        self.assertEqual(8, rotated["vine_direction_bits"])
        self.assertEqual("short", rotated["wall_connection_type_south"])
        self.assertEqual("tall", rotated["wall_connection_type_east"])
        self.assertEqual("none", rotated["wall_connection_type_west"])
        self.assertEqual("short", rotated["wall_connection_type_north"])

    def test_courtyard_template_rotation_keeps_the_upstream_piece_origin(self):
        template = structure_builder.SparseStructure((3, 1, 5), "asymmetric")
        template.set(0, 0, 0, "minecraft:stone")
        template.set(2, 0, 4, "minecraft:gold_block")
        result = structure_builder.SparseStructure((24, 2, 24), "rotated")

        structure_builder._place_courtyard_template(
            result,
            template,
            (8, 0, 8),
            1,
            random.Random(1234),
        )

        self.assertEqual(
            {
                (8, 0, 8): ("minecraft:stone", {}, {}),
                (4, 0, 10): ("minecraft:gold_block", {}, {}),
            },
            result.blocks,
        )

    def test_courtyard_nagastone_keeps_original_directional_states(self):
        self.assertEqual(
            (
                "tf_slice:nagastone",
                {"tf_slice:variant": "north_up"},
            ),
            structure_builder._bedrock_block(
                "twilightforest:nagastone",
                {"variant": "north_up"},
            ),
        )
        self.assertEqual(
            (
                "tf_slice:etched_nagastone",
                {"tf_slice:facing": "east"},
            ),
            structure_builder._bedrock_block(
                "twilightforest:etched_nagastone",
                {"facing": "east"},
            ),
        )
        self.assertEqual(
            (
                "tf_slice:nagastone_pillar",
                {
                    "tf_slice:axis": "x",
                    "tf_slice:reversed": True,
                },
            ),
            structure_builder._bedrock_block(
                "twilightforest:nagastone_pillar",
                {"axis": "x", "reversed": "true"},
            ),
        )
        self.assertEqual(
            (
                "tf_slice:nagastone_stairs_left",
                {
                    "tf_slice:facing": "west",
                    "tf_slice:half": "top",
                    "tf_slice:shape": "outer_left",
                },
            ),
            structure_builder._bedrock_block(
                "twilightforest:nagastone_stairs_left",
                {
                    "facing": "west",
                    "half": "top",
                    "shape": "outer_left",
                },
            ),
        )

    def test_manual_rotation_updates_custom_nagastone_states(self):
        rotated = structure_builder._rotated_states(
            {
                "tf_slice:facing": "north",
                "tf_slice:axis": "x",
                "tf_slice:variant": "west_down",
            },
            1,
        )
        self.assertEqual("east", rotated["tf_slice:facing"])
        self.assertEqual("z", rotated["tf_slice:axis"])
        self.assertEqual("north_down", rotated["tf_slice:variant"])

    def test_druid_hut_keeps_support_ladder_and_original_weathering(self):
        template_path = (
            structure_builder.JAVA_STRUCTURES
            / "feature"
            / "druid_hut"
            / "druid_doubledeck.nbt"
        )
        structure = structure_builder.java_template(
            template_path,
            "druid_doubledeck",
        )

        for y in range(1, 6):
            self.assertEqual(
                ("tf_slice:canopy_log", {}),
                structure.blocks[(4, y, 4)][:2],
            )
            self.assertEqual(
                ("minecraft:ladder", {"facing_direction": 5}),
                structure.blocks[(5, y, 4)][:2],
            )

        weatherable = {
            "minecraft:cobblestone",
            "minecraft:stone_stairs",
            "minecraft:mossy_cobblestone",
            "minecraft:mossy_cobblestone_stairs",
            "minecraft:stone_bricks",
            "minecraft:mossy_stone_bricks",
        }
        weathered = {
            block[0]
            for block in structure.blocks.values()
            if block[0] in weatherable
            and block[0].startswith("minecraft:mossy_")
        }
        self.assertIn("minecraft:mossy_cobblestone", weathered)
        self.assertIn("minecraft:mossy_cobblestone_stairs", weathered)

    def test_legacy_bedrock_aliases_are_normalized_to_registered_ids(self):
        expected = {
            "minecraft:grass_block": "minecraft:grass_block",
            "minecraft:oak_planks": "minecraft:oak_planks",
            "minecraft:spruce_planks": "minecraft:spruce_planks",
            "minecraft:stone_bricks": "minecraft:stone_bricks",
            "minecraft:mossy_stone_bricks": "minecraft:mossy_stone_bricks",
            "minecraft:cracked_stone_bricks": "minecraft:cracked_stone_bricks",
            "minecraft:chiseled_stone_bricks": "minecraft:chiseled_stone_bricks",
            "minecraft:oak_slab": "minecraft:oak_slab",
            "minecraft:spruce_slab": "minecraft:spruce_slab",
            "minecraft:oak_fence": "minecraft:oak_fence",
            "twilightforest:canopy_fence": "minecraft:cherry_fence",
            "twilightforest:oak_banister": "minecraft:oak_fence",
            "twilightforest:root": "tf_slice:root_block",
            "twilightforest:liveroot_block": "tf_slice:liveroot_block",
            "twilightforest:firefly": "tf_slice:firefly",
            "twilightforest:hedge": "tf_slice:hedge",
            "twilightforest:mazestone": "tf_slice:mazestone",
        }
        for source_name, target_name in expected.items():
            self.assertEqual(
                target_name,
                structure_builder._bedrock_block(source_name, {})[0],
                source_name,
            )

    def test_structure_grass_uses_the_current_netease_block_version(self):
        self.assertEqual(
            CURRENT_NETEASE_BLOCK_VERSION,
            structure_builder.BEDROCK_BLOCK_VERSION,
        )

        grass_entries = []
        for path in sorted((BP / "structures").rglob("*.mcstructure")):
            if b"minecraft:grass_block" not in path.read_bytes():
                continue
            grass_entries.extend(
                entry
                for entry in load_mcstructure_palette(path)
                if entry.get("name") == "minecraft:grass_block"
            )

        self.assertTrue(grass_entries)
        self.assertEqual(
            {CURRENT_NETEASE_BLOCK_VERSION},
            {entry.get("version") for entry in grass_entries},
        )

    def test_unknown_java_minecraft_block_fails_closed(self):
        with self.assertRaises(ValueError):
            structure_builder._bedrock_block(
                "minecraft:future_java_only_block",
                {},
            )

    def test_compiled_structures_do_not_contain_java_only_block_ids(self):
        java_only_ids = {
            "minecraft:bricks",
            "minecraft:cobblestone_stairs",
            "minecraft:magma_block",
            "minecraft:oak_trapdoor",
            "minecraft:redstone_wall_torch",
            "minecraft:potted_dead_bush",
            "minecraft:piston_head",
            "minecraft:repeater",
            "minecraft:cobweb",
            "minecraft:tripwire",
        }
        offenders = {}
        for path in (BP / "structures").rglob("*.mcstructure"):
            payload = path.read_bytes()
            found = sorted(
                block_id
                for block_id in java_only_ids
                if (
                    len(block_id).to_bytes(2, "little")
                    + block_id.encode("ascii")
                )
                in payload
            )
            if found:
                offenders[str(path.relative_to(BP))] = found

        self.assertEqual({}, offenders)

    def test_compiled_structures_do_not_use_unregistered_legacy_aliases(self):
        legacy_aliases = {
            "minecraft:fence",
            "minecraft:grass",
            "minecraft:planks",
            "minecraft:stonebrick",
            "minecraft:wooden_slab",
        }
        offenders = {}
        for path in (BP / "structures").rglob("*.mcstructure"):
            payload = path.read_bytes()
            found = sorted(
                block_id
                for block_id in legacy_aliases
                if (
                    len(block_id).to_bytes(2, "little")
                    + block_id.encode("ascii")
                )
                in payload
            )
            if found:
                offenders[str(path.relative_to(BP))] = found

        self.assertEqual({}, offenders)

    def test_labyrinth_templates_use_registered_wooden_pressure_plates(self):
        structure_root = BP / "structures" / "tf_slice" / "ruins"
        labyrinth_tiles = sorted((structure_root / "labyrinth").rglob("*.mcstructure"))
        surface_tiles = sorted(
            (structure_root / "surface_native" / "labyrinth").rglob("*.mcstructure")
        )
        self.assertTrue(labyrinth_tiles)
        self.assertTrue(surface_tiles)

        offenders = [
            str(path.relative_to(BP))
            for path in labyrinth_tiles + surface_tiles
            if b"minecraft:oak_pressure_plate" in path.read_bytes()
        ]
        self.assertEqual([], offenders)

        payload = b"".join(
            path.read_bytes() for path in labyrinth_tiles + surface_tiles
        )
        self.assertIn(b"minecraft:wooden_pressure_plate", payload)

        builder = (ROOT / "tools" / "build_ruin_structures.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn('"minecraft:oak_pressure_plate"', builder)

    def test_all_templates_exclude_unknown_oak_pressure_plate(self):
        structure_root = BP / "structures"
        offenders = [
            str(path.relative_to(BP))
            for path in structure_root.rglob("*.mcstructure")
            if b"minecraft:oak_pressure_plate" in path.read_bytes()
        ]

        self.assertEqual([], offenders)
        dark_tower_port = (
            ROOT / "tools" / "dark_tower_legacy_port.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('"minecraft:oak_pressure_plate"', dark_tower_port)

    def test_behavior_pack_does_not_reference_unsupported_rooted_dirt(self):
        offenders = []
        for path in BP.rglob("*"):
            if (
                path.is_file()
                and "__pycache__" not in path.parts
                and b"minecraft:rooted_dirt" in path.read_bytes()
            ):
                offenders.append(str(path.relative_to(BP)))

        self.assertEqual([], offenders)

    def test_structure_builder_cannot_regenerate_unsupported_rooted_dirt(self):
        builder = (
            ROOT / "tools" / "build_ruin_structures.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn('"minecraft:rooted_dirt"', builder)


class NativeRuinFeatureContractTests(unittest.TestCase):
    def test_release_gate_resolves_deduplicated_structure_aliases(self):
        gate = release_validator.Gate()
        documents = release_validator.collect_json(gate)

        release_validator.validate_ruin_worldgen(gate, documents)

        alias_failures = [
            failure
            for failure in gate.failures
            if failure.startswith("Ruin structure is missing:")
            or failure.startswith("Surface-native landmark tile is missing:")
            or failure.startswith(
                "Surface-native landmark resource set does not match metadata:"
            )
        ]
        self.assertEqual([], alias_failures)

    def test_release_gate_accepts_four_cardinal_route_companions(self):
        gate = release_validator.Gate()
        documents = release_validator.collect_json(gate)

        release_validator.validate_dimension_worldgen(gate, documents)

        failures = [
            failure
            for failure in gate.failures
            if "must link four cardinal companion centers to its inner core"
            in failure
        ]
        self.assertEqual([], failures)

    def test_release_gate_accepts_dark_tower_zero_clearance_policy(self):
        gate = release_validator.Gate()
        documents = release_validator.collect_json(gate)

        release_validator.validate_ruin_worldgen(gate, documents)

        failures = [
            failure
            for failure in gate.failures
            if failure.startswith(
                "Surface-native landmark must use compact terrain and "
                "environment policies: dark_tower/"
            )
        ]
        self.assertEqual([], failures)

    def test_release_gate_accepts_knight_stronghold_bury_forest_policy(self):
        gate = release_validator.Gate()
        documents = release_validator.collect_json(gate)

        release_validator.validate_ruin_worldgen(gate, documents)

        failures = [
            failure
            for failure in gate.failures
            if "knight_stronghold/" in failure
            and (
                failure.startswith(
                    "Surface-native landmark must use compact terrain and "
                    "environment policies:"
                )
                or failure.startswith(
                    "Protected landmark surface does not match metadata:"
                )
            )
        ]
        self.assertEqual([], failures)

    def test_slice_validator_checks_custom_structure_palette_states(self):
        validator = (ROOT / "tools" / "validate_slice.py").read_text(
            encoding="utf-8"
        )

        self.assertIn("def validate_structure_custom_states(", validator)
        self.assertIn(
            "validate_structure_custom_states(gate, documents)",
            validator,
        )

    def test_slice_validator_rejects_runtime_landmark_watchdog_resources(self):
        validator = (ROOT / "tools" / "validate_slice.py").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "The runtime landmark watchdog must not be shipped",
            validator,
        )
        self.assertNotIn(
            "The native-first large-landmark watchdog is incomplete",
            validator,
        )

    def test_large_landmark_watchdog_is_not_emitted_by_new_builds(self):
        feature_path = (
            BP
            / "netease_features"
            / "ruin_landmark_surface_watchdog_structure_feature.json"
        )
        rule_path = (
            BP
            / "netease_feature_rules"
            / "ruin_landmark_surface_watchdog_feature_rule.json"
        )

        structure_path = (
            BP / "structures" / "tf_slice" / "ruin_landmark_surface_watchdog.mcstructure"
        )

        self.assertFalse(feature_path.exists())
        self.assertFalse(rule_path.exists())
        self.assertFalse(structure_path.exists())

    def test_large_landmarks_use_one_bounded_trigger_per_biome_mode(self):
        noop_structure = (
            BP / "structures" / "tf_slice" / "ruin_landmark_noop.mcstructure"
        )
        self.assertTrue(noop_structure.exists())

        for mode in (
            "ordinary",
            "dense_mushroom",
            "enchanted",
            "swamp",
            "fire_swamp",
            "dark_forest",
            "dark_forest_center",
        ):
            rule_path = (
                BP
                / "netease_feature_rules"
                / ("ruin_landmark_surface_%s_feature_rule.json" % mode)
            )
            rule = load_json(rule_path)["minecraft:feature_rules"]
            iterations = str(rule["distribution"]["iterations"])

            self.assertIn("query.is_biome", iterations)
            self.assertIn("math.abs", iterations)
            self.assertIn("? 1 : 0", iterations)
            self.assertFalse(
                (
                    BP
                    / "netease_features"
                    / (
                        "ruin_landmark_surface_%s_naga_structure_feature.json"
                        % mode
                    )
                ).exists()
            )

    def test_large_landmark_trigger_windows_cover_legacy_center_jitter(self):
        from tools import validate_slice

        tile_radii = {
            "ordinary": 5,
            "dense_mushroom": 5,
            "enchanted": 5,
            "swamp": 5,
            "fire_swamp": 4,
            "dark_forest": 5,
            "dark_forest_center": 3,
        }
        maximum_center_jitter_chunks = 3

        for mode, tile_radius in tile_radii.items():
            rule_path = (
                BP
                / "netease_feature_rules"
                / ("ruin_landmark_surface_%s_feature_rule.json" % mode)
            )
            rule = load_json(rule_path)["minecraft:feature_rules"]
            iterations = str(rule["distribution"]["iterations"])
            required_radius_blocks = (
                tile_radius + maximum_center_jitter_chunks
            ) * 16

            with self.subTest(mode=mode):
                self.assertGreaterEqual(
                    structure_builder.SURFACE_LANDMARK_TRIGGER_RADIUS_CHUNKS[
                        mode
                    ],
                    tile_radius + maximum_center_jitter_chunks,
                )
                self.assertGreaterEqual(
                    iterations.count("<= %d" % required_radius_blocks),
                    2,
                )
                self.assertEqual(
                    required_radius_blocks,
                    validate_slice.SURFACE_LANDMARK_TRIGGER_RADIUS_BLOCKS[
                        mode
                    ],
                )
            self.assertFalse(
                (
                    BP
                    / "netease_feature_rules"
                    / (
                        "ruin_landmark_surface_%s_naga_feature_rule.json"
                        % mode
                    )
                ).exists()
            )

    def test_large_landmark_proxy_structures_use_render_safe_void_palette(self):
        proxy_names = ["ruin_landmark_noop"] + [
            "ruin_landmark_surface_%s" % mode
            for mode in (
                "ordinary",
                "dense_mushroom",
                "enchanted",
                "swamp",
                "fire_swamp",
                "dark_forest",
                "dark_forest_center",
            )
        ]

        for proxy_name in proxy_names:
            structure_path = (
                BP
                / "structures"
                / "tf_slice"
                / (proxy_name + ".mcstructure")
            )
            with self.subTest(proxy=proxy_name):
                self.assertIn(
                    b"minecraft:structure_void",
                    structure_path.read_bytes(),
                )

    def test_surface_native_tiles_always_have_a_render_safe_palette(self):
        catalog = load_json(CATALOG_PATH)
        checked = 0
        for entry in catalog["structures"]:
            for variant in entry.get("variants", []):
                surface = variant.get("surfaceNative")
                if not isinstance(surface, dict):
                    continue
                for alignment, bounds in surface["centerAlignments"].items():
                    for delta_x in range(int(bounds[0]), int(bounds[2]) + 1):
                        for delta_z in range(int(bounds[1]), int(bounds[3]) + 1):
                            reference = (
                                structure_builder.surface_native_tile_reference(
                                    surface["prefix"],
                                    alignment,
                                    delta_x,
                                    delta_z,
                                )
                            )
                            structure_path = catalog_structure_path(
                                catalog,
                                reference,
                            )
                            checked += 1
                            structure_bytes = structure_path.read_bytes()
                            with self.subTest(structure=reference):
                                self.assertTrue(
                                    b"minecraft:" in structure_bytes
                                    or b"tf_slice:" in structure_bytes,
                                    (
                                        "native worldgen can forward this tile "
                                        "to the client renderer, so an empty "
                                        "block palette is unsafe"
                                    ),
                                )
        self.assertGreater(checked, 5000)

        crash_reproducer = catalog_structure_path(
            catalog,
            "tf_slice/ruins/surface_native/small_hill/small_v07/"
            "mx08_mz08/xm03_zm03",
        )
        self.assertIn(
            b"minecraft:structure_void",
            crash_reproducer.read_bytes(),
        )

    def test_large_landmark_surface_rules_share_one_region_height(self):
        old_rule = (
            BP
            / "netease_feature_rules"
            / "ruin_landmark_trigger_feature_rule.json"
        )
        self.assertFalse(old_rule.exists())

        for mode in (
            "ordinary",
            "dense_mushroom",
            "enchanted",
            "swamp",
            "fire_swamp",
        ):
            feature_path = (
                BP
                / "netease_features"
                / (
                    "ruin_landmark_surface_%s_structure_feature.json"
                    % mode
                )
            )
            rule_path = (
                BP
                / "netease_feature_rules"
                / ("ruin_landmark_surface_%s_feature_rule.json" % mode)
            )
            feature = load_json(feature_path)["netease:structure_feature"]
            rule = load_json(rule_path)["minecraft:feature_rules"]
            distribution = rule["distribution"]

            self.assertEqual(
                "tf_slice:ruin_landmark_surface_%s" % mode,
                feature["places_structure"],
            )
            self.assertEqual(
                "surface_pass",
                rule["conditions"]["placement_pass"],
            )
            self.assertEqual(0, distribution["x"])
            self.assertEqual(0, distribution["z"])
            if mode in ("swamp", "fire_swamp"):
                self.assertEqual(
                    1,
                    distribution["y"].count("query.get_height_at"),
                )
                self.assertNotIn("math.max", distribution["y"])
                self.assertNotIn("math.min", distribution["y"])
                self.assertIn(
                    (
                        "- %d" % structure_builder.LABYRINTH_SURFACE_GROUND_Y
                        if mode == "swamp"
                        else "- 17"
                    ),
                    distribution["y"],
                )
            else:
                self.assertIn("math.floor", distribution["y"])
                self.assertIn("math.min", distribution["y"])
                self.assertIn("query.get_height_at", distribution["y"])
                self.assertEqual(
                    10,
                    distribution["y"].count("query.get_height_at"),
                )
                self.assertEqual(8, distribution["y"].count("math.max"))
                self.assertEqual(1, distribution["y"].count("math.min"))
                self.assertIn("+ 64", distribution["y"])
                self.assertIn("- 64", distribution["y"])
                self.assertIn("+ 3", distribution["y"])
                self.assertIn("- 17", distribution["y"])
            self.assertIn(
                "query.is_biome",
                distribution["iterations"],
            )

            self.assertIn("math.abs", distribution["iterations"])
            self.assertFalse(
                (
                    BP
                    / "netease_features"
                    / (
                        "ruin_landmark_surface_%s_naga_structure_feature.json"
                        % mode
                    )
                ).exists()
            )
            self.assertFalse(
                (
                    BP
                    / "netease_feature_rules"
                    / (
                        "ruin_landmark_surface_%s_naga_feature_rule.json"
                        % mode
                    )
                ).exists()
            )

    def test_native_features_place_real_structures_in_the_engine_pipeline(self):
        catalog = load_json(CATALOG_PATH)
        expected_features = {}

        for entry in catalog["structures"]:
            if entry["strategy"] != "native_feature":
                continue
            for variant in entry["variants"]:
                native = variant["nativeFeature"]
                target = native["structure"]
                self.assertTrue(target.startswith("tf_slice/ruins/"))
                self.assertEqual(native["rotation"], variant["rotation"])
                self.assertEqual(
                    native["surfaceOffset"],
                    -NATIVE_VERTICAL_OFFSETS.get(entry["id"], 0),
                )
                relative = target.replace(":", "/", 1)
                target_path = (
                    BP / "structures" / ("%s.mcstructure" % relative)
                )
                self.assertTrue(target_path.is_file(), target_path)
                expected_features[native["identifier"]] = native

        actual_features = {}
        for path in (BP / "netease_features").glob(
            "*_structure_feature.json"
        ):
            document = load_json(path)
            feature = document.get("netease:structure_feature")
            if feature is None:
                continue
            identifier = feature["description"]["identifier"]
            if identifier in expected_features:
                actual_features[identifier] = feature
                native = expected_features[identifier]
                self.assertEqual(
                    native["structure"].replace("tf_slice/", "tf_slice:", 1),
                    feature["places_structure"],
                )
                self.assertEqual(native["rotation"], feature["rotation"])
                self.assertFalse(
                    feature["places_structure"].startswith(
                        "tf_slice:ruin_handoff/"
                    )
                )

        self.assertEqual(set(expected_features), set(actual_features))

    def test_large_landmarks_have_chunk_aligned_surface_native_tiles(self):
        catalog = load_json(CATALOG_PATH)
        entries = {
            entry["id"]: entry for entry in catalog["structures"]
        }
        for entry_id in (
            "hedge_maze",
            "naga_courtyard",
            "lich_tower",
            "quest_grove",
            "mushroom_tower",
            "hollow_hill",
        ):
            for variant in entries[entry_id]["variants"]:
                surface = variant["surfaceNative"]
                self.assertEqual(16, surface["groundY"])
                self.assertEqual(0, surface["vegetationClearance"])
                self.assertEqual(16, surface["terrainClearance"])
                self.assertEqual(
                    "surface_pass",
                    surface["terrainAdaptationStage"],
                )
                self.assertEqual(
                    {
                        "mode": "beard_thin",
                        "width": 24,
                        "maxDeviation": 16,
                        "contourMode": "seeded_low_frequency",
                        "noiseAmplitude": 5,
                        "noiseCellSize": 12,
                        "maxAdjacentStep": 1,
                        "runtimeWrites": False,
                    },
                    surface["terrainAdaptation"],
                )
                self.assertEqual(
                    {
                        "mode": "center_capped_max_3x3",
                        "radius": 64,
                        "maxRise": 3,
                    },
                    surface["terrainAnchor"],
                )
                environment = surface["environmentIntegration"]
                self.assertEqual(
                    "native_biome_decorations",
                    environment["mode"],
                )
                self.assertEqual("surface_pass", environment["landmarkPass"])
                self.assertEqual("after_surface_pass", environment["treePass"])
                self.assertEqual(
                    ["after_surface_pass"],
                    environment["groundcoverPasses"],
                )
                self.assertFalse(environment["runtimeWrites"])
                self.assertEqual(0, environment["bakedTrees"])
                self.assertEqual(0, environment["bakedGroundcover"])
                self.assertEqual(
                    "tf_slice:landmark_protected_grass",
                    environment["protectedSurfaceBlock"],
                )
                self.assertNotIn("edgeBlendWidth", surface)
                self.assertNotIn("edgeBlendMode", surface)
                self.assertNotIn("edgeBlendShape", surface)
                self.assertEqual(3, len(surface["sourceSize"]))
                self.assertNotIn("vegetationMargin", surface)
                self.assertNotIn("treeExclusionSurface", surface)
                self.assertEqual(
                    "surface_pass",
                    surface["placementPass"],
                )
                self.assertEqual(
                    {"8,8"},
                    set(surface["centerAlignments"]),
                )
                for alignment, chunk_bounds in (
                    surface["centerAlignments"].items()
                ):
                    self.assertEqual(4, len(chunk_bounds))
                    minimum_x, minimum_z, maximum_x, maximum_z = (
                        chunk_bounds
                    )
                    self.assertLessEqual(minimum_x, maximum_x)
                    self.assertLessEqual(minimum_z, maximum_z)
                    for delta_x in range(minimum_x, maximum_x + 1):
                        for delta_z in range(
                            minimum_z,
                            maximum_z + 1,
                        ):
                            reference = (
                                structure_builder.surface_native_tile_reference(
                                    surface["prefix"],
                                    alignment,
                                    delta_x,
                                    delta_z,
                                )
                            )
                            path = catalog_structure_path(catalog, reference)
                            self.assertTrue(path.is_file(), str(path))

    def test_native_tree_features_cannot_root_on_landmark_guard_surface(self):
        tree_count = 0
        for path in (BP / "netease_features").glob("*.json"):
            document = load_json(path)
            tree = document.get("minecraft:tree_feature")
            if tree is None:
                continue
            tree_count += 1
            growable = set(tree.get("may_grow_on", []))
            growable.update(tree.get("base_block", []))
            self.assertNotIn("minecraft:moss_block", growable, path.name)
        self.assertGreater(tree_count, 0)

    def test_small_ruins_have_netease_features_scatter_chance_and_rules(self):
        for ruin_id, denominator in SMALL_RARITIES.items():
            structure_feature_path = (
                BP / "netease_features" / ("%s_structure_selector_feature.json" % ruin_id)
            )
            scatter_path = (
                BP / "netease_features" / ("%s_scatter_feature.json" % ruin_id)
            )
            rule_path = (
                BP / "netease_feature_rules" / ("%s_feature_rule.json" % ruin_id)
            )
            structure_feature = load_json(structure_feature_path)
            scatter = load_json(scatter_path)
            rule = load_json(rule_path)

            feature = structure_feature["minecraft:weighted_random_feature"]
            self.assertEqual(
                feature["description"]["identifier"],
                "tf_slice:%s_structure_selector_feature" % ruin_id,
            )
            self.assertGreaterEqual(len(feature["features"]), 1)
            rotations = set()
            for variant_id, weight in feature["features"]:
                self.assertTrue(variant_id.startswith("tf_slice:%s_" % ruin_id))
                self.assertGreater(weight, 0)
                variant_feature = load_json(
                    BP
                    / "netease_features"
                    / ("%s.json" % variant_id.split(":", 1)[1])
                )
                rotations.add(
                    variant_feature["netease:structure_feature"].get(
                        "rotation",
                        0,
                    )
                )
            self.assertEqual(rotations, {0, 90, 180, 270})
            self.assertEqual(
                {
                    variant["rotation"]
                    for variant in load_json(CATALOG_PATH)["structures"]
                    if variant["id"] == ruin_id
                    for variant in variant["variants"]
                },
                {0, 90, 180, 270},
            )

            scatter_body = scatter["minecraft:scatter_feature"]
            self.assertEqual(
                scatter_body["scatter_chance"],
                {"numerator": 1, "denominator": denominator},
            )
            self.assertIsInstance(scatter_body["iterations"], str)
            self.assertIn("query.get_height_at", scatter_body["iterations"])
            self.assertIn("math.max", scatter_body["iterations"])
            self.assertIn("math.min", scatter_body["iterations"])
            self.assertIn("<= 2", scatter_body["iterations"])
            self.assertEqual(
                scatter_body["places_feature"],
                "tf_slice:%s_structure_selector_feature" % ruin_id,
            )

            rule_body = rule["minecraft:feature_rules"]
            self.assertEqual(
                rule_body["description"]["places_feature"],
                "tf_slice:%s_scatter_feature" % ruin_id,
            )
            y_expression = rule_body["distribution"]["y"]
            expected_offset = SMALL_VERTICAL_OFFSETS.get(ruin_id, 0)
            if expected_offset:
                self.assertTrue(y_expression.endswith(" - %d" % abs(expected_offset)))
            else:
                self.assertNotIn(" - ", y_expression)
            filter_text = json.dumps(rule_body["conditions"]["minecraft:biome_filter"])
            self.assertIn("dm33027004", filter_text)
            self.assertIn("tf_slice_small_ruins", filter_text)
            filters = rule_body["conditions"]["minecraft:biome_filter"][0]["all_of"]
            exclusions = {
                item["value"]
                for item in filters
                if item.get("operator") == "!="
            }
            self.assertEqual(exclusions, set())

    def test_graveyard_embeds_its_two_groundwork_layers_at_surface(self):
        graveyard = structure_builder.graveyard_structure()
        footprint = graveyard.size[0] * graveyard.size[2]
        foundation_names = [
            graveyard.blocks[(x, 0, z)][0]
            for x in range(graveyard.size[0])
            for z in range(graveyard.size[2])
        ]
        surface_names = [
            graveyard.blocks[(x, 1, z)][0]
            for x in range(graveyard.size[0])
            for z in range(graveyard.size[2])
        ]
        self.assertNotIn("minecraft:air", foundation_names)
        self.assertGreaterEqual(
            foundation_names.count("minecraft:dirt"),
            footprint * 9 // 10,
        )
        self.assertGreaterEqual(
            sum(
                name in ("minecraft:grass", "minecraft:grass_block")
                for name in surface_names
            ),
            footprint * 9 // 10,
        )

        rule = load_json(
            BP / "netease_feature_rules" / "graveyard_feature_rule.json"
        )["minecraft:feature_rules"]
        self.assertEqual(
            "query.get_height_at(variable.worldx, variable.worldz) - 2",
            rule["distribution"]["y"],
        )

        catalog_entries = {
            entry["id"]: entry
            for entry in load_json(CATALOG_PATH)["structures"]
        }
        catalog_variant = catalog_entries["graveyard"]["variants"][0]
        self.assertEqual(2, catalog_variant["nativeFeature"]["surfaceOffset"])

    def test_native_ruin_rules_run_in_surface_pass_before_environment(self):
        environment = {"fallen_hollow_log", "hollow_stump", "hollow_tree"}
        rule_names = (set(SMALL_RARITIES) - environment) | {"graveyard"}
        for ruin_id in sorted(rule_names):
            rule = load_json(
                BP / "netease_feature_rules" / ("%s_feature_rule.json" % ruin_id)
            )["minecraft:feature_rules"]
            self.assertEqual(
                "surface_pass",
                rule["conditions"]["placement_pass"],
                ruin_id,
            )

        for ruin_id in sorted(environment):
            rule = load_json(
                BP / "netease_feature_rules" / ("%s_feature_rule.json" % ruin_id)
            )["minecraft:feature_rules"]
            self.assertEqual(
                "after_surface_pass",
                rule["conditions"]["placement_pass"],
                ruin_id,
            )

    def test_all_tree_features_accept_native_landmark_grass_only(self):
        protected = "tf_slice:landmark_protected_grass"
        tree_features = []
        for path in sorted((BP / "netease_features").glob("*.json")):
            document = load_json(path)
            tree = document.get("minecraft:tree_feature")
            if tree is not None:
                tree_features.append((path.name, tree))
        self.assertGreaterEqual(len(tree_features), 10)
        for filename, tree in tree_features:
            substrates = set(tree.get("may_grow_on", []))
            self.assertIn("minecraft:grass_block", substrates, filename)
            self.assertNotIn(protected, substrates, filename)

    def test_native_biome_decorators_reproject_to_structure_written_surface(self):
        self.assertEqual(
            [],
            sorted(
                (BP / "netease_features").glob(
                    "*_landmark_surface_search_feature.json"
                )
            ),
        )
        self.assertEqual(
            [],
            sorted(
                (BP / "netease_features").glob(
                    "*_landmark_surface_snap_feature.json"
                )
            ),
        )
        feature_documents = {}
        for path in sorted((BP / "netease_features").glob("*.json")):
            document = load_json(path)
            for feature_type, body in document.items():
                if not isinstance(body, dict):
                    continue
                identifier = body.get("description", {}).get("identifier")
                if identifier:
                    feature_documents[identifier] = document
                    break

        tree_identifiers = {
            identifier
            for identifier, document in feature_documents.items()
            if "minecraft:tree_feature" in document
            or (
                "tree"
                in str(
                    document.get("netease:structure_feature", {}).get(
                        "places_structure", ""
                    )
                ).lower()
                and not str(
                    document.get("netease:structure_feature", {}).get(
                        "places_structure", ""
                    )
                ).lower().startswith("tf_slice:ruins/")
                and str(
                    document.get("netease:structure_feature", {}).get(
                        "places_structure", ""
                    )
                ).lower()
                != "tf_slice:hollow_tree_chunk_trigger"
            )
        }

        def referenced_features(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    if key == "identifier":
                        continue
                    for reference in referenced_features(child):
                        yield reference
            elif isinstance(value, list):
                for child in value:
                    for reference in referenced_features(child):
                        yield reference
            elif isinstance(value, str) and value in feature_documents:
                yield value

        def reaches_tree(identifier, visiting=None):
            if identifier in tree_identifiers:
                return True
            if identifier not in feature_documents:
                return False
            visiting = set(visiting or ())
            if identifier in visiting:
                return False
            visiting.add(identifier)
            return any(
                reaches_tree(reference, visiting)
                for reference in referenced_features(
                    feature_documents[identifier]
                )
            )

        tree_rule_count = 0
        projected_patch_count = 0
        for path in sorted((BP / "netease_feature_rules").glob("*.json")):
            body = load_json(path).get("minecraft:feature_rules")
            if body is None or body.get("conditions", {}).get(
                "placement_pass"
            ) not in ("surface_pass", "after_surface_pass"):
                continue
            placed = body["description"]["places_feature"]
            y_expression = str(body.get("distribution", {}).get("y", ""))
            if path.stem in (
                "dark_forest_tree_profile_feature_rule",
                "dark_forest_center_tree_profile_feature_rule",
            ):
                self.assertEqual(
                    "after_surface_pass",
                    body["conditions"]["placement_pass"],
                    path.name,
                )
                self.assertNotIn("+ 64", y_expression, path.name)
                continue
            if reaches_tree(placed):
                tree_rule_count += 1
                self.assertEqual(
                    "after_surface_pass",
                    body["conditions"]["placement_pass"],
                    path.name,
                )
                self.assertIn("+ 64", y_expression, path.name)
                projection = feature_documents[placed].get(
                    "minecraft:scatter_feature"
                )
                self.assertIsNotNone(projection, path.name)
                self.assertTrue(
                    projection["project_input_to_floor"], path.name
                )
                self.assertEqual(
                    {
                        "iterations": 1,
                        "coordinate_eval_order": "xzy",
                        "x": 0,
                        "y": 0,
                        "z": 0,
                    },
                    projection["distribution"],
                    path.name,
                )
                continue

            feature = feature_documents.get(placed, {}).get(
                "minecraft:scatter_feature"
            )
            if feature is not None and feature.get("project_input_to_floor"):
                projected_patch_count += 1
                self.assertIn("+ 64", y_expression, path.name)

        self.assertGreaterEqual(tree_rule_count, 10)
        self.assertGreaterEqual(projected_patch_count, 8)

    def test_no_biome_feature_can_use_the_protected_landmark_surface(self):
        protected = "tf_slice:landmark_protected_grass"
        for path in sorted((BP / "netease_features").glob("*.json")):
            self.assertNotIn(
                protected,
                json.dumps(load_json(path), sort_keys=True),
                path.name,
            )

    def test_landmark_protected_grass_is_server_client_closed(self):
        identifier = "tf_slice:landmark_protected_grass"
        server = load_json(
            BP / "netease_blocks" / "landmark_protected_grass.json"
        )
        self.assertEqual(
            identifier,
            server["minecraft:block"]["description"]["identifier"],
        )

        client = load_json(RP / "blocks.json")
        self.assertIn(identifier, client)
        textures = client[identifier]["textures"]
        self.assertEqual("tf_slice:landmark_protected_grass_top", textures["up"])
        self.assertEqual("tf_slice:landmark_protected_grass_side", textures["side"])
        self.assertEqual("tf_slice:landmark_protected_grass_bottom", textures["down"])

        atlas = load_json(RP / "textures" / "terrain_texture.json")["texture_data"]
        for key in textures.values():
            self.assertIn(key, atlas)

        self.assertEqual("1.21.80", server["format_version"])
        components = server["minecraft:block"]["components"]
        self.assertEqual(
            "minecraft:geometry.full_block",
            components["minecraft:geometry"],
        )
        materials = components["minecraft:material_instances"]
        self.assertEqual(
            {
                "texture": textures["up"],
                "render_method": "opaque",
                "tint_method": "grass",
            },
            materials["up"],
        )
        self.assertEqual(
            {
                "texture": textures["side"],
                "render_method": "opaque",
            },
            materials["*"],
        )
        self.assertEqual(
            {
                "texture": textures["down"],
                "render_method": "opaque",
            },
            materials["down"],
        )
        self.assertEqual(
            "textures/blocks/grass_top",
            atlas[textures["up"]]["textures"],
        )


class SpecialBiomeContractTests(unittest.TestCase):
    def test_spooky_and_dense_mushroom_biomes_are_server_client_closed(self):
        for biome_id, tag in (
            ("dm33027004_roofed_forest", "tf_slice_spooky_forest"),
            ("dm33027004_mushroom_island", "tf_slice_dense_mushroom_forest"),
        ):
            server = load_json(
                BP / "netease_biomes" / "dm33027004" / ("%s.json" % biome_id)
            )
            client = load_json(RP / "biomes" / ("%s.client_biome.json" % biome_id))
            self.assertEqual(
                server["minecraft:biome"]["description"]["identifier"],
                biome_id,
            )
            self.assertIn(tag, server["minecraft:biome"]["components"])
            self.assertEqual(
                client["minecraft:client_biome"]["description"]["identifier"],
                biome_id,
            )

    def test_dimension_pool_registers_both_special_biomes(self):
        dimension = load_json(BP / "netease_dimension" / "dm33027004.json")
        text = json.dumps(dimension)
        self.assertIn("dm33027004_roofed_forest", text)
        self.assertIn("dm33027004_mushroom_island", text)


class RuinServerIntegrationContractTests(unittest.TestCase):
    def test_server_disables_client_chunk_generation_after_addon_load(self):
        server_text = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            '"LoadServerAddonScriptsAfter",',
            server_text,
        )
        self.assertIn(
            "self.OnLoadServerAddonScriptsAfter",
            server_text,
        )
        handler_start = server_text.index(
            "    def OnLoadServerAddonScriptsAfter("
        )
        handler_end = server_text.index("    def ", handler_start + 8)
        handler = server_text[handler_start:handler_end]
        self.assertIn(
            "self._chunk_comp.OpenClientChunkGeneration(False)",
            handler,
        )

    def test_hollow_hill_runtime_uses_isolated_spawn_random_streams(self):
        service_text = (
            BP / "TwilightBossSlice" / "structureWorldgenService.py"
        ).read_text(encoding="utf-8")
        start = service_text.index("    def _spawn_hollow_hill_group(")
        end = service_text.index("    def ", start + 8)
        helper = service_text[start:end]
        self.assertIn("landmark_stream_seed", helper)
        self.assertIn('"spawn_group"', helper)
        self.assertIn('"spawn_position"', helper)
        self.assertNotIn("_stable_seed", helper)

    def test_server_integrates_worldgen_service_and_debug_commands(self):
        server_text = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        service_text = (
            BP / "TwilightBossSlice" / "structureWorldgenService.py"
        ).read_text(encoding="utf-8")

        self.assertIn("StructureWorldgenService", server_text)
        runtime_catalog_path = (
            BP / "TwilightBossSlice" / "ruin_catalog_data.py"
        )
        self.assertTrue(runtime_catalog_path.is_file())
        runtime_namespace = {}
        exec(
            compile(
                runtime_catalog_path.read_text(encoding="utf-8"),
                str(runtime_catalog_path),
                "exec",
            ),
            runtime_namespace,
        )
        self.assertEqual(
            json.loads(runtime_namespace["CATALOG_JSON"]),
            load_json(CATALOG_PATH),
        )
        self.assertIn("self._ruin_worldgen.tick", server_text)
        self.assertIn('"ChunkGeneratedServerEvent"', server_text)
        self.assertIn("OnChunkGeneratedServerEvent", server_text)
        self.assertIn("on_chunk_generated_event(args)", server_text)
        self.assertIn('"ChunkLoadedServerEvent"', server_text)
        self.assertIn("OnChunkLoadedServerEvent", server_text)
        self.assertIn("on_chunk_loaded_event(args)", server_text)
        self.assertIn("!slice ruin list", server_text)
        self.assertIn("!slice ruin locate", server_text)
        self.assertIn("!slice ruin place", server_text)
        self.assertIn("!slice ruin status", server_text)
        self.assertIn(
            "StructureWorldgenService, DEFAULT_LOCATE_RADIUS",
            server_text,
        )
        self.assertNotIn(
            "structureWorldgenService.DEFAULT_LOCATE_RADIUS",
            server_text,
        )

        self.assertIn("tf_slice:ruin_landmarks_v1", service_text)
        self.assertIn("ruin_catalog_data", service_text)
        self.assertIn("CreateExtraData", service_text)
        self.assertIn("PlaceStructure", service_text)
        self.assertIn("MAX_PIECES_PER_TICK = 1", service_text)
        self.assertIn("is_inside_landmark_clearance", service_text)
        self.assertIn('variant.get("bounds") or entry.get', service_text)
        self.assertIn("_native_structure_handoffs", service_text)
        self.assertIn("debug_locate", service_text)
        self.assertIn("_spawn_ruin_entity", server_text)


class RuinGameplayDependencyContractTests(unittest.TestCase):
    def test_all_required_ruin_mobs_have_server_and_client_definitions(self):
        for mob_id in RUIN_MOBS:
            server = load_json(BP / "entities" / ("%s.entity.json" % mob_id))
            client = load_json(RP / "entity" / ("%s.entity.json" % mob_id))
            expected = "tf_slice:%s" % mob_id
            self.assertEqual(
                server["minecraft:entity"]["description"]["identifier"],
                expected,
            )
            self.assertEqual(
                client["minecraft:client_entity"]["description"]["identifier"],
                expected,
            )

    def test_ruin_mobs_have_real_animated_models_and_creative_spawn_eggs(self):
        upstream_texture_mobs = {
            "raven",
            "skeleton_druid",
            "swarm_spider",
            "hedge_spider",
            "wraith",
            "redcap",
            "redcap_sapper",
            "kobold",
        }
        placeholder_geometries = {
            "geometry.tf_slice.ruin_humanoid",
            "geometry.tf_slice.ruin_spider",
            "geometry.tf_slice.ruin_bird",
            "geometry.tf_slice.ruin_quadruped",
        }
        en_us = (RP / "texts" / "en_US.lang").read_text(encoding="utf-8")
        zh_cn = (RP / "texts" / "zh_CN.lang").read_text(encoding="utf-8")
        creative_catalog = json.dumps(
            load_json(BP / "item_catalog" / "crafting_item_catalog.json")
        )
        self.assertNotIn("\ufffd", zh_cn)

        for mob_id in RUIN_MOBS:
            server_description = load_json(
                BP / "entities" / ("%s.entity.json" % mob_id)
            )["minecraft:entity"]["description"]
            client_description = load_json(
                RP / "entity" / ("%s.entity.json" % mob_id)
            )["minecraft:client_entity"]["description"]

            self.assertIs(server_description["is_spawnable"], True, mob_id)
            self.assertIn("spawn_egg", client_description, mob_id)
            self.assertIn("animations", client_description, mob_id)
            self.assertTrue(
                client_description.get("animation_controllers")
                or client_description.get("scripts", {}).get("animate"),
                mob_id,
            )
            self.assertTrue(
                set(client_description["geometry"].values()).isdisjoint(
                    placeholder_geometries
                ),
                mob_id,
            )
            egg_key = "item.spawn_egg.entity.tf_slice:%s.name=" % mob_id
            self.assertIn(egg_key, en_us, mob_id)
            self.assertIn(egg_key, zh_cn, mob_id)
            self.assertIn(
                "tf_slice:%s_spawn_egg" % mob_id,
                creative_catalog,
                mob_id,
            )

            if mob_id in upstream_texture_mobs:
                texture = client_description["textures"]["default"]
                self.assertTrue(
                    texture.startswith("textures/entity/tf_slice/"),
                    (mob_id, texture),
                )
                self.assertTrue(
                    (RP / (texture + ".png")).is_file(),
                    (mob_id, texture),
                )

    def test_ruin_loot_tables_are_complete_and_only_reference_real_items(self):
        for loot_id in RUIN_LOOT_TABLES:
            table = load_json(
                BP / "loot_tables" / "chests" / "tf_slice" / ("%s.json" % loot_id)
            )
            self.assertGreaterEqual(len(table["pools"]), 1)
            entries = [
                entry
                for pool in table["pools"]
                for entry in pool.get("entries", [])
            ]
            self.assertGreaterEqual(len(entries), 1)
            for entry in entries:
                self.assertTrue(
                    entry["name"].startswith("minecraft:")
                    or entry["name"] == "tf_slice:torchberries"
                )

    def test_hollow_hill_loot_keeps_the_upstream_vanilla_item_subset(self):
        expected = {
            "hollow_hill_small": {
                "minecraft:wheat",
                "minecraft:string",
                "minecraft:bucket",
                "minecraft:torch",
                "minecraft:arrow",
                "minecraft:gunpowder",
                "minecraft:iron_pickaxe",
                "minecraft:diamond",
            },
            "hollow_hill_medium": {
                "minecraft:carrot",
                "minecraft:ladder",
                "minecraft:baked_potato",
                "minecraft:diamond",
                "minecraft:emerald",
            },
            "hollow_hill_large": {
                "minecraft:gold_nugget",
                "minecraft:potato",
                "minecraft:cod",
                "tf_slice:torchberries",
                "minecraft:pumpkin_pie",
                "minecraft:diamond",
                "minecraft:emerald",
            },
        }
        for loot_id, required_items in expected.items():
            table = load_json(
                BP / "loot_tables" / "chests" / "tf_slice" / ("%s.json" % loot_id)
            )
            item_ids = {
                entry["name"]
                for pool in table["pools"]
                for entry in pool.get("entries", [])
            }
            self.assertTrue(required_items.issubset(item_ids), loot_id)

    def test_mcstructures_embed_loot_tables_and_structure_specific_spawners(self):
        structure_root = BP / "structures" / "tf_slice" / "ruins"

        def folder_bytes(folder):
            return b"".join(
                path.read_bytes()
                for path in sorted((structure_root / folder).rglob("*.mcstructure"))
            )

        self.assertIn(b"loot_tables/chests/tf_slice/well.json", folder_bytes("well"))
        self.assertIn(b"tf_slice:skeleton_druid", folder_bytes("druid_hut"))
        self.assertIn(b"tf_slice:swarm_spider", folder_bytes("hollow_tree"))

        graveyard = folder_bytes("graveyard")
        self.assertIn(b"loot_tables/chests/tf_slice/graveyard.json", graveyard)
        self.assertIn(b"tf_slice:rising_zombie", graveyard)

        hedge = folder_bytes("hedge_maze")
        self.assertIn(b"tf_slice:hedge_spider", hedge)
        self.assertIn(b"tf_slice:hostile_wolf", hedge)

        hills = folder_bytes("hollow_hill")
        self.assertIn(b"tf_slice:redcap", hills)
        self.assertIn(b"minecraft:mob_spawner", hills)
        for entity_id in (
            "tf_slice:wraith",
            "tf_slice:slime_beetle",
            "tf_slice:fire_beetle",
            "tf_slice:pinch_beetle",
        ):
            self.assertIn(entity_id, structure_builder.HOLLOW_HILL_MOBS[3])


if __name__ == "__main__":
    unittest.main()
