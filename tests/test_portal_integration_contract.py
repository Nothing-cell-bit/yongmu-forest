# -*- coding: utf-8 -*-
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
PORTAL_ID = "tf_slice:twilight_portal"
TARGET_DIMENSION_ID = 33027004


def read_json(path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


class PortalResourceContractTests(unittest.TestCase):
    def test_portal_loading_overlay_covers_the_client_streaming_gap(self):
        definitions = read_json(RP / "ui" / "_ui_defs.json")["ui_defs"]
        overlay = read_json(RP / "ui" / "portal_loading.json")
        screen = overlay["main"]
        background = screen["controls"][0]["overlay"]

        self.assertIn("ui/portal_loading.json", definitions)
        self.assertTrue(screen["render_game_behind"])
        self.assertFalse(screen["absorbs_input"])
        self.assertEqual(["100%", "100%"], background["size"])
        self.assertGreaterEqual(background["alpha"], 0.95)
        self.assertFalse(background["visible"])

    def test_portal_uses_the_fresh_dimension_registry(self):
        dimension_config = read_json(
            BP / "netease_dimension" / "dimension_config.json"
        )["netease:dimension"]
        runtime_config = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        dimension_path = (
            BP
            / "netease_dimension"
            / ("dm%d.json" % TARGET_DIMENSION_ID)
        )

        self.assertEqual(
            [TARGET_DIMENSION_ID],
            dimension_config["modDimensionId"],
        )
        self.assertIn(
            "DIMENSION_ID = %d" % TARGET_DIMENSION_ID,
            runtime_config,
        )
        self.assertTrue(dimension_path.is_file())

    def test_ocean_profile_is_not_in_random_base_terrain_pool(self):
        dimension = read_json(
            BP / "netease_dimension" / "dm33027004.json"
        )["netease:dimension_info"]
        source_layers = dimension["components"]["netease:biome_source"]
        biome_pool = next(
            layer["pool"]
            for layer in source_layers
            if layer["type"] == "random_with_weight"
        )
        registered_biomes = {
            entry["biome_type"]
            for entry in biome_pool
        }

        self.assertIn("dm33027004_plains", registered_biomes)
        self.assertNotIn("dm33027004_ocean", registered_biomes)

    def test_active_ocean_biome_is_registered_for_the_fresh_dimension(self):
        server_biome = read_json(
            BP
            / "netease_biomes"
            / "dm33027004"
            / "dm33027004_ocean.json"
        )["minecraft:biome"]
        client_biome = read_json(
            RP / "biomes" / "dm33027004_ocean.client_biome.json"
        )["minecraft:client_biome"]

        self.assertEqual(
            "dm33027004_ocean",
            server_biome["description"]["identifier"],
        )
        self.assertEqual(
            "ocean",
            server_biome["description"]["inherits"],
        )
        self.assertIn("dm33027004", server_biome["components"])
        self.assertEqual(
            "dm33027004_ocean",
            client_biome["description"]["identifier"],
        )

    def test_validator_tracks_only_the_active_dimension_id(self):
        validator = (ROOT / "tools" / "validate_slice.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("DIMENSION_ID = 33027004", validator)
        self.assertNotIn("LEGACY_DIMENSION_ID", validator)

    def test_stale_dimension_definitions_are_not_shipped(self):
        self.assertFalse(
            (BP / "netease_dimension" / "dm33027003.json").exists()
        )
        self.assertFalse(
            (BP / "netease_biomes" / "dm33027003").exists()
        )
        self.assertFalse(
            any(
                (RP / "biomes").glob(
                    "dm33027003_*.client_biome.json"
                )
            )
        )

    def test_server_block_sends_inside_and_neighbor_events(self):
        document = read_json(BP / "netease_blocks" / "twilight_portal.json")
        block = document["minecraft:block"]
        self.assertEqual(PORTAL_ID, block["description"]["identifier"])
        components = block["components"]
        self.assertTrue(
            components["netease:on_entity_inside"]["send_python_event"]
        )
        self.assertTrue(
            components["netease:neighborchanged_sendto_script"]["value"]
        )
        self.assertEqual(
            [0.0, 0.0, 0.0],
            components["netease:aabb"]["collision"]["max"],
        )
        self.assertEqual(
            "geometry.tf_slice.twilight_portal",
            components["minecraft:geometry"],
        )

    def test_client_bindings_and_geometry_are_closed(self):
        blocks = read_json(RP / "blocks.json")
        atlas = read_json(RP / "textures" / "terrain_texture.json")
        geometry = read_json(
            RP / "models" / "blocks" / "twilight_portal.geo.json"
        )
        self.assertIn(PORTAL_ID, blocks)
        self.assertIn(PORTAL_ID, atlas["texture_data"])
        identifiers = {
            entry["description"]["identifier"]
            for entry in geometry["minecraft:geometry"]
        }
        self.assertIn("geometry.tf_slice.twilight_portal", identifiers)
        cube = geometry["minecraft:geometry"][0]["bones"][0]["cubes"][0]
        self.assertEqual([-8, 12, -8], cube["origin"])
        self.assertEqual([16, 1, 16], cube["size"])
        self.assertIsInstance(cube["uv"], dict)
        self.assertEqual({"up"}, set(cube["uv"]))
        self.assertEqual([0, 0], cube["uv"]["up"]["uv"])
        self.assertEqual([16, 16], cube["uv"]["up"]["uv_size"])
        self.assertEqual("*", cube["uv"]["up"]["material_instance"])


class PortalServerContractTests(unittest.TestCase):
    def test_relocation_waits_for_client_render_ack(self):
        server = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        client = (
            BP / "TwilightBossSlice" / "clientSystem.py"
        ).read_text(encoding="utf-8")

        self.assertIn('"PortalArrivalRelocated"', server)
        self.assertIn('"PortalArrivalPrepared"', server)
        self.assertIn('"PortalArrivalEngineReady"', server)
        self.assertIn('"PortalArrivalClientReady"', server)
        self.assertIn("clientEngineReadyPending", server)
        self.assertIn("clientReadyPending", server)
        self.assertIn('"PortalArrivalPrepared"', client)
        self.assertIn('"PortalArrivalEngineReady"', client)
        self.assertIn('"PortalArrivalRelocated"', client)
        self.assertIn('"PortalArrivalFinished"', client)
        self.assertIn('"ChunkLoadedClientEvent"', client)
        self.assertIn("OnChunkLoadedClientEvent", client)
        self.assertIn("client_required_chunk_positions", client)
        self.assertIn("client_required_chunks_loaded", client)
        self.assertIn("client_destination_anchor_ready", client)
        self.assertNotIn("probeTopHeights", client)
        self.assertNotIn("GetTopBlockHeight(samplePosition)", client)
        self.assertIn('self.NotifyToServer(\n                "PortalArrivalClientReady"', client)

    def test_activation_keeps_lightning_and_ticks_away_new_fire(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        config = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        activation = source[source.index("    def _activate_portal") :]
        activation = activation[: activation.index(
            "    def _process_portal_catalysts"
        )]
        update = source[source.index("    def Update(self)") :]
        update = update[: update.index("    def OnServerChatEvent")]

        self.assertIn("/summon lightning_bolt ", activation)
        self.assertIn("_prepare_portal_fire_cleanup", activation)
        self.assertIn("_portal_fire_cleanups.append", activation)
        self.assertIn("_process_portal_fire_cleanups()", update)
        self.assertIn("PORTAL_LIGHTNING_FIRE_CLEANUP_TICKS = 8", config)

    def test_entering_an_active_portal_does_not_require_flowers(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        helper = source[source.index("    def _portal_surface") :]
        helper = helper[: helper.index("    def _portal_exit")]

        self.assertIn("collect_stable_portal", helper)
        self.assertNotIn("collect_portal(", helper)

    def test_activation_and_travel_events_are_registered(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        for event_name in (
            "PlayerDropItemServerEvent",
            "OnEntityInsideBlockServerEvent",
            "BlockNeighborChangedServerEvent",
        ):
            self.assertIn(event_name, source)
        self.assertIn("collect_enclosed_surface", source)
        self.assertIn("CreateEngineItemEntity", source)
        self.assertIn("ChangePlayerDimension", source)

    def test_command_entry_and_rejoin_recover_persistent_return_portal(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        config = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        finish = source[source.index(
            "    def OnDimensionChangeFinish"
        ) :]
        finish = finish[: finish.index("    def OnPlayerDropItem")]
        ready = source[source.index("    def OnClientReady") :]
        ready = ready[: ready.index(
            "    def OnDimensionChangeServerEvent"
        )]

        self.assertIn("DimensionChangeServerEvent", source)
        self.assertIn("fromX", source)
        self.assertIn("_store_return_point", source)
        self.assertIn("_queue_portal_recovery", finish)
        self.assertIn("_queue_portal_recovery", ready)
        self.assertIn("PORTAL_RETURN_POINTS_KEY", config)
        self.assertIn("SaveExtraData", source)

    def test_portal_work_is_bounded_for_mobile(self):
        config = (
            BP / "TwilightBossSlice" / "config.py"
        ).read_text(encoding="utf-8")
        self.assertIn("PORTAL_SCAN_INTERVAL_TICKS = 2", config)
        self.assertIn("PORTAL_MAX_SIZE = 64", config)
        self.assertIn("MAX_PENDING_CATALYSTS = 32", config)

    def test_entry_waits_for_ready_chunks_without_async_chunk_work(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        enter = source[source.index("    def _enter_slice") :]
        enter = enter[: enter.index("    def _return_from_slice")]
        process = source[source.index("    def _process_portal_arrivals") :]
        process = process[: process.index("    def _enter_slice")]

        self.assertIn("DimensionChangeFinishServerEvent", source)
        self.assertNotIn("DoTaskOnChunkAsync", enter)
        self.assertNotIn("_change_dimension(", enter)
        self.assertIn("GetTopBlockHeight", source)
        self.assertIn("SetAddArea", source)
        self.assertIn("CheckChunkState", source)
        self.assertIn("_portal_target_chunks_ready", process)
        self.assertIn("_make_return_portal", process)
        self.assertIn("_change_dimension", process)

    def test_background_chunk_work_runs_only_after_arrival_release(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        finish = source[source.index("    def _finish_portal_arrival") :]
        finish = finish[: finish.index("    def _process_portal_arrivals")]
        background = source[
            source.index("    def _process_portal_background_preloads") :
        ]
        background = background[: background.index("\n    def ", 5)]

        release = finish.index("_pending_portal_entries.pop")
        queue = finish.index("_queue_portal_background_preload")
        self.assertLess(release, queue)
        self.assertNotIn("DoTaskOnChunkAsync", finish)
        self.assertIn("DoTaskOnChunkAsync", background)
        self.assertIn("_process_portal_background_preloads()", source)
        self.assertIn('"entry.worldgen.summary"', finish)

    def test_dimension_finish_only_finalizes_a_verified_destination_portal(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        helper = source[source.index("    def _finish_portal_arrival") :]
        helper = helper[: helper.index("    def _process_portal_arrivals")]

        self.assertIn("_portal_exit", helper)
        self.assertIn("_remember_portal_link", helper)
        self.assertNotIn("CF.CreatePos(playerId).SetPos", helper)
        self.assertNotIn("_make_return_portal", helper)

    def test_neighbor_changes_do_not_require_flowers_after_activation(self):
        source = (
            BP / "TwilightBossSlice" / "serverSystem.py"
        ).read_text(encoding="utf-8")
        handler = source[source.index("    def OnBlockNeighborChanged") :]
        handler = handler[: handler.index("    def OnBossSyncAck")]

        self.assertIn("collect_stable_portal", handler)
        self.assertNotIn("collect_portal(", handler)


if __name__ == "__main__":
    unittest.main()
