"""Exercise real event handlers against a small world, without starting Minecraft."""
import ast
import json
import random
import re
import runpy
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "TwilightBossSliceB/TwilightBossSlice"
PLANTS = (
    "mushgloom", "fiddlehead", "mayapple", "fallen_leaves", "root_strand",
    "torchberry_plant", "torchberry_plant_empty", "huge_water_lily",
    "huge_lily_pad", "huge_lily_pad_nw", "huge_lily_pad_ne",
    "huge_lily_pad_sw", "huge_lily_pad_se",
)
FULL_BOX = {"min": (0, 0, 0), "max": (1, 1, 1)}


def load_runtime():
    path = SCRIPTS / "plant_support_logic.py"
    logic = types.SimpleNamespace(**runpy.run_path(str(path))) if path.exists() else None
    source = (SCRIPTS / "serverSystem.py").read_text(encoding="utf-8")
    names = (
        "_plant_support_status", "_check_plant_support", "_block_event_position",
        "OnBlockNeighborChanged", "OnBlockRandomTickServerEvent",
        "OnServerEntityTryPlaceBlockEvent",
        "OnEntityPlaceBlockAfterServerEvent", "_initialize_placed_firefly",
    )
    chunks = []
    for name in names:
        match = re.search(r"^    def " + name + r"\(", source, re.M)
        if match:
            end = re.search(r"^    (?:def |@)", source[match.end():], re.M)
            chunk = source[match.start():match.end() + end.start() if end else len(source)]
            chunks.append(("    @staticmethod\n" if name == "_block_event_position" else "") + chunk)
    namespace = {
        "plant_support_logic": logic,
        "random": random,
        "config": types.SimpleNamespace(PORTAL_IDENTIFIER="tf_slice:twilight_portal"),
        "banister_logic": types.SimpleNamespace(is_banister=lambda name: False),
        "leaf_decay_logic": types.SimpleNamespace(sapling_feature=lambda name: None, is_decayable_leaf=lambda name: False),
        "fire_swamp_logic": types.SimpleNamespace(DEVICE_BLOCKS=()),
        "public_block_logic": types.SimpleNamespace(
            trophy_block_for_face=lambda *a: None),
        "vanilla_block_adapter_logic": types.SimpleNamespace(adapt_placement_event=lambda args: None),
        "HUGE_LILY_PAD_BLOCK": "tf_slice:huge_lily_pad",
        "TROPHY_BLOCKS": (),
    }
    exec("class Runtime:\n" + "".join(chunks), namespace)
    return namespace["Runtime"], logic


