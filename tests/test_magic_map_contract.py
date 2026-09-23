# -*- coding: utf-8 -*-
import json
import hashlib
import importlib.util
import pathlib
import unittest

from PIL import Image


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
RELEASE_METADATA_PATH = (
    BP / "TwilightBossSlice" / "release_metadata.py"
)
RELEASE_METADATA_SPEC = importlib.util.spec_from_file_location(
    "magic_map_release_metadata",
    str(RELEASE_METADATA_PATH),
)
RELEASE_METADATA = importlib.util.module_from_spec(RELEASE_METADATA_SPEC)
RELEASE_METADATA_SPEC.loader.exec_module(RELEASE_METADATA)
EXPECTED_PACK_VERSION = list(RELEASE_METADATA.PACK_VERSION)


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class MagicMapContentContractTests(unittest.TestCase):
    def test_landmark_icons_keep_the_unrotated_upstream_pixels(self):
        expected_rgba_hashes = {
            "naga_courtyard": (
                "7c0e3b4988c9c8b0d4e9381d9babd843"
                "8334a1f7622c0fe0e2a70c2a8160963a"
            ),
            "lich_tower": (
                "2f3f8928826b3725e53c7e43c2c89465"
                "cc49c5baacde7898f78700c01fa0cd7c"
            ),
        }
        icon_root = (
            RP / "textures" / "ui" / "tf_slice" / "magic_map_icons"
        )
        for icon_name, expected_hash in expected_rgba_hashes.items():
            with Image.open(icon_root / (icon_name + ".png")) as image:
                rgba_hash = hashlib.sha256(
                    image.convert("RGBA").tobytes()
                ).hexdigest()
            self.assertEqual(expected_hash, rgba_hash, icon_name)

        importer = (
            ROOT / "tools" / "import_magic_map_assets.ps1"
        ).read_text(encoding="utf-8")
        self.assertNotIn("Rotate180FlipNone", importer)

    def test_items_and_recipes_cover_the_survival_chain(self):
        for item_name in (
            "magic_map_focus",
            "magic_map",
            "filled_magic_map",
        ):
            item = read_json(BP / "items" / ("%s.item.json" % item_name))
            description = item["minecraft:item"]["description"]
            self.assertEqual("tf_slice:%s" % item_name, description["identifier"])
            self.assertTrue(
                (RP / "textures" / "items" / ("%s.png" % item_name)).is_file()
            )

        focus_recipe = read_json(
            BP / "recipes" / "magic_map_focus.recipe.json"
        )["minecraft:recipe_shapeless"]
        self.assertEqual(
            {
                "tf_slice:raven_feather",
                "tf_slice:torchberries",
                "minecraft:glowstone_dust",
            },
            {
                ingredient["item"]
                for ingredient in focus_recipe["ingredients"]
            },
        )
        self.assertEqual(
            "tf_slice:magic_map_focus",
            focus_recipe["result"]["item"],
        )
        self.assertEqual(
            {"context": "AlwaysUnlocked"},
            focus_recipe["unlock"],
        )

        map_recipe = read_json(
            BP / "recipes" / "magic_map.recipe.json"
        )["minecraft:recipe_shaped"]
        self.assertEqual(["PPP", "PFP", "PPP"], map_recipe["pattern"])
        self.assertEqual("minecraft:paper", map_recipe["key"]["P"]["item"])
        self.assertEqual("tf_slice:magic_map_focus", map_recipe["key"]["F"]["item"])
        self.assertEqual("tf_slice:magic_map", map_recipe["result"]["item"])
        self.assertEqual(
            {"context": "AlwaysUnlocked"},
            map_recipe["unlock"],
        )

        for blank_count in range(1, 9):
            clone_recipe = read_json(
                BP
                / "recipes"
                / ("magic_map_cloning_%d.recipe.json" % blank_count)
            )["minecraft:recipe_shapeless"]
            ingredients = clone_recipe["ingredients"]
            self.assertEqual(
                1,
                sum(
                    entry["item"] == "tf_slice:filled_magic_map"
                    for entry in ingredients
                ),
            )
            self.assertEqual(
                blank_count,
                sum(
                    entry["item"] == "tf_slice:magic_map"
                    for entry in ingredients
                ),
            )
            self.assertEqual(
                blank_count + 1,
                clone_recipe["result"]["count"],
            )

    def test_resource_registration_exposes_items_and_fixed_magic_map_ui(self):
        textures = read_json(RP / "textures" / "item_texture.json")[
            "texture_data"
        ]
        for item_name in (
            "magic_map_focus",
            "magic_map",
            "filled_magic_map",
        ):
            self.assertIn("tf_slice:%s" % item_name, textures)

        ui_defs = read_json(RP / "ui" / "_ui_defs.json")["ui_defs"]
        self.assertIn("ui/magic_map.json", ui_defs)
        self.assertIn("ui/magic_map_hud.json", ui_defs)
        self.assertIn("ui/hud_screen.json", ui_defs)
        ui_source = (RP / "ui" / "magic_map.json").read_text(encoding="utf-8")
        ui_document = json.loads(ui_source)
        self.assertNotIn("mini_map.mini_map_wrapper", ui_source)
        self.assertIn('"is_showing_menu": true', ui_source)
        screen = ui_document["main"]
        self.assertEqual("screen", screen["type"])
        self.assertFalse(screen["always_accepts_input"])
        self.assertFalse(screen["force_render_below"])
        self.assertFalse(screen["should_steal_mouse"])
        parchment = screen["controls"][1]["parchment_frame"]
        self.assertEqual(
            "textures/ui/tf_slice/magic_map_frame_v2",
            parchment["texture"],
        )
        self.assertEqual([220, 218], parchment["size"])
        self.assertNotIn("nineslice_size", parchment)
        self.assertTrue(
            (
                RP
                / "textures"
                / "ui"
                / "tf_slice"
                / "magic_map_frame_v2.png"
            ).is_file()
        )
        parchment_controls = json.dumps(parchment["controls"])
        self.assertIn('"map_canvas"', parchment_controls)
        self.assertIn('"coordinates"', parchment_controls)
        map_canvas = parchment["controls"][1]["map_canvas"]
        self.assertEqual("image", map_canvas["type"])
        self.assertEqual([192, 192], map_canvas["size"])
        self.assertEqual("textures/ui/white", map_canvas["texture"])
        self.assertNotIn("uv", map_canvas)
        self.assertNotIn("uv_size", map_canvas)
        self.assertEqual([0.69, 0.57, 0.35], map_canvas["color"])
        self.assertIn("controls", map_canvas)
        close_button = parchment["controls"][3]["close_button"]
        self.assertEqual("button", close_button["type"])
        self.assertEqual("top_right", close_button["anchor_to"])
        self.assertEqual("X", close_button["controls"][0]["close_label"]["text"])
        conquered = ui_document["conquered_marker"]
        self.assertEqual("X", conquered["text"])
        self.assertEqual([0.78, 0.04, 0.03], conquered["color"])
        self.assertEqual("image", ui_document["player_marker"]["type"])
        self.assertEqual("image", ui_document["other_player_marker"]["type"])

        biome_keys = (
            "forest",
            "dense_forest",
            "oak_savannah",
            "mushroom_forest",
            "firefly_forest",
            "stream",
            "dense_mushroom_forest",
            "lake",
            "enchanted_forest",
            "clearing",
            "spooky_forest",
            "unknown",
            "swamp",
            "fire_swamp",
            "dark_forest",
            "dark_forest_center",
        )
        for biome_key in biome_keys:
            template = ui_document["biome_%s" % biome_key]
            self.assertEqual("image", template["type"])
            self.assertEqual("textures/ui/white", template["texture"])
            self.assertNotIn("uv", template)
            self.assertNotIn("uv_size", template)
            self.assertEqual(3, len(template["color"]))
            self.assertTrue(
                (
                    RP
                    / "textures"
                    / "ui"
                    / "tf_slice"
                    / "magic_map_palette"
                    / (biome_key + ".png")
                ).is_file(),
                biome_key,
            )

        # Match the upstream MagicMapItem MapColor + brightness palette.
        self.assertEqual([0.0, 0.42, 0.0], ui_document["biome_forest"]["color"])
        self.assertEqual(
            [0.0, 0.34, 0.0],
            ui_document["biome_dense_forest"]["color"],
        )
        self.assertEqual(
            [0.22, 0.22, 0.86],
            ui_document["biome_stream"]["color"],
        )
        self.assertEqual(
            [0.30, 0.50, 0.60],
            ui_document["biome_enchanted_forest"]["color"],
        )
        self.assertEqual(
            [0.773, 0.427, 0.729],
            ui_document["biome_unknown"]["color"],
        )
        self.assertEqual(
            [0.19, 0.45, 0.44],
            ui_document["biome_swamp"]["color"],
        )
        self.assertEqual(
            [0.38, 0.01, 0.0],
            ui_document["biome_fire_swamp"]["color"],
        )
        self.assertEqual(
            [0.207843, 0.258824, 0.105882],
            ui_document["biome_dark_forest"]["color"],
        )
        self.assertEqual(
            [0.439216, 0.258824, 0.105882],
            ui_document["biome_dark_forest_center"]["color"],
        )

        expected_palette_pixels = {
            "swamp": (48, 115, 112, 255),
            "fire_swamp": (97, 3, 0, 255),
            "dark_forest": (53, 66, 27, 255),
            "dark_forest_center": (112, 66, 27, 255),
        }
        palette_root = (
            RP / "textures" / "ui" / "tf_slice" / "magic_map_palette"
        )
        for biome_key, expected_pixel in expected_palette_pixels.items():
            with Image.open(palette_root / (biome_key + ".png")) as image:
                pixels = set(image.convert("RGBA").getdata())
            self.assertEqual({expected_pixel}, pixels, biome_key)

        generator = (
            ROOT / "tools" / "generate_magic_map_hud_pool.ps1"
        ).read_text(encoding="utf-8")
        for biome_key in expected_palette_pixels:
            self.assertIn("    %s = @(" % biome_key, generator)

        for icon_name in (
            "small_hill",
            "medium_hill",
            "large_hill",
            "hedge_maze",
            "naga_courtyard",
            "lich_tower",
            "ice_tower",
            "quest_grove",
            "hydra_lair",
            "labyrinth",
            "dark_tower",
            "knight_stronghold",
            "yeti_cave",
            "troll_cave",
            "final_castle",
        ):
            self.assertTrue(
                (
                    RP
                    / "textures"
                    / "ui"
                    / "tf_slice"
                    / "magic_map_icons"
                    / ("%s.png" % icon_name)
                ).is_file()
            )

    def test_held_map_uses_magic_map_pixels_without_right_click(self):
        hud = read_json(RP / "ui" / "magic_map_hud.json")
        self.assertEqual("magic_map_hud", hud["namespace"])
        hud_source = (
            RP / "ui" / "magic_map_hud.json"
        ).read_text(encoding="utf-8")
        self.assertNotIn("mini_map.mini_map_wrapper", hud_source)
        self.assertNotIn("native_map", hud_source)
        self.assertNotIn('"coordinates"', hud_source)
        screen = hud["main"]
        self.assertEqual("screen", screen["type"])
        self.assertFalse(screen["absorbs_input"])
        self.assertFalse(screen["is_showing_menu"])
        self.assertNotIn("held_map_root", hud)
        self.assertIn("held_map_root", screen["controls"][0])
        root = screen["controls"][0]["held_map_root"]
        self.assertEqual("bottom_middle", root["anchor_to"])
        # Native HUD controls exist before the Python proxy can bind. Default
        # hidden is the fail-safe that prevents an empty map from flashing or
        # remaining visible while the player is not holding one.
        self.assertFalse(root["visible"])
        frame = root["controls"][0]["parchment_frame"]
        self.assertEqual(
            "textures/map/map_background",
            frame["texture"],
        )
        self.assertNotIn("nineslice_size", frame)
        self.assertEqual([144, 144], frame["size"])
        map_canvas = frame["controls"][0]["map_canvas"]
        self.assertEqual("panel", map_canvas["type"])
        self.assertEqual([128, 128], map_canvas["size"])
        self.assertNotIn("texture", map_canvas)
        self.assertNotIn("color", map_canvas)
        self.assertNotIn("alpha", map_canvas)
        self.assertNotIn("uv", map_canvas)
        self.assertNotIn("uv_size", map_canvas)
        self.assertTrue(map_canvas["clips_children"])
        pool_controls = {
            next(iter(control)): next(iter(control.values()))
            for control in map_canvas["controls"]
        }
        self.assertIn("biome_bitmap_a", pool_controls)
        self.assertIn("biome_bitmap_b", pool_controls)
        self.assertIn("biome_bitmap_c", pool_controls)
        self.assertNotIn("biome_bitmap", pool_controls)
        self.assertNotIn("biome_pool", pool_controls)
        self.assertIn("landmark_pool", pool_controls)
        self.assertIn("conquered_pool", pool_controls)
        self.assertIn("player_pool", pool_controls)
        for slot in ("a", "b", "c"):
            bitmap = pool_controls["biome_bitmap_%s" % slot]
            binding_name = "#tf_magic_map_bitmap_path_%s" % slot
            self.assertEqual("image", bitmap["type"])
            self.assertEqual([128, 128], bitmap["size"])
            self.assertEqual("RawPath", bitmap["texture_file_system"])
            self.assertEqual(binding_name, bitmap["texture"])
            self.assertEqual(binding_name, bitmap["bindings"][0]["binding_name"])
            self.assertEqual(
                "#texture",
                bitmap["bindings"][0]["binding_name_override"],
            )
            self.assertEqual("always", bitmap["bindings"][0]["binding_condition"])
            self.assertTrue(bitmap["force_texture_reload"])
            self.assertFalse(bitmap["bilinear"])
            self.assertTrue(bitmap["pixel_perfect"])
            self.assertFalse(bitmap["visible"])
        landmark_slots = pool_controls["landmark_pool"]["controls"]
        conquered_slots = pool_controls["conquered_pool"]["controls"]
        other_player_slots = pool_controls["other_player_pool"]["controls"]
        self.assertNotIn("biome_slot_0000", hud_source)
        native_hud_source = (
            RP / "ui" / "hud_screen.json"
        ).read_text(encoding="utf-8")
        self.assertIn("biome_bitmap_a", native_hud_source)
        self.assertIn("biome_bitmap_b", native_hud_source)
        self.assertIn("biome_bitmap_c", native_hud_source)
        self.assertNotIn("biome_slot_0000", native_hud_source)
        self.assertGreaterEqual(len(landmark_slots), 128)
        self.assertGreaterEqual(len(conquered_slots), 64)
        self.assertGreaterEqual(len(other_player_slots), 64)
        player_pool = pool_controls["player_pool"]
        self.assertEqual(206, player_pool["layer"])
        player_controls = {
            next(iter(control)): next(iter(control.values()))
            for control in player_pool["controls"]
        }
        self.assertIn("held_player_marker_backdrop", player_controls)
        self.assertIn("held_player_marker", player_controls)
        held_player = player_controls["held_player_marker"]
        self.assertEqual("image", held_player["type"])
        self.assertEqual([8, 8], held_player["size"])
        self.assertEqual(
            "textures/ui/tf_slice/magic_map_player/north",
            held_player["texture"],
        )
        held_backdrop = player_controls["held_player_marker_backdrop"]
        self.assertEqual("image", held_backdrop["type"])
        self.assertEqual("textures/ui/white", held_backdrop["texture"])
        self.assertEqual([0.92, 0.16, 0.12], held_backdrop["color"])
        self.assertFalse(held_backdrop["visible"])
        for direction in ("north", "east", "south", "west", "off_map"):
            marker_path = (
                RP
                / "textures"
                / "ui"
                / "tf_slice"
                / "magic_map_player"
                / (direction + ".png")
            )
            self.assertTrue(marker_path.is_file())
            with Image.open(marker_path) as marker:
                self.assertEqual((8, 8), marker.size)
        self.assertEqual(200, root["layer"])
        self.assertEqual(200, frame["layer"])
        self.assertEqual(201, map_canvas["layer"])

        native_hud = read_json(RP / "ui" / "hud_screen.json")
        self.assertEqual("hud", native_hud["namespace"])
        modifications = native_hud["hud_content"]["modifications"]
        self.assertEqual("controls", modifications[0]["array_name"])
        self.assertEqual("insert_back", modifications[0]["operation"])
        native_root = modifications[0]["value"][0]["tf_magic_map"]
        self.assertEqual(root, native_root)
        self.assertNotIn(
            "@magic_map_hud.",
            json.dumps(modifications, ensure_ascii=False),
        )
        self.assertEqual(
            "panel",
            native_root["controls"][0]["parchment_frame"]["controls"][0][
                "map_canvas"
            ]["type"],
        )

        filled = read_json(
            BP / "items" / "filled_magic_map.item.json"
        )["minecraft:item"]["components"]
        self.assertTrue(filled["minecraft:allow_off_hand"])
        # International-style items/ does not reliably honor the legacy
        # netease:show_in_hand component.  The empty attachable below is the
        # deterministic first-person carrier instead.
        self.assertNotIn("netease:show_in_hand", filled)
        self.assertNotIn("minecraft:use_animation", filled)

    def test_biome_hud_rectangles_disable_texture_aspect_ratio(self):
        first_biome_slot = read_json(
            RP / "ui" / "magic_map.json"
        )["hud_biome"]

        # Biome runs are deliberately rectangular.  A square palette texture
        # must stretch to the control bounds instead of preserving 1:1 ratio,
        # otherwise each rectangle is reduced to a sparse line or dot.
        self.assertIn("keep_ratio", first_biome_slot)
        self.assertFalse(first_biome_slot["keep_ratio"])

    def test_scripts_keep_map_opening_server_authoritative(self):
        server = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        client = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        service = (
            BP / "TwilightBossSlice" / "structureWorldgenService.py"
        ).read_text(encoding="utf-8")
        config = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"ServerItemTryUseEvent"', server)
        self.assertIn('"CraftItemOutputChangeServerEvent"', server)
        self.assertIn('"UIContainerItemChangedServerEvent"', server)
        self.assertIn('"MagicMapOpenRequest"', server)
        self.assertIn('"MagicMapSnapshot"', server)
        self.assertIn('"MagicMapDelta"', server)
        self.assertIn("GetPlayerItem", server)
        self.assertIn(
            'playerId = args.get("playerId", args.get("entityId"))',
            server,
        )
        self.assertIn("def _magic_map_identity(", server)
        self.assertIn("tf_slice:magic_map_records_v2", config)
        self.assertIn("MAGIC_MAP_SCAN_INTERVAL_TICKS = 1", config)
        self.assertIn(
            "MAGIC_MAP_ITEM_RECONCILE_INTERVAL_TICKS = 10", config
        )
        self.assertIn(
            "MAGIC_MAP_CLIENT_RECONCILE_INTERVAL_TICKS = 30",
            config,
        )
        self.assertIn("MAGIC_MAP_SAMPLE_BUDGET = 13", config)
        self.assertIn("self._magic_map_discovery_frontiers = {}", server)
        self.assertIn("magic_map_logic.discovery_frontier_batch(", server)
        self.assertIn("def _tick_cached_magic_map_discovery(", server)
        self.assertIn("magic_map_landmarks_near", service)
        self.assertIn("BIOMES_BY_IDENTIFIER", server)
        self.assertIn("GetBiomeName", server)
        self.assertIn('"biomesPacked"', server)
        self.assertIn("decode_map_identity", server)
        self.assertIn("extra_id_version(rawExtraId) != 3", server)
        self.assertNotIn("ChangePlayerItemTipsAndExtraId", server)
        self.assertIn("_allocate_magic_map(", server)

        self.assertIn('"UiInitFinished"', client)
        self.assertIn("RegisterUI", client)
        self.assertIn("clientApi.GetUI(", client)
        self.assertIn("def _ensure_magic_map_ui(", client)
        self.assertIn("self._ensure_magic_map_ui()", client)
        self.assertIn("magicMapHudUI.is_active()", client)
        self.assertIn('"magic_map.main"', client)
        self.assertIn('"magic_map_hud.main"', client)
        self.assertIn("magicMapHudUI.MagicMapHudUI", client)
        self.assertIn('{"isHud": 1}', client)
        self.assertIn("GetNativeScreenManagerCls()", client)
        self.assertIn("RegisterScreenProxy(", client)
        self.assertIn('"hud.hud_screen"', client)
        self.assertIn("MagicMapHudProxy", client)
        self.assertIn("item_comp.GetCarriedItem", client)
        self.assertIn("item_comp.GetOffhandItem", client)
        self.assertIn('"OnCarriedNewItemChangedClientEvent"', client)
        self.assertIn("clientItemLogic.is_filled_magic_map(", client)
        stable_tick = client[
            client.index("    def OnScriptTickClient(self):") : client.index(
                "    def _spawn_naga_state_particle(",
            )
        ]
        self.assertIn("self._update_magic_map_hud()", stable_tick)
        self.assertIn('"openScreen": False', client)
        self.assertNotIn('"magic_map.magic_map_screen"', client)
        self.assertIn("PushScreen", client)
        self.assertIn('"MagicMapSnapshot"', client)
        self.assertIn('"MagicMapDelta"', client)
        self.assertIn('"MagicMapHeldState"', client)
        self.assertIn("def OnMagicMapHeldState(", client)
        self.assertIn("magicMapHudUI.set_snapshot(snapshot)", client)
        self.assertIn("magicMapHudUI.apply_delta(dict(args))", client)
        self.assertIn("def _set_magic_map_hud_visible(", client)
        self.assertIn("CF.CreatePlayerView(player_id).GetPerspective()", client)
        self.assertIn("clientItemLogic.should_show_held_map(", client)
        self.assertIn("clientItemLogic.resolve_held_map_state(", client)
        self.assertIn("schemaVersion != 3", client)
        self.assertNotIn("schemaVersion != 2", client)
        ui_init_handler = client[client.index(
            "    def OnUiInitFinished"
        ):client.index(
            "    def _ensure_lich_boss_hud"
        )]
        self.assertNotIn("bool(", ui_init_handler)
        self.assertIn("self._ensure_magic_map_ui()", ui_init_handler)
        ensure_magic_map_ui = client[client.index(
            "    def _ensure_magic_map_ui"
        ):client.index(
            "    def OnMagicMapSnapshot"
        )]
        self.assertIn(
            "self._magic_map_ui_ready = True",
            ensure_magic_map_ui,
        )

        use_handler = server[server.index(
            "    def OnServerItemTryUseEvent"
        ):server.index(
            "    def OnMagicMapOpenRequest"
        )]
        self.assertNotIn('args["cancel"] = True', use_handler)
        self.assertIn("itemName != config.MAGIC_MAP_ITEM", use_handler)
        self.assertIn("self._is_magic_map_stack(item)", use_handler)
        self.assertNotIn('"minecraft:empty_map"', use_handler)
        self.assertIn("_queue_blank_magic_map_use(", use_handler)
        self.assertIn("_queue_filled_magic_map_open(", use_handler)
        self.assertIn("def _complete_blank_magic_map_use(", server)
        self.assertIn("def _complete_filled_magic_map_open(", server)
        self.assertRegex(server, r"AddTimer\(\s*0\.05")

        replace_handler = server[server.index(
            "    def _replace_blank_magic_map"
        ):server.index(
            "    def _queue_blank_magic_map_use"
        )]
        self.assertNotIn("self._is_creative(", replace_handler)
        self.assertIn("self._filled_magic_map_item(extraId)", replace_handler)
        self.assertIn(
            "self._set_hand_item(playerId, hand, filledMap)",
            replace_handler,
        )
        filled_item_handler = server[server.index(
            "    def _filled_magic_map_item"
        ):server.index(
            "    def _deliver_item"
        )]
        self.assertIn(
            '"itemName": config.FILLED_MAGIC_MAP_ITEM',
            filled_item_handler,
        )
        self.assertNotIn("userData", filled_item_handler)
        self.assertNotIn("map_uuid", filled_item_handler)

        open_handler = client[client.index(
            "    def _open_magic_map"
        ):client.index(
            "    def _update_ambient_fireflies"
        )]
        self.assertIn("magicMapUI.set_snapshot(snapshot)", open_handler)
        self.assertNotIn("snapshot,", open_handler)

        map_ui = (
            BP / "TwilightBossSlice" / "magicMapUI.py"
        ).read_text(encoding="utf-8")
        self.assertIn("GetScreenNodeCls()", map_ui)
        self.assertIn("CreateChildControl(", map_ui)
        self.assertIn("BITMAP_RENDER_INTERVAL_TICKS = 6", map_ui)
        self.assertIn("BITMAP_RETENTION_TICKS = 120", map_ui)
        self.assertIn('BITMAP_BUFFER_SLOTS = ("a", "b", "c")', map_ui)
        self.assertIn("magic_map_bitmap_cache", map_ui)
        self.assertIn("GetViewBinderCls()", map_ui)
        self.assertIn("ViewBinder.BF_BindString", map_ui)
        self.assertIn('"#tf_magic_map_bitmap_path_a"', map_ui)
        self.assertIn('"#tf_magic_map_bitmap_path_b"', map_ui)
        self.assertIn('"#tf_magic_map_bitmap_path_c"', map_ui)
        self.assertIn("def _render_biome_bitmap(", map_ui)
        self.assertIn(
            '"/parchment_frame/map_canvas/biome_bitmap_a"',
            map_ui,
        )
        self.assertIn(
            '"/parchment_frame/map_canvas/biome_bitmap_b"',
            map_ui,
        )
        self.assertIn(
            '"/parchment_frame/map_canvas/biome_bitmap_c"',
            map_ui,
        )
        self.assertNotIn("budgeted_biome_rectangles", map_ui)
        self.assertIn("def ApplyDelta(", map_ui)
        self.assertIn("CF.CreateRot(playerId).GetRot()", map_ui)
        self.assertIn("canvas.GetSize()", map_ui)
        self.assertIn('"/parchment_frame/map_canvas"', map_ui)
        self.assertIn('"/parchment_frame/close_button"', map_ui)
        self.assertNotIn("GetMiniMapScreenNodeCls", map_ui)
        self.assertNotIn("AddStaticMarker", map_ui)

        map_hud = (
            BP / "TwilightBossSlice" / "magicMapHudUI.py"
        ).read_text(encoding="utf-8")
        self.assertIn("GetScreenNodeCls()", map_hud)
        self.assertNotIn("CreateChildControl(", map_hud)
        self.assertNotIn("RemoveChildControl(", map_hud)
        self.assertNotIn("BIOME_POOL_SIZE", map_hud)
        self.assertNotIn("BIOME_CREATE_BUDGET", map_hud)
        self.assertIn("BIOME_KEYS", map_hud)
        self.assertIn(
            "BIOME_KEYS = magic_map_logic.TWILIGHT_BIOME_KEYS",
            map_hud,
        )
        self.assertIn('"biomeRuns"', map_hud)
        self.assertIn("def _draw_biomes(", map_hud)
        self.assertIn("def _draw_landmarks(", map_hud)
        self.assertIn("def _draw_player(", map_hud)
        self.assertIn("CF.CreateRot(player_id).GetRot()", map_hud)
        self.assertIn("magic_map_logic.player_marker_direction", map_hud)
        self.assertIn("magic_map_logic.map_marker_position", map_hud)
        self.assertIn("magic_map_bitmap_cache", map_hud)
        self.assertIn("GetViewBinderCls()", map_hud)
        self.assertGreaterEqual(
            map_hud.count('"#tf_magic_map_bitmap_path_a"'),
            2,
        )
        self.assertGreaterEqual(
            map_hud.count('"#tf_magic_map_bitmap_path_b"'),
            2,
        )
        self.assertGreaterEqual(
            map_hud.count('"#tf_magic_map_bitmap_path_c"'),
            2,
        )
        self.assertIn("PLAYER_MARKER_TEXTURE_PATHS", map_hud)
        self.assertIn("self._player_backdrop_control", map_hud)
        self.assertIn('canvas_path + "/player_pool/held_player_marker"', map_hud)
        self.assertIn("backdrop.SetVisible(visible)", map_hud)
        self.assertIn("image.SetSprite(", map_hud)
        self.assertIn("BITMAP_RENDER_INTERVAL_TICKS = 6", map_hud)
        self.assertIn("BITMAP_RETENTION_TICKS = 120", map_hud)
        self.assertIn('BITMAP_BUFFER_SLOTS = ("a", "b", "c")', map_hud)
        self.assertIn("def _render_biome_bitmap(", map_hud)
        self.assertIn('canvas_path + "/biome_bitmap_a"', map_hud)
        self.assertIn('canvas_path + "/biome_bitmap_b"', map_hud)
        self.assertIn('canvas_path + "/biome_bitmap_c"', map_hud)
        retention_handler = map_hud[
            map_hud.index("    def _advance_bitmap_retention") :
            map_hud.index("    def GetBitmapPath", map_hud.index(
                "    def _advance_bitmap_retention"
            ))
        ]
        self.assertIn("SetAlpha(0.0)", retention_handler)
        self.assertNotIn("budgeted_biome_rectangles", map_hud)
        self.assertIn("def SetHeldVisible(", map_hud)
        self.assertIn("def is_active(", map_hud)
        self.assertIn("def Init(", map_hud)
        self.assertIn("GetUIScreenProxyCls()", map_hud)
        self.assertIn("class MagicMapHudProxy(", map_hud)
        self.assertIn("def OnCreate(", map_hud)
        self.assertIn("def OnTick(", map_hud)
        self.assertIn("def OnDestroy(", map_hud)
        self.assertIn("GetAllChildrenPath(", map_hud)
        self.assertIn('endswith("/tf_magic_map")', map_hud)
        self.assertIn("NATIVE_HUD_MAGIC_MAP_PATH", map_hud)
        self.assertIn(
            '"inner_matrix/safezone_screen_panel/'
            'root_screen_panel/tf_magic_map"',
            map_hud,
        )
        self.assertNotIn("GetMiniMapScreenNodeCls", map_hud)
        self.assertNotIn(".asMiniMap()", map_hud)
        self.assertNotIn("AddStaticMarker(", map_hud)
        self.assertNotIn("AddEntityMarker(", map_hud)
        self.assertNotIn("ZoomOut(", map_hud)

        map_screen_definition = read_json(RP / "ui" / "magic_map.json")
        for biome_key in (
            "forest",
            "dense_forest",
            "oak_savannah",
            "mushroom_forest",
            "firefly_forest",
            "stream",
            "dense_mushroom_forest",
            "lake",
            "enchanted_forest",
            "clearing",
            "spooky_forest",
            "unknown",
            "swamp",
            "fire_swamp",
            "dark_forest",
            "dark_forest_center",
        ):
            self.assertIn("biome_%s" % biome_key, map_screen_definition)
        screen_frame = map_screen_definition["main"]["controls"][1][
            "parchment_frame"
        ]
        screen_canvas = screen_frame["controls"][1]["map_canvas"]
        screen_bitmaps = {
            next(iter(control)): next(iter(control.values()))
            for control in screen_canvas["controls"]
        }
        for slot in ("a", "b", "c"):
            screen_bitmap = screen_bitmaps["biome_bitmap_%s" % slot]
            binding_name = "#tf_magic_map_bitmap_path_%s" % slot
            self.assertEqual("RawPath", screen_bitmap["texture_file_system"])
            self.assertEqual(binding_name, screen_bitmap["texture"])
            self.assertEqual(
                binding_name,
                screen_bitmap["bindings"][0]["binding_name"],
            )
            self.assertEqual(
                "#texture",
                screen_bitmap["bindings"][0]["binding_name_override"],
            )
            self.assertEqual(
                "always",
                screen_bitmap["bindings"][0]["binding_condition"],
            )
            self.assertTrue(screen_bitmap["force_texture_reload"])
            self.assertFalse(screen_bitmap["bilinear"])
            self.assertTrue(screen_bitmap["pixel_perfect"])
            self.assertFalse(screen_bitmap["visible"])
        self.assertIn(
            "BIOME_KEYS = magic_map_logic.TWILIGHT_BIOME_KEYS",
            map_ui,
        )
        bitmap_cache = (
            BP / "TwilightBossSlice" / "magic_map_bitmap_cache.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"unknown": (197, 109, 186, 255)', bitmap_cache)

        biome_handler_start = server.index("    def _magic_map_biome_key")
        biome_handler = server[
            biome_handler_start:server.index(
                "    def _discover_magic_map(",
                biome_handler_start,
            )
        ]
        self.assertIn("magic_map_logic.UNKNOWN_BIOME_KEY", biome_handler)
        self.assertIn("(blockX, 0, blockZ)", biome_handler)
        self.assertIn("def OnMagicMapCraftingInputChanged(", server)
        self.assertIn("def OnMagicMapCrafted(", server)
        self.assertIn("def _repair_cloned_magic_map(", server)
        self.assertIn("def _magic_map_player_markers(", server)
        self.assertIn('players = self._magic_map_player_markers(', server)
        self.assertIn('delta["players"] = players', server)
        self.assertIn("OTHER_PLAYER_POOL_SIZE = 64", map_hud)
        self.assertIn("def _draw_shared_players(", map_hud)
        self.assertIn("def _draw_shared_players(", map_ui)

        self.assertIn("def _send_magic_map_snapshot(", server)
        self.assertIn("openScreen=True,", server)
        self.assertIn("hand=None,", server)
        self.assertIn('snapshot["openScreen"] = bool(openScreen)', server)
        scan_handler = server[server.index(
            "    def _scan_carried_magic_maps"
        ):server.index(
            "    def _get_dimension"
        )]
        self.assertIn('"MagicMapHeldState"', scan_handler)
        self.assertIn("magic_map_logic.held_map_transition(", scan_handler)
        self.assertIn('transition["heldChanged"]', scan_handler)
        self.assertIn('transition["snapshotNeeded"]', scan_handler)
        self.assertIn('"mapId": mapId', scan_handler)
        self.assertIn("openScreen=False", scan_handler)
        snapshot_branch = scan_handler[scan_handler.index(
            '            if transition["snapshotNeeded"]:'
        ):scan_handler.index(
            "            changes = {}",
        )]
        self.assertIn("                continue", snapshot_branch)

        held_update = client[client.index(
            "    def _update_magic_map_hud"
        ):client.index(
            "    def _log_magic_map_hud"
        )]
        self.assertNotIn("% 40", held_update)
        self.assertIn("filled_magic_map_signature(held_item)", held_update)
        self.assertIn("signature_changed = bool(", held_update)
        self.assertIn(
            "if held and (not self._magic_map_was_held or signature_changed):",
            held_update,
        )
        request_handler = server[server.index(
            "    def OnMagicMapOpenRequest"
        ):server.index(
            "    def OnServerItemUseOnEvent"
        )]
        self.assertIn('args.get("openScreen", False)', request_handler)

        held_item_handler = server[server.index(
            "    def _hand_pos_type"
        ):server.index(
            "    def _is_creative"
        )]
        self.assertIn("itemPos.CARRIED", held_item_handler)
        self.assertIn("itemPos.OFFHAND", held_item_handler)
        self.assertIn("def _set_hand_item(", held_item_handler)
        self.assertIn("def _magic_map_hand_item(", held_item_handler)

        blank_timer_handler = server[server.index(
            "    def _replace_blank_magic_map"
        ):server.index(
            "    def _queue_filled_magic_map_open"
        )]
        self.assertIn('"hand": hand', blank_timer_handler)
        self.assertIn('data.get("hand")', blank_timer_handler)
        self.assertIn("self._set_hand_item(", blank_timer_handler)

    def test_held_map_reconciliation_bounds_native_item_queries(self):
        """Fallback polling must not hammer the native item registry."""
        server = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        client = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        config = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")

        self.assertIn("MAGIC_MAP_SCAN_INTERVAL_TICKS = 1", config)
        self.assertIn(
            "MAGIC_MAP_ITEM_RECONCILE_INTERVAL_TICKS = 10", config
        )
        self.assertIn(
            "MAGIC_MAP_CLIENT_RECONCILE_INTERVAL_TICKS = 30",
            config,
        )

        hand_item = server[
            server.index("    def _hand_item(") : server.index(
                "    def _carried_item(",
            )
        ]
        self.assertIn("GetPlayerItem(posType, 0, False)", hand_item)
        self.assertNotIn("GetPlayerItem(posType, 0, True)", hand_item)

        client_items = client[
            client.index("    def _get_magic_map_client_items(") : client.index(
                "    def _set_magic_map_hud_visible(",
            )
        ]
        self.assertEqual(1, client_items.count("item_comp.GetCarriedItem"))
        self.assertEqual(1, client_items.count("item_comp.GetOffhandItem"))
        self.assertNotIn("GetPlayerItem(", client_items)

        held_update = client[
            client.index("    def _update_magic_map_hud(") : client.index(
                "    def _log_magic_map_hud(",
            )
        ]
        self.assertIn(
            "% config.MAGIC_MAP_CLIENT_RECONCILE_INTERVAL_TICKS",
            held_update,
        )

        cached_discovery = server[
            server.index("    def _tick_cached_magic_map_discovery(") :
            server.index("    def _get_dimension(")
        ]
        self.assertNotIn("_magic_map_hand_item(", cached_discovery)
        self.assertNotIn("GetPlayerItem(", cached_discovery)
        self.assertIn("self._discover_magic_map(", cached_discovery)

        update = server[server.index("    def Update(self):") :]
        self.assertIn(
            "% config.MAGIC_MAP_SCAN_INTERVAL_TICKS", update
        )
        self.assertIn(
            "% config.MAGIC_MAP_ITEM_RECONCILE_INTERVAL_TICKS", update
        )

    def test_native_item_diagnostics_bracket_each_registry_call(self):
        server = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        client = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "import TwilightBossSlice.native_item_diagnostics",
            server,
        )
        self.assertIn(
            "import TwilightBossSlice.native_item_diagnostics",
            client,
        )

        hand_item = server[
            server.index("    def _hand_item(") : server.index(
                "    def _carried_item(",
            )
        ]
        self.assertLess(
            hand_item.index("begin_line("),
            hand_item.index("GetPlayerItem("),
        )
        self.assertLess(
            hand_item.index("GetPlayerItem("),
            hand_item.index("end_line("),
        )

        client_query = client[
            client.index("    def _query_magic_map_client_item(") : client.index(
                "    def _get_magic_map_client_items(",
            )
        ]
        self.assertLess(
            client_query.index("begin_line("),
            client_query.index("getter()"),
        )
        self.assertLess(
            client_query.index("getter()"),
            client_query.index("end_line("),
        )

    def test_held_hud_is_restored_with_diagnostics_disabled(self):
        client = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        config = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")

        self.assertIn("MAGIC_MAP_HELD_HUD_ENABLED = True", config)
        self.assertIn("MAGIC_MAP_DIAGNOSTICS_ENABLED = False", config)

        register = client[
            client.index("    def _register_magic_map_hud_proxy(") : client.index(
                "    def _unregister_magic_map_hud_proxy(",
            )
        ]
        self.assertLess(
            register.index("if not config.MAGIC_MAP_HELD_HUD_ENABLED:"),
            register.index("GetNativeScreenManagerCls()"),
        )

        stable_tick = client[
            client.index("    def OnScriptTickClient(") : client.index(
                "    def _spawn_naga_state_particle(",
            )
        ]
        self.assertIn(
            "if config.MAGIC_MAP_HELD_HUD_ENABLED:\n"
            "            self._update_magic_map_hud()",
            stable_tick,
        )

        ensure = client[
            client.index("    def _ensure_magic_map_ui(") : client.index(
                "    def OnMagicMapSnapshot(",
            )
        ]
        self.assertIn("config.MAGIC_MAP_UI_NAME", ensure)
        self.assertIn(
            "if held_hud_enabled and not self._magic_map_hud_ui_ready:",
            ensure,
        )

        snapshot = client[
            client.index("    def OnMagicMapSnapshot(") : client.index(
                "    def OnMagicMapDelta(",
            )
        ]
        self.assertIn(
            "if config.MAGIC_MAP_HELD_HUD_ENABLED:\n"
            "            magicMapHudUI.set_snapshot(snapshot)",
            snapshot,
        )

        delta = client[
            client.index("    def OnMagicMapDelta(") : client.index(
                "    def OnMagicMapHeldState(",
            )
        ]
        self.assertLess(
            delta.index("magicMapUI.apply_delta(dict(args))"),
            delta.index("if not config.MAGIC_MAP_HELD_HUD_ENABLED:"),
        )
        self.assertLess(
            delta.index("if not config.MAGIC_MAP_HELD_HUD_ENABLED:"),
            delta.index("magicMapHudUI.apply_delta(dict(args))"),
        )

        diagnostics = client[
            client.index("    def _log_magic_map_hud(") : client.index(
                "    def _log_twilight_sky(",
            )
        ]
        self.assertIn(
            "if not config.MAGIC_MAP_DIAGNOSTICS_ENABLED:",
            diagnostics,
        )

    def test_native_hud_proxy_defers_control_access_until_after_create(self):
        map_hud = (
            BP / "TwilightBossSlice" / "magicMapHudUI.py"
        ).read_text(encoding="utf-8")

        renderer_init = map_hud[
            map_hud.index("    def Init(self):"):
            map_hud.index("    def _bind_controls(self):")
        ]
        self.assertIn("if self._bind_delay_ticks <= 0:", renderer_init)

        renderer_update = map_hud[
            map_hud.index("    def Update(self):"):
            map_hud.index("    def Destroy(self):")
        ]
        self.assertIn(
            "if self._tick < self._bind_delay_ticks:",
            renderer_update,
        )

        bind_controls = map_hud[
            map_hud.index("    def _bind_controls(self):"):
            map_hud.index("    def _clean_cells(self, snapshot=None):")
        ]
        self.assertLess(
            bind_controls.index("for root_path in root_control_paths:"),
            bind_controls.index(
                "if self._root is None and self._discover_paths:"
            ),
        )

        proxy = map_hud[
            map_hud.index("class MagicMapHudProxy("):
        ]
        self.assertIn(
            "bind_delay_ticks=NATIVE_HUD_BIND_DELAY_TICKS",
            proxy,
        )

    def test_magic_map_restores_original_item_and_adds_a_custom_map_pose(self):
        animation_controller_path = (
            RP
            / "animation_controllers"
            / "magic_map_player.animation_controllers.json"
        )
        self.assertTrue(animation_controller_path.exists())
        controller_source = animation_controller_path.read_text(
            encoding="utf-8"
        )
        self.assertIn("controller.animation.tf_magic_map_pose", controller_source)
        self.assertIn("first_person_map_hold", controller_source)
        self.assertIn("filled_magic_map", controller_source)

        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            'MAGIC_MAP_ITEM = "tf_slice:magic_map"',
            config_source,
        )
        self.assertIn(
            'FILLED_MAGIC_MAP_ITEM = "tf_slice:filled_magic_map"',
            config_source,
        )
        self.assertIn(
            'LEGACY_NATIVE_MAGIC_MAP_ITEM = "minecraft:filled_map"',
            config_source,
        )

        server_source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn("def _is_magic_map_stack(", server_source)
        self.assertIn("def _migrate_legacy_native_magic_map(", server_source)
        self.assertIn(
            "magic_map_logic.decode_map_identity(",
            server_source,
        )

        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")
        self.assertIn("AddPlayerAnimationController(", client_source)
        self.assertIn("AddPlayerScriptAnimate(", client_source)
        self.assertIn("AddPlayerRenderController(", client_source)
        self.assertIn("controller.render.tf_magic_map_arms", client_source)
        self.assertIn("RebuildPlayerRender(", client_source)
        pose_handler = client_source[
            client_source.index("    def _ensure_magic_map_player_pose(self):"):
            client_source.index("    def _ensure_magic_map_ui(self):")
        ]
        # First-person map transforms use camera-space coordinates.  They
        # must never run for the inventory paper doll or map-face preview.
        self.assertGreaterEqual(
            pose_handler.count("variable.is_first_person"),
            2,
        )
        self.assertGreaterEqual(
            pose_handler.count("!variable.is_paperdoll"),
            2,
        )
        self.assertGreaterEqual(
            pose_handler.count("!variable.map_face_icon"),
            2,
        )

        attachable_path = (
            RP / "attachables" / "filled_magic_map.attachable.json"
        )
        geometry_path = (
            RP / "models" / "entity" / "filled_magic_map_carrier.geo.json"
        )
        render_controller_path = (
            RP
            / "render_controllers"
            / "magic_map_player.render_controllers.json"
        )
        self.assertTrue(attachable_path.exists())
        self.assertTrue(geometry_path.exists())
        self.assertTrue(render_controller_path.exists())
        attachable = read_json(attachable_path)["minecraft:attachable"][
            "description"
        ]
        self.assertEqual("tf_slice:filled_magic_map", attachable["identifier"])
        self.assertEqual(
            "geometry.tf_magic_map_carrier",
            attachable["geometry"]["default"],
        )
        geometry = read_json(geometry_path)["minecraft:geometry"][0]
        self.assertEqual(
            "geometry.tf_magic_map_carrier",
            geometry["description"]["identifier"],
        )
        # The attachable intentionally has no cubes: the predeclared HUD is
        # the map sheet, while this suppresses the ordinary flat item sprite.
        self.assertNotIn("cubes", geometry["bones"][0])
        render_controller_source = render_controller_path.read_text(
            encoding="utf-8"
        )
        self.assertIn(
            "controller.render.tf_magic_map_arms",
            render_controller_source,
        )
        self.assertIn("filled_magic_map", render_controller_source)

    def test_magic_map_pose_waits_for_local_player_skin_before_rebuild(self):
        client_source = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")

        # RebuildPlayerRender cannot resolve the player's default material
        # until the local skin payload has finished loading.  The engine's
        # UpdatePlayerSkinClientEvent is the lifecycle boundary documented
        # for accessing the final player render definition.
        self.assertIn(
            '"UpdatePlayerSkinClientEvent"',
            client_source,
        )
        self.assertIn(
            "self.OnUpdatePlayerSkinClientEvent",
            client_source,
        )
        self.assertIn(
            "self._magic_map_skin_ready = False",
            client_source,
        )

        skin_handler = client_source[
            client_source.index(
                "    def OnUpdatePlayerSkinClientEvent(self, args):"
            ):
            client_source.index("    def _ensure_magic_map_player_pose(self):")
        ]
        self.assertIn("clientApi.GetLocalPlayerId()", skin_handler)
        self.assertIn("self._magic_map_skin_ready = True", skin_handler)
        self.assertIn("self._magic_map_pose_registered = False", skin_handler)
        self.assertIn("self._ensure_magic_map_player_pose()", skin_handler)

        pose_handler = client_source[
            client_source.index("    def _ensure_magic_map_player_pose(self):"):
            client_source.index("    def _ensure_magic_map_ui(self):")
        ]
        self.assertIn("if not self._magic_map_skin_ready:", pose_handler)

        # Use the namespace-aware item query for custom items.  This avoids
        # relying on the legacy namespace-stripping behavior of
        # get_equipped_item_name in different renderer contexts.
        self.assertIn(
            "query.is_item_name_any('slot.weapon.mainhand', ",
            pose_handler,
        )
        self.assertIn("'tf_slice:filled_magic_map')", pose_handler)
        animation_source = (
            RP
            / "animation_controllers"
            / "magic_map_player.animation_controllers.json"
        ).read_text(encoding="utf-8")
        render_source = (
            RP
            / "render_controllers"
            / "magic_map_player.render_controllers.json"
        ).read_text(encoding="utf-8")
        self.assertIn("query.is_item_name_any", animation_source)
        self.assertIn("tf_slice:filled_magic_map", animation_source)
        self.assertIn("query.is_item_name_any", render_source)
        self.assertIn("tf_slice:filled_magic_map", render_source)

    def test_version_and_catalog_are_consistent(self):
        for manifest_path in (BP / "manifest.json", RP / "manifest.json"):
            manifest = read_json(manifest_path)
            self.assertEqual(
                EXPECTED_PACK_VERSION,
                manifest["header"]["version"],
            )
            for module in manifest["modules"]:
                self.assertEqual(EXPECTED_PACK_VERSION, module["version"])

        catalog = read_json(
            BP / "item_catalog" / "crafting_item_catalog.json"
        )
        encoded = json.dumps(catalog)
        for item_name in (
            "tf_slice:magic_map_focus",
            "tf_slice:magic_map",
        ):
            self.assertIn(item_name, encoded)
        self.assertNotIn("tf_slice:filled_magic_map", encoded)
        self.assertNotIn("tf_slice:filled_maze_map", encoded)

    def test_magic_map_ruleset_is_locked_to_the_supplied_original_jar(self):
        config_source = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        documentation = (
            ROOT / "docs" / "magic-map-upstream-port.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            'MAGIC_MAP_RULESET = "twilightforest:1.20.1-4.3.2508"',
            config_source,
        )
        self.assertIn("行为基线：1.20.1-4.3.2508", documentation)
        self.assertIn("4.3.2508 不同步征服红叉", documentation)


if __name__ == "__main__":
    unittest.main()
