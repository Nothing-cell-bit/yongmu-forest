"""Head-slot, mounting and native-use regressions for trophy wearables."""

import copy
import sys
import textwrap
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest import TestCase, mock

from tools import build_public_block_shapes as builder

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "TwilightBossSliceB"))
from TwilightBossSlice import public_block_logic, portal_logic


class TrophyWearableTests(TestCase):
    def test_held_model_gate_uses_real_head_equipment_not_unavailable_slot_context(self):
        for name in builder.TROPHY_SPECS:
            attachment = builder.trophy_attachable_document(name)["minecraft:attachable"]["description"]
            predicate = attachment["item"][attachment["identifier"]]
            self.assertNotIn("context.item_slot", predicate)
            self.assertIn("query.is_item_name_any('slot.armor.head'", predicate)
            self.assertNotIn("slot.weapon.mainhand", predicate)
            self.assertNotIn("slot.weapon.offhand", predicate)

    def test_every_trophy_keeps_stackable_items_and_binds_worn_models(self):
        for name in builder.TROPHY_SPECS:
            with self.subTest(trophy=name):
                item = builder.trophy_item_document(name)["minecraft:item"]
                comp = item["components"]
                self.assertEqual({"slot": "slot.armor.head", "protection": 0}, comp.get("minecraft:wearable"))
                self.assertEqual(64, comp["minecraft:max_stack_size"])
                self.assertNotIn("minecraft:durability", comp)
                self.assertEqual("tf_slice:" + name + "_trophy", comp["minecraft:block_placer"]["block"])
                attachment = builder.trophy_attachable_document(name)["minecraft:attachable"]["description"]
                self.assertEqual(item["description"]["identifier"], attachment["identifier"])
                worn = "query.is_item_name_any('slot.armor.head', '%s')" % item["description"]["identifier"]
                self.assertEqual(worn, attachment["item"][attachment["identifier"]])
                self.assertEqual([{"controller.render.armor": worn}], attachment["render_controllers"])
                self.assertNotIn("context.item_slot", str(attachment), "unsupported in item predicates on NetEase 3.8")

    def test_stack_refresh_keeps_64_and_never_equips_a_held_item(self):
        self._check_stack_refresh(mutate_dictionary=True)

    def test_successful_native_stack_override_is_written_back_even_if_dictionary_is_unchanged(self):
        self._check_stack_refresh(mutate_dictionary=False)

    def _check_stack_refresh(self, mutate_dictionary):
        source = (ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py").read_text("utf-8")
        self.assertTrue("    def _refresh_trophy_stack_sizes(" in source, "missing stack override")
        method = source[source.index("    def _refresh_trophy_stack_sizes("):]
        method = method[:method.index("\n    def ", 1)]
        factory = mock.Mock()
        slots = [
            {"itemName": "tf_slice:naga_trophy_item", "count": 32, "userData": {"custom": "preserve"}},
            {"itemName": "minecraft:diamond_helmet", "count": 1},
            None,
        ]
        comp = factory.CreateItem.return_value
        comp.GetPlayerAllItems.side_effect = lambda pos, data: copy.deepcopy(slots)
        comp.GetPlayerItem.side_effect = lambda pos, index, data: copy.deepcopy(slots[index])
        def resize(item, size):
            if mutate_dictionary:
                item.setdefault("userData", {})["ModMaxStackSize"] = size
            return True
        comp.SetMaxStackSize.side_effect = resize
        def write(updates):
            for (pos, index), item in updates.items():
                self.assertEqual("inventory", pos, "refresh must not write armor")
                slots[index] = copy.deepcopy(item)
            return {key: True for key in updates}
        comp.SetPlayerAllItems.side_effect = write
        api = SimpleNamespace(GetMinecraftEnum=lambda: SimpleNamespace(ItemPosType=SimpleNamespace(INVENTORY="inventory")))
        namespace = {"copy": copy, "CF": factory, "serverApi": api, "public_block_logic": public_block_logic, "portal_logic": portal_logic}
        exec(textwrap.dedent(method), namespace)
        player = SimpleNamespace(_pending_trophy_stack_refresh={"player"})
        namespace["_refresh_trophy_stack_sizes"](player, "player")
        self.assertEqual(32, slots[0]["count"])
        expected_data = {"custom": "preserve"}
        if mutate_dictionary:
            expected_data["ModMaxStackSize"] = 64
        self.assertEqual(expected_data, slots[0]["userData"])
        comp.SetPlayerAllItems.assert_called_once()
        self.assertEqual({"itemName": "minecraft:diamond_helmet", "count": 1}, slots[1])
        comp.SetPlayerAllItems.reset_mock()
        namespace["_refresh_trophy_stack_sizes"](player, "player")
        comp.SetPlayerAllItems.assert_not_called()

    def test_selecting_a_hotbar_trophy_only_queues_stack_configuration(self):
        source = (ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py").read_text("utf-8")
        factory = mock.Mock()
        namespace = {"CF": factory, "LEVEL_ID": "level", "portal_logic": portal_logic, "public_block_logic": public_block_logic}
        player = SimpleNamespace(_refresh_trophy_stack_sizes=mock.Mock(), _try_equip_trophy=mock.Mock(), _queue_trophy_equip=mock.Mock())
        for name in ("_queue_trophy_stack_refresh", "OnTrophyStackItemEvent"):
            method = source[source.index("    def " + name + "("):]
            exec(textwrap.dedent(method[:method.index("\n    def ", 1)]), namespace)
            setattr(player, name, MethodType(namespace[name], player))
        event = {"playerId": "player", "newItemDict": {"itemName": "tf_slice:naga_trophy_item", "count": 64}}
        player._trophy_stack_snapshots = {"player": {0: {"itemName": "tf_slice:naga_trophy_item"}}}
        player.OnTrophyStackItemEvent(event)
        player.OnTrophyStackItemEvent(event)
        self.assertIn("player", player._trophy_stack_snapshots)
        factory.CreateGame.return_value.AddTimer.assert_called_once_with(0.05, player._refresh_trophy_stack_sizes, "player")
        player._try_equip_trophy.assert_not_called()
        player._queue_trophy_equip.assert_not_called()
        self.assertNotIn("cancel", event)
        player.OnTrophyStackItemEvent({"actor": "player", "itemDict": event["newItemDict"]})
        self.assertNotIn("player", player._trophy_stack_snapshots)
        player._try_equip_trophy.assert_not_called()

    def test_head_core_covers_skin_and_protrusions_do_not_shift_the_mount(self):
        sources = builder.trophy_geometry_document()["minecraft:geometry"]
        for source in sources:
            name = source["description"]["identifier"].removeprefix("geometry.tf_slice.").removesuffix("_trophy")
            with self.subTest(trophy=name):
                before = copy.deepcopy(source)
                wearable = builder._wearable_trophy_geometry(name, source)
                self.assertEqual(before, source)
                bones = {bone["name"]: bone for bone in wearable["bones"]}
                self.assertEqual("'head'", bones["trophy_mount"].get("binding"))
                self.assertEqual([0, 24, 0], bones["trophy_mount"]["pivot"])
                self.assertEqual("trophy_mount", bones["trophy_root"]["parent"])
                core_name = "trophy_body" if name == "ur_ghast" else "trophy_head"
                core = bones[core_name]["cubes"][0]
                center = [core["origin"][axis] + core["size"][axis] / 2 for axis in range(3)]
                self.assertEqual([0, 27.5 if name == "ur_ghast" else 28, 0], center)
                for axis, (low, high) in enumerate(((-4, 4), (24, 32), (-4, 4))):
                    self.assertLessEqual(core["origin"][axis] - core.get("inflate", 0), low)
                    self.assertGreaterEqual(core["origin"][axis] + core["size"][axis] + core.get("inflate", 0), high)
                for bone in bones.values():
                    if bone["name"] != "trophy_mount":
                        self.assertIn(bone["parent"], bones)

    def test_worn_ghast_animation_resolves_to_wearable_bones(self):
        document = builder.trophy_wearable_animation_document()["animations"]
        animation = document["animation.tf_slice.trophy_wearable.ur_ghast_idle"]
        self.assertEqual(36, len(animation["bones"]))
        self.assertTrue(all(name.startswith("trophy_tentacle_") for name in animation["bones"]))
        hidden = document["animation.tf_slice.trophy_wearable.hide_first_person"]
        self.assertEqual({"trophy_root": {"scale": [0, 0, 0]}}, hidden["bones"])
        self.assertNotIn("head", hidden["bones"], "must not animate the player's head itself")

    def _equip_harness(self, head=None, failures=()):
        path = ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py"
        source = path.read_text("utf-8")
        self.assertTrue("    def _try_equip_trophy(" in source, "missing equip handler")
        method = source[source.index("    def _try_equip_trophy("):]
        method = method[:method.index("\n    def ", 1)]
        factory = mock.Mock()
        slots = {("carried", 0): {"itemName": "tf_slice:naga_trophy_item", "count": 64, "extraId": "named", "userData": {"test": 1}}, ("armor", 0): copy.deepcopy(head)}
        item_comp = factory.CreateItem.return_value
        item_comp.GetPlayerItem.side_effect = lambda pos, index, data: copy.deepcopy(slots[(pos, index)])
        def write(updates):
            result = {}
            for key, value in updates.items():
                result[key] = key not in failures
                if result[key]:
                    slots[key] = copy.deepcopy(value)
            return result
        item_comp.SetPlayerAllItems.side_effect = write
        api = SimpleNamespace(GetMinecraftEnum=lambda: SimpleNamespace(ItemPosType=SimpleNamespace(ARMOR="armor", CARRIED="carried")))
        namespace = {"CF": factory, "serverApi": api, "copy": copy, "public_block_logic": public_block_logic, "portal_logic": portal_logic}
        exec(textwrap.dedent(method), namespace)
        event = {"playerId": "player", "itemDict": copy.deepcopy(slots[("carried", 0)])}
        return namespace["_try_equip_trophy"], factory, slots, event

    def test_air_use_moves_one_and_preserves_metadata_without_replacing_helmet(self):
        for name in builder.TROPHY_SPECS:
            for head in (None, {"itemName": "minecraft:diamond_helmet", "count": 1}):
                equip, factory, slots, event = self._equip_harness(head)
                slots[("carried", 0)]["itemName"] = "tf_slice:" + name + "_trophy_item"
                event["itemDict"] = copy.deepcopy(slots[("carried", 0)])
                self.assertTrue(equip(SimpleNamespace(), event))
                self.assertTrue(event["cancel"])
                self.assertEqual(64 if head else 63, slots[("carried", 0)]["count"])
                if head:
                    self.assertEqual(head, slots[("armor", 0)])
                    factory.CreateItem.return_value.SetPlayerAllItems.assert_not_called()
                else:
                    self.assertEqual(1, slots[("armor", 0)]["count"])
                    self.assertEqual("named", slots[("armor", 0)]["extraId"])
                    self.assertEqual({"test": 1}, slots[("armor", 0)]["userData"])

    def test_partial_inventory_failure_restores_the_successful_half(self):
        for failed in (("carried", 0), ("armor", 0)):
            equip, factory, slots, event = self._equip_harness(failures=(failed,))
            before = copy.deepcopy(slots)
            self.assertTrue(equip(SimpleNamespace(), event))
            self.assertEqual(before, slots)

    def test_stale_or_cancelled_events_cannot_equip_a_different_hand_item(self):
        for cancelled in (False, True):
            equip, factory, slots, event = self._equip_harness()
            if cancelled:
                event["cancel"] = True
            else:
                slots[("carried", 0)]["itemName"] = "minecraft:stone"
            before = copy.deepcopy(slots)
            equip(SimpleNamespace(), event)
            self.assertEqual(before, slots)
            factory.CreateItem.return_value.SetPlayerAllItems.assert_not_called()

    def test_single_remaining_trophy_empties_the_hand(self):
        equip, factory, slots, event = self._equip_harness()
        slots[("carried", 0)]["count"] = 1
        event["itemDict"]["count"] = 1
        equip(SimpleNamespace(), event)
        self.assertIsNone(slots[("carried", 0)])
        self.assertEqual(1, slots[("armor", 0)]["count"])

    def test_exception_after_partial_write_is_reconciled_without_duplication(self):
        equip, factory, slots, event = self._equip_harness()
        comp = factory.CreateItem.return_value
        normal_write = comp.SetPlayerAllItems.side_effect
        def fail_once(updates):
            key = ("armor", 0)
            slots[key] = copy.deepcopy(updates[key])
            comp.SetPlayerAllItems.side_effect = normal_write
            raise RuntimeError("partial native write")
        comp.SetPlayerAllItems.side_effect = fail_once
        before = copy.deepcopy(slots)
        equip(SimpleNamespace(), event)
        self.assertEqual(before, slots)

    def test_block_use_wins_in_either_event_order_and_air_click_equips_once(self):
        source = (ROOT / "TwilightBossSliceB/TwilightBossSlice/serverSystem.py").read_text("utf-8")
        factory = mock.Mock()
        namespace = {"copy": copy, "CF": factory, "LEVEL_ID": "level", "portal_logic": portal_logic, "public_block_logic": public_block_logic}
        for name in ("_queue_trophy_equip", "_finish_trophy_equip", "_mark_trophy_block_use"):
            self.assertTrue("    def " + name + "(" in source)
            method = source[source.index("    def " + name + "("):]
            exec(textwrap.dedent(method[:method.index("\n    def ", 1)]), namespace)
        for order in ("before", "after", "air"):
            with self.subTest(order=order):
                player = SimpleNamespace(_tick=100, _try_equip_trophy=mock.Mock())
                for name in ("_queue_trophy_equip", "_finish_trophy_equip", "_mark_trophy_block_use"):
                    setattr(player, name, MethodType(namespace[name], player))
                factory.reset_mock()
                event = {"playerId": "player", "itemDict": {"itemName": "tf_slice:naga_trophy_item", "count": 64}}
                block_event = {"entityId": "player"}
                if order == "before":
                    player._mark_trophy_block_use(block_event, "tf_slice:naga_trophy_item")
                player._queue_trophy_equip(event)
                player._queue_trophy_equip(dict(event, cancel=False))
                self.assertEqual(1, factory.CreateGame.return_value.AddTimer.call_count)
                if order == "after":
                    player._mark_trophy_block_use(block_event, "tf_slice:naga_trophy_item")
                delay, callback, request = factory.CreateGame.return_value.AddTimer.call_args.args
                callback(request)
                callback(request)
                self.assertEqual(1 if order == "air" else 0, player._try_equip_trophy.call_count)
                self.assertNotIn("ret", block_event, "block placement must not be cancelled")
                self.assertEqual({}, player._pending_trophy_equips)