class PlantRuntimeTests(unittest.TestCase):
    def setUp(self):
        runtime, self.logic = load_runtime()
        self.system = runtime()
        self.pos = (10, 65, 20)
        self.world = {self.pos: {"name": "tf_slice:mushgloom"}}
        self.writes, self.drops = [], []
        self.box = FULL_BOX
        self.write_success = True
        self.system._get_block = lambda pos, dim: self.world.get(pos, {"name": "minecraft:air"})
        self.system._block_name = lambda block: (block or {}).get("name", "")
        self.system._set_block = self.set_block
        self.update_flags = []
        self.system._block_comp = types.SimpleNamespace(
            GetBlockCollision=lambda *a: self.box,
            SetBlockNew=self.engine_set_block,
        )
        self.system.CreateEngineItemEntity = lambda *a: self.drops.append(a)
        self.system._protect_locked_lich_tower = lambda args: False
        self.system._get_dimension = lambda player: 7
        self.states = {"tf_slice:facing": "north"}
        self.system._block_state_comp = types.SimpleNamespace(
            GetBlockStates=lambda *args: self.states.copy(),
            SetBlockStates=self.set_states,
        )

    def set_states(self, pos, states, dim):
        self.states = states
        return True

    def set_block(self, pos, name, dim):
        if not self.write_success:
            return False
        self.writes.append((pos, name, dim))
        self.world[pos] = {"name": name}
        return True

    def engine_set_block(self, pos, block, handling, dim, legacy, update):
        self.update_flags.append(update)
        changed = self.set_block(pos, block["name"], dim)
        if changed and update:
            below = (pos[0], pos[1] - 1, pos[2])
            name = self.world.get(below, {}).get("name", "")
            if name.startswith("tf_slice:"):
                self.system.OnBlockNeighborChanged(dict(
                    blockName=name, position=below, dimensionId=dim))
        return changed

    def event(self, name="mushgloom"):
        return {"blockName": "tf_slice:" + name, "x": 10, "y": 65, "z": 20, "dimensionId": 7}

    def support(self, name, above=False):
        self.world[(10, 66 if above else 64, 20)] = {"name": name} if name is not None else None

    def test_removed_ground_breaks_mushgloom_once(self):
        self.system.OnBlockNeighborChanged(self.event())
        self.system.OnBlockNeighborChanged(self.event())
        self.assertEqual([(self.pos, "minecraft:air", 7)], self.writes)
        self.assertEqual(1, len(self.drops))

    def test_root_chain_detaches_without_waiting_for_random_ticks(self):
        self.world = {
            (10, y, 20): {"name": "tf_slice:root_strand"}
            for y in (63, 64, 65)
        }
        self.system.OnBlockNeighborChanged(self.event("root_strand"))
        self.assertEqual(3, len(self.writes))
        self.assertTrue(all(self.update_flags))

    def test_drop_contents_follow_plant_state(self):
        for name, item in (
            ("torchberry_plant", "tf_slice:torchberries"),
            ("torchberry_plant_empty", None), ("root_strand", "minecraft:stick"),
            ("huge_lily_pad_ne", None), ("huge_lily_pad_nw", "tf_slice:huge_lily_pad"),
        ):
            with self.subTest(plant=name):
                self.world = {self.pos: {"name": "tf_slice:" + name}}
                self.drops.clear()
                self.system.OnBlockNeighborChanged(self.event(name))
                self.assertEqual([item] if item else [], [entry[0]["newItemName"] for entry in self.drops])

    def test_all_affected_plants_are_cleaned_on_random_tick(self):
        for name in PLANTS:
            with self.subTest(plant=name):
                self.world = {self.pos: {"name": "tf_slice:" + name}}
                self.system.OnBlockRandomTickServerEvent(self.event(name))
                self.assertEqual("minecraft:air", self.world[self.pos]["name"])

    def test_mushgloom_cannot_be_placed_against_a_wall_above_air(self):
        args = self.event()
        args.update(playerId="player", face=2)
        self.system.OnServerEntityTryPlaceBlockEvent(args)
        self.assertTrue(args.get("cancel"))
        self.assertFalse(args.get("ret", True))
        self.assertFalse(self.writes)

    def test_solid_stone_glass_and_top_slab_support_mushgloom(self):
        for name, box in (
            ("minecraft:stone", FULL_BOX), ("minecraft:glass", FULL_BOX),
            ("minecraft:stone_slab", {"min": (0, .5, 0), "max": (1, 1, 1)}),
        ):
            self.support(name)
            self.box = box
            self.system.OnBlockNeighborChanged(self.event())
        self.assertFalse(self.writes)

    def test_bottom_slab_does_not_support_a_floating_mushroom(self):
        self.support("minecraft:stone_slab")
        self.box = {"min": (0, 0, 0), "max": (1, .5, 1)}
        self.system.OnBlockNeighborChanged(self.event())
        self.assertEqual(1, len(self.writes))

    def test_unknown_support_does_not_delete_existing_plant(self):
        for block, box in ((None, FULL_BOX), ("minecraft:stone", None), ("minecraft:stone", {})):
            self.support(block)
            self.box = box
            self.system.OnBlockNeighborChanged(self.event())
        self.assertFalse(self.writes)

    def test_support_api_errors_defer_removal(self):
        self.support("minecraft:stone")
        def unavailable(*args):
            raise RuntimeError("chunk unloaded")
        self.system._block_comp.GetBlockCollision = unavailable
        self.system.OnBlockNeighborChanged(self.event())
        self.assertFalse(self.writes)

    def test_set_api_errors_do_not_drop(self):
        def unavailable(*args):
            raise RuntimeError("chunk unloaded")
        self.system._block_comp.SetBlockNew = unavailable
        self.system.OnBlockNeighborChanged(self.event())
        self.assertFalse(self.drops)

    def test_failed_write_does_not_drop_items(self):
        self.write_success = False
        self.system.OnBlockNeighborChanged(self.event())
        self.assertFalse(self.drops)

    def test_event_does_not_delete_replacement_block(self):
        self.world[self.pos] = {"name": "minecraft:stone"}
        self.system.OnBlockNeighborChanged(self.event())
        self.assertFalse(self.writes)

    def test_hanging_plants_keep_ceiling_and_roots_keep_chains(self):
        for name, ceiling in (("root_strand", "tf_slice:root_strand"), ("torchberry_plant", "minecraft:stone")):
            self.world = {self.pos: {"name": "tf_slice:" + name}}
            self.support(ceiling, above=True)
            self.system.OnBlockNeighborChanged(self.event(name))
        self.assertFalse(self.writes)

    def test_water_supports_aquatic_plants_and_fallen_leaves(self):
        for name in ("huge_water_lily", "huge_lily_pad", "fallen_leaves"):
            self.world = {self.pos: {"name": "tf_slice:" + name}}
            self.support("minecraft:water")
            self.system.OnBlockNeighborChanged(self.event(name))
        self.assertFalse(self.writes)

    def test_firefly_stays_when_its_wall_is_removed(self):
        for facing, offset in (("north", (0, 0, 1)), ("south", (0, 0, -1)), ("west", (1, 0, 0)), ("east", (-1, 0, 0))):
            with self.subTest(facing=facing):
                self.writes.clear()
                self.drops.clear()
                self.states = {"tf_slice:facing": facing}
                wall = tuple(self.pos[i] + offset[i] for i in range(3))
                self.world = {self.pos: {"name": "tf_slice:firefly"}, wall: {"name": "minecraft:log"}}
                self.system.OnBlockNeighborChanged(self.event("firefly"))
                self.assertFalse(self.writes)
                self.world[wall] = {"name": "minecraft:air"}
                self.system.OnBlockNeighborChanged(self.event("firefly"))
                self.assertFalse(self.writes)
                self.assertFalse(self.drops)

    def test_firefly_missing_wall_allows_placement(self):
        args = self.event("firefly")
        args["face"] = 5
        self.system.OnServerEntityTryPlaceBlockEvent(args)
        self.assertFalse(args.get("cancel", False))

    def test_firefly_placement_sets_clicked_wall_direction(self):
        for face, facing, offset in ((2, "north", (0, 0, 1)), (3, "south", (0, 0, -1)), (4, "west", (1, 0, 0)), (5, "east", (-1, 0, 0))):
            self.world = {self.pos: {"name": "tf_slice:firefly"}}
            self.world[tuple(self.pos[i] + offset[i] for i in range(3))] = {"name": "minecraft:log"}
            args = self.event("firefly")
            args["face"] = face
            self.system.OnServerEntityTryPlaceBlockEvent(args)
            self.assertFalse(args.get("cancel", False))
            self.system.OnEntityPlaceBlockAfterServerEvent(args)
            self.assertEqual(facing, self.states["tf_slice:facing"])

    def test_firefly_placement_has_no_attachment_face_restriction(self):
        for face in (0, 1, None, "bad"):
            args = self.event("firefly")
            args["face"] = face
            self.system.OnServerEntityTryPlaceBlockEvent(args)
            self.assertFalse(args.get("cancel", False))

    def test_firefly_existing_unreadable_state_is_preserved(self):
        self.world = {self.pos: {"name": "tf_slice:firefly"}}
        self.states = {}
        self.system.OnBlockNeighborChanged(self.event("firefly"))
        self.assertFalse(self.writes)


class PlantPackTests(unittest.TestCase):
    def test_every_affected_plant_receives_neighbor_and_random_ticks(self):
        for name in PLANTS:
            with self.subTest(plant=name):
                document = json.loads((ROOT / "TwilightBossSliceB/netease_blocks" / (name + ".json")).read_text(encoding="utf-8"))
                components = document["minecraft:block"]["components"]
                self.assertEqual({"value": True}, components.get("netease:neighborchanged_sendto_script"))
                self.assertEqual({"enable": True, "tick_to_script": True}, components.get("netease:random_tick"))

    def test_swamp_builder_preserves_plant_update_components(self):
        tree = ast.parse((ROOT / "tools/build_swamp_features.py").read_text(encoding="utf-8"))
        for function in tree.body:
            if isinstance(function, ast.FunctionDef) and function.name in (
                "lily_quadrant_block", "huge_lily_pad_block", "huge_water_lily_block"
            ):
                namespace = {}
                exec(compile(ast.Module(body=[function], type_ignores=[]), "swamp", "exec"), namespace)
                args = ("huge_lily_pad_nw",) if function.name == "lily_quadrant_block" else ()
                components = namespace[function.name](*args)["minecraft:block"]["components"]
                self.assertEqual({"value": True}, components.get("netease:neighborchanged_sendto_script"))
                self.assertEqual({"enable": True, "tick_to_script": True}, components.get("netease:random_tick"))


class PlantRuleTests(unittest.TestCase):
    def setUp(self):
        self.logic = types.SimpleNamespace(**runpy.run_path(str(SCRIPTS / "plant_support_logic.py")))

    def test_substrate_matrix(self):
        cases = (
            ("fiddlehead", "minecraft:dirt", True),
            ("mayapple", "tf_slice:landmark_protected_grass", True),
            ("mayapple", "minecraft:stone", False),
            ("mushgloom", "minecraft:air", False),
            ("mushgloom", "minecraft:lava", False),
            ("mushgloom", "minecraft:water", False),
            ("mushgloom", "tf_slice:fiddlehead", False),
            ("mushgloom", "minecraft:glass", None),
            ("mushgloom", "", None),
            ("huge_water_lily", "minecraft:flowing_water", True),
            ("huge_water_lily", "minecraft:stone", False),
        )
        for plant, support, expected in cases:
            self.assertIs(expected, self.logic.named_support("tf_slice:" + plant, support))

    def test_supporting_faces_and_unreadable_collision(self):
        for box in (None, {}, {"min": None}, {"min": [0], "max": [1]}, {"min": ["bad"], "max": [1]}):
            self.assertIsNone(self.logic.collision_support("tf_slice:mushgloom", box))
        self.assertTrue(self.logic.collision_support("tf_slice:root_strand", FULL_BOX))
        self.assertFalse(self.logic.collision_support("tf_slice:root_strand", {"min": [0, .5, 0], "max": [1, 1, 1]}))
        self.assertFalse(self.logic.collision_support("tf_slice:mushgloom", {"min": [.4, 0, .4], "max": [.6, 1.5, .6]}))


if __name__ == "__main__":
    unittest.main()
