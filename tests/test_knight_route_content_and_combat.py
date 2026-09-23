# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
PACKAGE = BP / "TwilightBossSlice"
TOOLS = ROOT / "tools"
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


class KnightRouteContentContractTests(unittest.TestCase):
    def test_all_new_knight_models_are_registered_at_the_completed_offline_gate(self):
        registry = json.loads(
            (ROOT / "model_acceptance" / "registry.json").read_text(
                encoding="utf-8"
            )
        )
        entries = {entry["id"]: entry for entry in registry["entities"]}
        identifiers = {
            "block_chain_goblin",
            "lower_goblin_knight",
            "upper_goblin_knight",
            "helmet_crab",
            "knight_phantom",
            "knight_axe_projectile",
            "knight_pickaxe_projectile",
            "block_chain_projectile",
        }
        self.assertTrue(identifiers.issubset(entries))
        for identifier in identifiers:
            entry = entries[identifier]
            if identifier.endswith("_projectile"):
                self.assertEqual("rejected" if identifier == "block_chain_projectile" else "converted", entry["status"])
                self.assertNotIn("offline_evidence", entry)
            else:
                self.assertEqual(
                    "rejected"
                    if identifier == "knight_phantom"
                    else "candidate",
                    entry["status"],
                )
                self.assertEqual(
                    "model_acceptance/offline/%s.json" % identifier,
                    entry["offline_evidence"],
                )
            self.assertEqual(
                "model_acceptance/evidence/%s.json" % identifier,
                entry["evidence"],
            )
        for identifier in identifiers - {
            "knight_axe_projectile",
            "knight_pickaxe_projectile",
            "block_chain_projectile",
        }:
            client = json.loads(
                (BP.parent / "TwilightBossSliceR" / "entity" / (identifier + ".entity.json")).read_text(
                    encoding="utf-8"
                )
            )
            geometry = client["minecraft:client_entity"]["description"]["geometry"]["default"]
            self.assertEqual("geometry.tf_slice.%s" % identifier, geometry)

    def test_stronghold_entities_have_locked_attributes(self):
        expected = {
            "block_chain_goblin": (20, 8),
            "lower_goblin_knight": (20, 4),
            "upper_goblin_knight": (30, 8),
            "helmet_crab": (13, 3),
            "knight_phantom": (35, 1),
        }
        for name, (health, damage) in expected.items():
            document = json.loads(
                (BP / "entities" / (name + ".entity.json")).read_text(
                    encoding="utf-8"
                )
            )
            components = document["minecraft:entity"]["components"]
            self.assertEqual(health, components["minecraft:health"]["max"])
            self.assertEqual(damage, components["minecraft:attack"]["damage"])

    def test_helmet_crab_matches_source_armor_and_goal_speeds(self):
        document = json.loads(
            (BP / "entities" / "helmet_crab.entity.json").read_text(
                encoding="utf-8"
            )
        )
        components = document["minecraft:entity"]["components"]
        self.assertEqual(6, components["minecraft:armor"]["value"])
        self.assertEqual(
            1.0,
            components["minecraft:behavior.melee_attack"]["speed_multiplier"],
        )
        self.assertEqual(
            1.0,
            components["minecraft:behavior.random_stroll"]["speed_multiplier"],
        )

    def test_trophy_pedestal_has_a_persisted_active_visual_state(self):
        document = json.loads(
            (BP / "netease_blocks" / "trophy_pedestal.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:block"]
        self.assertEqual(
            [False, True],
            document["description"]["states"]["tf_slice:active"],
        )
        self.assertTrue(
            any(
                "tf_slice:active" in permutation.get("condition", "")
                for permutation in document.get("permutations", ())
            )
        )
        worldgen = (PACKAGE / "structureWorldgenService.py").read_text(
            encoding="utf-8"
        )
        activation = worldgen[worldgen.index("def activate_trophy_pedestal"):]
        activation = activation[:activation.index("\n    def ", 1)]
        self.assertIn('"tf_slice:active"', activation)
        self.assertIn("trophyPedestalActiveVisual", activation)

    def test_trophy_pedestal_uses_source_profile_and_multiface_art(self):
        block = json.loads(
            (BP / "netease_blocks" / "trophy_pedestal.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:block"]
        self.assertEqual(
            "geometry.tf_slice.trophy_pedestal",
            block["components"]["minecraft:geometry"],
        )
        materials = block["components"]["minecraft:material_instances"]
        self.assertTrue(
            {"north", "south", "east", "west", "top", "bottom"}
            <= set(materials)
        )
        active = next(
            permutation
            for permutation in block["permutations"]
            if "tf_slice:active" in permutation["condition"]
        )
        self.assertIn(
            "minecraft:material_instances",
            active["components"],
        )

        geometry = json.loads(
            (
                RP / "models" / "blocks" / "trophy_pedestal.geo.json"
            ).read_text(encoding="utf-8")
        )["minecraft:geometry"][0]
        cubes = [
            cube
            for bone in geometry["bones"]
            for cube in bone.get("cubes", ())
        ]
        self.assertGreaterEqual(len(cubes), 7)
        self.assertNotIn([16, 16, 16], [cube["size"] for cube in cubes])

    def test_knightmetal_item_family_is_complete(self):
        import build_knight_stronghold_content as builder

        names = {
            "armor_shard",
            "armor_shard_cluster",
            "knightmetal_ingot",
            "knightmetal_helmet",
            "knightmetal_chestplate",
            "knightmetal_leggings",
            "knightmetal_boots",
            "knightmetal_sword",
            "knightmetal_pickaxe",
            "knightmetal_axe",
            "knightmetal_ring",
            "knightmetal_shield",
            "block_and_chain",
            "phantom_helmet",
            "phantom_chestplate",
        }
        for name in names:
            self.assertTrue((BP / "items" / (name + ".item.json")).is_file(), name)
        breaking = json.loads(
            (BP / "enchantments" / "destruction.enchantment.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(3, breaking["tf_slice:enchantment"]["max_level"])
        for name in (
            "knight_axe_projectile", "knight_pickaxe_projectile",
            "block_chain_projectile",
        ):
            self.assertTrue((BP / "entities" / (name + ".entity.json")).is_file(), name)
        block_chain_client = json.loads(
            (BP.parent / "TwilightBossSliceR" / "entity" / "block_chain_projectile.entity.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            "textures/entity/tf_slice/block_chain_goblin",
            block_chain_client["minecraft:client_entity"]["description"]["textures"]["default"],
        )
        self.assertEqual(
            "geometry.tf_slice.block_chain_projectile",
            block_chain_client["minecraft:client_entity"]["description"][
                "geometry"
            ]["default"],
        )
        client_description = block_chain_client["minecraft:client_entity"][
            "description"
        ]
        self.assertEqual(
            "animation.tf_slice.block_chain_projectile.chain",
            client_description["animations"]["chain"],
        )
        self.assertEqual(
            ["chain"],
            client_description["scripts"]["animate"],
        )
        self.assertEqual(
            block_chain_client,
            builder._projectile_client(
                "block_chain_projectile", "block_and_chain_thrown"
            ),
        )
        chain_behavior = json.loads(
            (BP / "entities" / "block_chain_projectile.entity.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:entity"]
        chain_properties = chain_behavior["description"]["properties"]
        self.assertEqual(
            {"tf_slice:chain_x", "tf_slice:chain_y", "tf_slice:chain_z"},
            set(chain_properties),
        )
        for value in chain_properties.values():
            self.assertEqual("float", value["type"])
            self.assertEqual([-20.0, 20.0], value["range"])
            self.assertTrue(value["client_sync"])
        geometry_path = (
            RP / "models" / "entity" / "block_chain_projectile.geo.json"
        )
        self.assertTrue(geometry_path.is_file())
        geometry = json.loads(geometry_path.read_text(encoding="utf-8"))[
            "minecraft:geometry"
        ][0]
        self.assertEqual(
            "geometry.tf_slice.block_chain_projectile",
            geometry["description"]["identifier"],
        )
        self.assertGreaterEqual(geometry["description"]["visible_bounds_width"], 34)
        self.assertGreaterEqual(geometry["description"]["visible_bounds_height"], 34)
        bones = {bone["name"]: bone for bone in geometry["bones"]}
        self.assertEqual(
            {"block"}
            | {"spikes_%d" % index for index in range(27)}
            | {"chain_%d" % index for index in range(5)}
            | {"chain_root"},
            set(bones) - {"chain_origin", "chain_head", "chain_basis_x", "chain_basis_y", "chain_basis_z"},
        )
        self.assertEqual(
            {"origin": [-4, 0, -4], "size": [8, 8, 8], "uv": [32, 16]},
            bones["block"]["cubes"][0],
        )
        self.assertEqual([0, 9, 0], bones["spikes_0"]["pivot"])
        self.assertEqual([0, 8, 4], bones["spikes_1"]["pivot"])
        self.assertEqual([45, 0, 0], bones["spikes_1"]["rotation"])
        self.assertEqual([4, 8, 4], bones["spikes_2"]["pivot"])
        self.assertEqual([-55, 45, 0], bones["spikes_2"]["rotation"])
        self.assertEqual([4, 8, 0], bones["spikes_3"]["pivot"])
        self.assertEqual([0, 0, -45], bones["spikes_3"]["rotation"])
        for index in range(27):
            spike = bones["spikes_%d" % index]
            self.assertEqual("block", spike["parent"])
            self.assertEqual([2, 2, 2], spike["cubes"][0]["size"])
            self.assertEqual([56, 16], spike["cubes"][0]["uv"])
        for index in range(5):
            link = bones["chain_%d" % index]
            self.assertEqual("chain_root", link["parent"])
            self.assertEqual([0, 0, 0], link["pivot"])
            self.assertEqual([2, 2, 2], link["cubes"][0]["size"])
            self.assertEqual([56, 16], link["cubes"][0]["uv"])
        self.assertEqual(
            geometry,
            builder._block_chain_projectile_geometry()[
                "minecraft:geometry"
            ][0],
        )
        chain_animation_path = (
            RP / "animations" / "block_chain_projectile.animation.json"
        )
        self.assertTrue(chain_animation_path.is_file())
        chain_animation = json.loads(
            chain_animation_path.read_text(encoding="utf-8")
        )
        self.assertEqual(
            chain_animation,
            builder._block_chain_projectile_animation(),
        )
        encoded_animation = json.dumps(chain_animation)
        self.assertNotIn("tf_slice:chain_length", encoded_animation)
        for property_name in ("chain_hand_x", "chain_hand_y", "chain_hand_z",
                              "chain_head_x", "chain_head_y", "chain_head_z"):
            self.assertIn(
                "query.mod.tf_%s" % property_name,
                encoded_animation,
            )
        chain_bones = chain_animation["animations"][
            "animation.tf_slice.block_chain_projectile.chain"
        ]["bones"]
        self.assertNotIn("chain_root", chain_bones)
        for index in range(5):
            self.assertEqual(0, chain_bones['chain_%d' % index]['scale'])
        self.assertNotIn('query.position(', encoded_animation)
        self.assertNotIn('query.body_y_rotation', encoded_animation)
        for pack_root, folder in ((BP, "entities"), (RP, "entity")):
            self.assertTrue(
                (pack_root / folder / "block_chain_link.entity.json").is_file()
            )
        link_behavior = json.loads(
            (BP / "entities" / "block_chain_link.entity.json").read_text(
                encoding="utf-8"
            )
        )
        link_client = json.loads(
            (RP / "entity" / "block_chain_link.entity.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(link_behavior, builder._block_chain_link_behavior())
        self.assertEqual(link_client, builder._block_chain_link_client())
        link_controller = json.loads((RP / 'render_controllers/block_chain_link.render_controllers.json').read_text())
        self.assertEqual(builder._block_chain_link_render_controller(), link_controller)
        self.assertIn('query.mod.tf_chain_ready > 0.5', json.dumps(link_controller))
        for behavior in (
            json.loads(
                (BP / "entities" / "block_chain_projectile.entity.json").read_text(
                    encoding="utf-8"
                )
            ),
            link_behavior,
        ):
            entity = behavior["minecraft:entity"]
            self.assertEqual(
                {},
                entity["component_groups"]["tf_slice:instant_remove"][
                    "minecraft:instant_despawn"
                ],
            )
            self.assertEqual(
                ["tf_slice:instant_remove"],
                entity["events"]["tf_slice:instant_remove"]["add"][
                    "component_groups"
                ],
            )
        self.assertEqual(
            False,
            link_behavior["minecraft:entity"]["components"][
                "minecraft:damage_sensor"
            ]["triggers"][0]["deals_damage"],
        )
        link_geometry_path = (
            RP / "models" / "entity" / "block_chain_link.geo.json"
        )
        self.assertTrue(link_geometry_path.is_file())
        link_geometry = json.loads(
            link_geometry_path.read_text(encoding="utf-8")
        )["minecraft:geometry"][0]
        self.assertEqual(
            "geometry.tf_slice.block_chain_link",
            link_geometry["description"]["identifier"],
        )
        self.assertEqual(
            link_geometry,
            builder._block_chain_link_geometry()["minecraft:geometry"][0],
        )
        self.assertEqual(
            [56, 16],
            link_geometry["bones"][0]["cubes"][0]["uv"],
        )
        catalog = json.loads(
            (BP / "item_catalog" / "crafting_item_catalog.json").read_text(
                encoding="utf-8"
            )
        )
        creative_items = {
            identifier
            for category in catalog["minecraft:crafting_items_catalog"]["categories"]
            for group in category.get("groups", [])
            for identifier in group.get("items", [])
        }
        expected_public = names | {
            "underbrick",
            "cracked_underbrick",
            "mossy_underbrick",
            "underbrick_floor",
            "knightmetal_block",
            "stronghold_shield",
            "trophy_pedestal",
        }
        self.assertTrue(
            {"tf_slice:" + value for value in expected_public}.issubset(creative_items)
        )

    def test_model_evidence_cannot_skip_the_offline_preview_gate(self):
        evidence = json.loads(
            (ROOT / "evidence" / "models" / "knight_route.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual("rejected", evidence["status"])
        self.assertFalse(evidence["offlineEvidenceComplete"])
        self.assertFalse(evidence["clientAccepted"])
        self.assertFalse(evidence["runtimeVerified"])
        for model in evidence["models"]:
            self.assertEqual(
                ["front", "back", "left", "right", "top", "three_quarter"],
                model["requiredViews"],
            )
            self.assertEqual(
                ["rest", "walk_extreme", "look_up", "look_down"],
                model["requiredPoses"],
            )
            self.assertIn("offlineEvidence", model)


class KnightCombatLogicTests(unittest.TestCase):
    def test_player_knightmetal_items_expose_real_use_contracts(self):
        import build_knight_stronghold_content as builder

        chain = json.loads(
            (BP / "items" / "block_and_chain.item.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:item"]["components"]
        shield = json.loads(
            (BP / "items" / "knightmetal_shield.item.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:item"]["components"]

        self.assertEqual(99, chain["minecraft:durability"]["max_durability"])
        self.assertNotIn("minecraft:damage", chain)
        self.assertNotIn("minecraft:use_duration", chain)
        self.assertNotIn("minecraft:projectile", chain)
        self.assertNotIn("minecraft:throwable", chain)

        self.assertTrue(shield["minecraft:allow_off_hand"])
        self.assertEqual("block", shield["minecraft:use_animation"])
        self.assertNotIn("minecraft:use_duration", shield)
        self.assertNotIn("minecraft:hand_equipped", shield)
        self.assertEqual(
            1024, shield["minecraft:durability"]["max_durability"]
        )

        generated_chain = builder._item("block_and_chain", 1, None, 99)
        generated_shield = builder._item(
            "knightmetal_shield", 1, None, 1024
        )
        self.assertEqual(
            chain, generated_chain["minecraft:item"]["components"]
        )
        self.assertEqual(
            shield, generated_shield["minecraft:item"]["components"]
        )

    def test_player_knightmetal_items_have_input_bridge_and_shield_attachable(self):
        import build_knight_stronghold_content as builder
        from PIL import Image

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn('"ClientItemTryUseEvent"', client)
        self.assertIn('"ClientItemUseOnEvent"', client)
        self.assertIn('"RightClickBeforeClientEvent"', client)
        self.assertIn('"RightClickReleaseClientEvent"', client)
        self.assertIn('"KnightItemUseRequest"', client)
        self.assertIn('"KnightItemUseRequest"', server)
        right_click = client[client.index("def OnKnightRightClickBeforeClientEvent"):]
        right_click = right_click[:right_click.index("\n    def ", 1)]
        self.assertIn("self._notify_knight_item_use(args)", right_click)
        right_release = client[
            client.index("def OnKnightRightClickReleaseClientEvent"):
        ]
        right_release = right_release[:right_release.index("\n    def ", 1)]
        self.assertIn("self.OnTapOrHoldReleaseClientEvent(args)", right_release)
        request = server[server.index("def OnKnightItemUseRequest"):]
        request = request[:request.index("\n    def ", 1)]
        self.assertIn("self._use_block_and_chain", request)
        self.assertIn("self._held_knightmetal_shield", request)
        self.assertIn('"knight.item_use_request"', request)

        attachable_path = (
            RP / "attachables" / "knightmetal_shield.attachable.json"
        )
        geometry_path = (
            RP / "models" / "entity" / "knightmetal_shield.geo.json"
        )
        icon_path = RP / "textures" / "items" / "knightmetal_shield_icon.png"
        self.assertTrue(attachable_path.is_file())
        self.assertTrue(geometry_path.is_file())
        self.assertTrue(icon_path.is_file())

        attachable = json.loads(attachable_path.read_text(encoding="utf-8"))[
            "minecraft:attachable"
        ]["description"]
        self.assertEqual("tf_slice:knightmetal_shield", attachable["identifier"])
        self.assertEqual(
            "geometry.tf_slice.knightmetal_shield",
            attachable["geometry"]["default"],
        )
        pre_animation = " ".join(attachable["scripts"]["pre_animation"])
        self.assertIn("tf_slice:knightmetal_shield", pre_animation)
        self.assertIn("controller.animation.shield.wield", attachable["animations"]["wield"])

        geometry = json.loads(geometry_path.read_text(encoding="utf-8"))[
            "minecraft:geometry"
        ][0]
        self.assertEqual(
            "geometry.tf_slice.knightmetal_shield",
            geometry["description"]["identifier"],
        )
        self.assertEqual(
            "q.item_slot_to_bone_name(c.item_slot)",
            geometry["bones"][0]["binding"],
        )
        self.assertEqual(
            attachable,
            builder._knightmetal_shield_attachable()[
                "minecraft:attachable"
            ]["description"],
        )
        self.assertEqual(
            geometry,
            builder._knightmetal_shield_geometry()["minecraft:geometry"][0],
        )
        with Image.open(icon_path) as icon:
            self.assertEqual((64, 64), icon.size)

        chain_attachable_path = (
            RP / "attachables" / "block_and_chain.attachable.json"
        )
        self.assertTrue(chain_attachable_path.is_file())
        attachable = json.loads(chain_attachable_path.read_text())
        self.assertEqual(builder._block_and_chain_attachable(), attachable)
        chain_item = json.loads((BP / "items" / "block_and_chain.item.json").read_text("utf-8"))
        self.assertTrue(chain_item["minecraft:item"]["components"]["minecraft:hand_equipped"])
        self.assertEqual("minecraft:item/handheld",
                         json.loads((builder.UPSTREAM / "models" / "item" / "block_and_chain.json").read_text())["parent"])

        atlas = json.loads(
            (RP / "textures" / "item_texture.json").read_text(encoding="utf-8")
        )["texture_data"]
        self.assertEqual(
            "textures/items/knightmetal_shield_icon",
            atlas["tf_slice:knightmetal_shield"]["textures"],
        )

    def test_player_shield_and_chain_rules_match_upstream_boundaries(self):
        import knight_route_logic as logic

        self.assertFalse(
            logic.player_shield_blocks(
                held=True,
                raised_ticks=4,
                from_front=True,
                damage_cause="entity_attack",
            )
        )
        self.assertTrue(
            logic.player_shield_blocks(
                held=True,
                raised_ticks=5,
                from_front=True,
                damage_cause="entity_attack",
            )
        )
        self.assertFalse(
            logic.player_shield_blocks(
                held=True,
                raised_ticks=20,
                from_front=False,
                damage_cause="entity_attack",
            )
        )
        self.assertFalse(
            logic.player_shield_blocks(
                held=True,
                raised_ticks=20,
                from_front=True,
                damage_cause="magic",
            )
        )
        self.assertFalse(logic.block_chain_should_return(False, 15.9, 99))
        self.assertTrue(logic.block_chain_should_return(False, 16.01, 1))
        self.assertFalse(logic.block_chain_should_return(False, 1.0, 100))
        self.assertEqual(12, logic.block_chain_smash_allowance(0))
        self.assertEqual(2, logic.block_chain_smash_allowance(10))
        self.assertEqual(0, logic.block_chain_smash_allowance(12))

        links = logic.block_chain_link_positions((0, 2, 0), (10, 2, 0))
        self.assertEqual(
            [(0.5, 2.0, 0.0), (2.5, 2.0, 0.0), (4.5, 2.0, 0.0),
             (6.5, 2.0, 0.0), (8.5, 2.0, 0.0)],
            links,
        )
        main_hand = logic.block_chain_hand_anchor(
            (0, 10, 0), (0, 0), main_hand=True, eye_height=1.62
        )
        self.assertAlmostEqual(-0.3894183423, main_hand[0])
        self.assertAlmostEqual(11.22, main_hand[1])
        self.assertAlmostEqual(0.9210609940, main_hand[2])
        off_hand = logic.block_chain_hand_anchor(
            (0, 10, 0), (0, 0), main_hand=False, eye_height=1.62
        )
        self.assertAlmostEqual(0.3894183423, off_hand[0])
        self.assertAlmostEqual(11.22, off_hand[1])
        self.assertAlmostEqual(0.9210609940, off_hand[2])
        spawn = logic.block_chain_spawn_position(
            (0, 10, 0), (0, 0), main_hand=True, eye_height=1.62
        )
        self.assertAlmostEqual(-0.3894183423, spawn[0])
        self.assertAlmostEqual(11.22, spawn[1])
        self.assertAlmostEqual(1.4210609940, spawn[2])
        visual = logic.block_chain_visual_state(main_hand, (0, 11.22, 3.0))
        self.assertAlmostEqual(2.1150967, visual["length"], places=5)
        self.assertEqual(
            (main_hand[0], 0.0, main_hand[2] - 3.0),
            visual["towardHand"],
        )
        self.assertFalse(
            logic.block_chain_can_hit_target("owner", "owner", "minecraft:player")
        )
        self.assertFalse(
            logic.block_chain_can_hit_target(
                "legacy-link", "owner", "tf_slice:block_chain_link"
            )
        )
        self.assertTrue(
            logic.block_chain_can_hit_target("victim", "owner", "minecraft:zombie")
        )
        self.assertEqual(
            (0.0, 0.0), logic.block_chain_rotation_for_motion((0, 0, 1))
        )
        self.assertEqual(
            (0.0, 90.0), logic.block_chain_rotation_for_motion((-1, 0, 0))
        )
        self.assertEqual(
            (1.0, -0.05, 0.0),
            logic.block_chain_return_motion(
                (1, 0, 0), (0, 0, 0), (10, 0, 0), 0
            ),
        )
        self.assertEqual(
            (-2.0, -0.05, 0.0),
            logic.block_chain_return_motion(
                (1, 0, 0), (0, 0, 0), (10, 0, 0), 34
            ),
        )
        self.assertEqual(
            (-0.36, 0.0, 0.0),
            logic.block_chain_bounce_motion((1, 0, 0), "WEST"),
        )

    def test_player_chain_hit_path_owns_damage_return_and_durability(self):
        import build_knight_stronghold_content as builder

        projectile = json.loads(
            (
                BP / "entities" / "block_chain_projectile.entity.json"
            ).read_text(encoding="utf-8")
        )["minecraft:entity"]["components"]["minecraft:projectile"]
        self.assertEqual(0, projectile["on_hit"]["impact_damage"]["damage"])
        self.assertEqual(0.05, projectile["gravity"])
        self.assertNotIn("remove_on_hit", projectile["on_hit"])
        generated_projectile = builder._projectile_entity(
            "block_chain_projectile", 0
        )["minecraft:entity"]["components"]["minecraft:projectile"]
        self.assertEqual(projectile, generated_projectile)

        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        hit = source[source.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        self.assertIn("BLOCK_CHAIN_DAMAGE", hit)
        self.assertIn("_damage_block_and_chain", hit)
        self.assertIn("BLOCK_CHAIN_SHIELD_DISABLE_TICKS", hit)

        driver = source[source.index("def _drive_block_chain_projectiles"):]
        driver = driver[:driver.index("\n    def ", 1)]
        visual = source[source.index("def _sync_block_chain_visual"):]
        visual = visual[:visual.index("\n    def ", 1)]
        self.assertNotIn("def _spawn_block_chain_links", source)
        self.assertNotIn("def _update_block_chain_links", source)
        self.assertNotIn("def _destroy_block_chain_links", source)
        self.assertIn('"BlockChainVisual"', visual)
        self.assertNotIn("_set_entity_property", visual)
        self.assertNotIn('"tf_slice:chain_length"', visual)
        self.assertNotIn("CreateRot", visual)
        self.assertIn("return True", visual)
        self.assertNotIn("_orient_block_chain_projectile", visual)
        self.assertNotIn("def _orient_block_chain_projectile", source)
        self.assertIn("_sync_block_chain_visual", driver)
        self.assertIn("_instant_remove_chain_entity(projectileId)", driver)

        use = source[source.index("def _use_block_and_chain"):]
        use = use[:use.index("\n    def ", 1)]
        self.assertIn("block_chain_spawn_position", use)
        self.assertNotIn("_spawn_block_chain_links", use)

        chain_branch = source[source.index("chainKey = entity_registry_logic.matching_entity_key"):]
        chain_branch = chain_branch[:chain_branch.index("if projectileType == HYDRA_MORTAR_IDENTIFIER")]
        self.assertIn("block_chain_can_hit_target", chain_branch)
        self.assertLess(
            chain_branch.index("block_chain_can_hit_target"),
            chain_branch.index("returnAgeOffset"),
        )

        use_on = source[source.index("def OnServerItemUseOnEvent"):]
        use_on = use_on[:use_on.index("\n    def ", 1)]
        self.assertIn('itemName == "tf_slice:block_and_chain"', use_on)
        self.assertIn("self._use_block_and_chain(args)", use_on)

        release = source[source.index("def OnItemReleaseUsingServerEvent"):]
        release = release[:release.index("\n    def ", 1)]
        self.assertIn("_knightmetal_shield_users", release)

        use = source[source.index("def _use_block_and_chain"):]
        use = use[:use.index("\n    def ", 1)]
        self.assertIn('args["cancel"] = True', use)
        self.assertIn('"knight.block_chain_launched"', use)

        drive = source[source.index("def _drive_block_chain_projectiles"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn("block_chain_return_motion", drive)
        self.assertIn("_sync_block_chain_visual", drive)
        self.assertNotIn("block_chain_link_positions", drive)

        hit = source[source.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        self.assertIn("block_chain_bounce_motion", hit)

    def test_server_consumes_persisted_formation_state(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _drive_knight_phantoms", source)
        update = source[source.index("def Update(self):"):]
        update = update[:update.index("def ", len("def Update(self):"))]
        self.assertIn("self._drive_knight_phantoms()", update)
        worldgen = (PACKAGE / "structureWorldgenService.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def active_knight_groups", worldgen)
        self.assertIn('"kind": "knight_phantoms"', source)
        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        hud = (PACKAGE / "routeBossHudUI.py").read_text(encoding="utf-8")
        self.assertIn(
            'visible_bosses(\n            self._bosses.values(),\n            "knight_phantoms"',
            client,
        )
        self.assertIn("class KnightPhantomsBossHudUI", hud)
        self.assertIn("def _spawn_knight_projectiles", source)
        self.assertIn("def _use_block_and_chain", source)
        item_effects = (PACKAGE / "item_effects.py").read_text(encoding="utf-8")
        self.assertIn("knightmetal_bonus", item_effects)
        self.assertIn('"DamageEvent", self._item_effects.on_damage', source)
        self.assertIn('"tf_slice:knightmetal_block"', source)

    def test_six_members_roles_health_and_formation_constants(self):
        import knight_route_logic as logic

        group = logic.create_group_state("g", (10, 40, 10), range(6))
        self.assertEqual(6, len(group["members"]))
        self.assertEqual([0, 1, 2, 0, 1, 2], [m["role"] for m in group["members"]])
        self.assertEqual(["hover"] * 6, [m["formation"] for m in group["members"]])
        self.assertEqual(210.0, logic.combined_health(group))
        self.assertEqual(90, logic.FORMATION_DURATIONS["hover"])
        self.assertEqual(180, logic.FORMATION_DURATIONS["charge_plus_x"])
        self.assertEqual(50, logic.FORMATION_DURATIONS["attack_player_attack"])

    def test_random_formation_rolls_match_the_source_weight_table(self):
        import knight_route_logic as logic

        self.assertEqual(
            [
                "small_clockwise",
                "small_anticlockwise",
                "small_anticlockwise",
                "charge_plus_x",
                "charge_minus_x",
                "charge_plus_z",
                "charge_minus_z",
                "small_clockwise",
            ],
            [logic.select_group_formation(roll) for roll in range(8)],
        )

    def test_group_advance_broadcasts_a_random_formation_and_one_charger(self):
        import knight_route_logic as logic

        group = logic.create_group_state("g", (10, 40, 10), range(6))
        group["formationTick"] = 89
        for member in group["members"]:
            member["formationTick"] = 89

        self.assertEqual(
            "small_clockwise",
            logic.advance_formation(
                group,
                1,
                formation_roll=0,
                charger_roll=2,
            ),
        )
        charging = [
            member for member in group["members"] if member["charging"]
        ]
        self.assertEqual([2], [member["number"] for member in charging])
        self.assertEqual("attack_player_start", charging[0]["formation"])
        self.assertEqual(
            ["small_clockwise"] * 5,
            [
                member["formation"]
                for member in group["members"]
                if member["number"] != 2
            ],
        )

        logic.advance_formation(group, 50)
        self.assertEqual(
            "attack_player_attack",
            logic.member_state(group, 2)["formation"],
        )
        self.assertEqual(
            [2],
            [
                member["number"]
                for member in group["members"]
                if member["charging"]
            ],
        )

    def test_source_movement_formulas_cover_orbits_sweeps_hover_and_roles(self):
        import knight_route_logic as logic

        group = logic.create_group_state("g", (10, 40, 10), range(6))
        leader = logic.member_state(group, 0)
        leader["formation"] = "large_clockwise"
        leader["formationTick"] = 0
        orbit = logic.formation_destination(group, 0)
        self.assertAlmostEqual(
            8.5,
            logic.horizontal_distance(orbit, (10, orbit[1], 10)),
            places=5,
        )

        leader["formation"] = "charge_plus_x"
        leader["formationTick"] = 60
        sweep_start = logic.formation_destination(group, 0)
        leader["formationTick"] = 120
        sweep_mid = logic.formation_destination(group, 0)
        leader["formationTick"] = 180
        sweep_end = logic.formation_destination(group, 0)
        self.assertEqual((2.5, 0.0, 17.0), (
            round(sweep_start[0], 4),
            round(sweep_mid[2] - group["home"][2], 4),
            round(sweep_end[2], 4),
        ))

        leader["formation"] = "hover"
        leader["formationTick"] = 1
        hover = logic.formation_destination(
            group, 0, current_position=(12.0, 41.0, 11.0)
        )
        self.assertEqual((12.0, 11.0), (hover[0], hover[2]))

        leader["formation"] = "attack_player_attack"
        leader["chargePos"] = [30, 42, 30]
        sword_attack = logic.formation_destination(
            group, 0, player_position=(50, 42, 50),
            current_position=(12.0, 41.0, 11.0),
        )
        self.assertEqual((30.0, 42.0, 30.0), sword_attack)

        axe = logic.member_state(group, 1)
        axe["formation"] = "attack_player_attack"
        axe["formationTick"] = 1
        axe_attack = logic.formation_destination(
            group, 1, player_position=(50, 42, 50),
            current_position=(12.0, 41.0, 11.0),
        )
        self.assertGreater(
            logic.horizontal_distance(axe_attack, (50, 42, 50)),
            30.0,
        )

    def test_server_drives_member_formations_instead_of_a_group_attack_state(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = source[source.index("def _drive_knight_phantoms"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn('memberFormation = str(member.get("formation"', drive)
        self.assertIn("current_position=position", drive)
        self.assertIn('memberFormation == "attack_player_attack"', drive)
        self.assertIn("tf_slice:enable_noclip", drive)
        self.assertIn("tf_slice:disable_noclip", drive)

    def test_charging_component_applies_source_damage_and_dynamic_hitbox(self):
        entity = json.loads(
            (BP / "entities" / "knight_phantom.entity.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:entity"]
        charging = entity["component_groups"]["tf_slice:charging_combat"]
        self.assertEqual(8, charging["minecraft:attack"]["damage"])
        self.assertEqual(
            {"width": 1.75, "height": 4.0},
            charging["minecraft:collision_box"],
        )
        self.assertEqual(
            0.0,
            charging["minecraft:behavior.melee_attack"]["speed_multiplier"],
        )
        self.assertEqual(
            1.0,
            charging["minecraft:behavior.melee_attack"]["cooldown_time"],
        )
        self.assertFalse(
            entity["components"]["minecraft:behavior.nearest_attackable_target"][
                "must_see"
            ]
        )
        self.assertNotIn("minecraft:behavior.random_hover", entity["components"])
        self.assertFalse(
            entity["component_groups"]["tf_slice:noclip"]["minecraft:physics"][
                "has_collision"
            ]
        )
        suffocation = next(
            trigger
            for trigger in entity["components"]["minecraft:damage_sensor"][
                "triggers"
            ]
            if trigger.get("cause") == "suffocation"
        )
        self.assertFalse(suffocation["deals_damage"])
        self.assertEqual(
            ["tf_slice:charging_combat"],
            entity["events"]["tf_slice:start_charging"]["add"][
                "component_groups"
            ],
        )
        self.assertEqual(
            ["tf_slice:charging_combat"],
            entity["events"]["tf_slice:stop_charging"]["remove"][
                "component_groups"
            ],
        )

    def test_schema_v1_attack_migrates_to_one_safe_charger(self):
        import knight_route_logic as logic

        legacy = logic.create_group_state("legacy", (0, 40, 0), range(6))
        legacy["schemaVersion"] = 1
        legacy["formation"] = "attack_player_attack"
        legacy["formationTick"] = 17
        for member in legacy["members"]:
            member["formation"] = "attack_player_attack"
            member["formationTick"] = 17
            for key in (
                "charging", "attackDamage", "armorMultiplier", "chargePos"
            ):
                member.pop(key, None)

        restored = logic.load_group_state(legacy)

        self.assertEqual(logic.GROUP_SCHEMA_VERSION, restored["schemaVersion"])
        self.assertEqual("hover", restored["formation"])
        self.assertEqual(
            [0],
            [
                member["number"]
                for member in restored["members"]
                if member["charging"]
            ],
        )
        self.assertEqual(
            ["hover"] * 5,
            [
                member["formation"]
                for member in restored["members"]
                if member["number"] != 0
            ],
        )

    def test_long_horizon_keeps_at_most_one_independent_charger(self):
        import knight_route_logic as logic

        group = logic.create_group_state("long", (0, 40, 0), range(6))
        group["formationTick"] = 89
        for member in group["members"]:
            member["formationTick"] = 89

        seen_charger = False
        seen_waiting = False
        for tick in range(720):
            logic.advance_formation(
                group,
                1,
                formation_roll=tick,
                charger_roll=tick + 2,
                weapon_roll=tick,
            )
            chargers = [
                member
                for member in group["members"]
                if member["charging"]
            ]
            self.assertLessEqual(len(chargers), 1)
            seen_charger = seen_charger or bool(chargers)
            seen_waiting = seen_waiting or any(
                member["formation"] == "waiting_for_leader"
                for member in group["members"]
            )
            self.assertTrue(
                all(
                    member["formation"] in logic.FORMATION_DURATIONS
                    for member in group["members"]
                )
            )
        self.assertTrue(seen_charger)
        self.assertTrue(seen_waiting)

    def test_single_survivor_restarts_as_a_source_sword_charger(self):
        import knight_route_logic as logic

        group = logic.create_group_state("solo", (0, 40, 0), range(6))
        for member in group["members"][1:]:
            member["alive"] = False
        group["deathSlots"] = [1, 2, 3, 4, 5]
        survivor = logic.member_state(group, 0)
        survivor["formation"] = "attack_player_attack"
        survivor["formationTick"] = 49

        logic.advance_formation(group, 1, weapon_roll=2)

        self.assertEqual(logic.ROLE_SWORD, survivor["role"])
        self.assertEqual("attack_player_start", survivor["formation"])
        self.assertTrue(survivor["charging"])

    def test_single_survivor_keeps_formation_but_is_immediately_renumbered_to_sword(self):
        import knight_route_logic as logic

        group = logic.create_group_state("solo-entry", (0, 40, 0), range(6))
        survivor = logic.member_by_slot(group, 5)
        survivor["formation"] = "large_clockwise"
        survivor["formationTick"] = 12
        survivor["visualRole"] = logic.ROLE_PICKAXE
        for slot in range(5):
            self.assertFalse(logic.record_member_death(group, slot))

        self.assertTrue(group["soloMode"])
        self.assertEqual(0, survivor["number"])
        self.assertEqual(logic.ROLE_SWORD, survivor["role"])
        self.assertEqual(-1, survivor["visualRole"])
        self.assertEqual("large_clockwise", survivor["formation"])
        self.assertEqual(12, survivor["formationTick"])

        logic.advance_formation(group, 1, weapon_roll=2)

        self.assertEqual("large_clockwise", survivor["formation"])
        self.assertEqual(13, survivor["formationTick"])
        restored = logic.load_group_state(json.loads(json.dumps(group)))
        restored_survivor = logic.member_by_slot(restored, 5)
        self.assertEqual(logic.ROLE_SWORD, restored_survivor["role"])
        self.assertEqual(
            0,
            len(logic.projectile_pattern(restored_survivor["role"], 4)),
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        spawn = server[server.index("def _spawn_knight_projectiles"):]
        spawn = spawn[:spawn.index("\n    def ", 1)]
        self.assertIn('member.get("role"', spawn)

    def test_delayed_death_path_and_stale_solo_save_self_heal_without_skipping_formation(self):
        import knight_route_logic as logic

        group = logic.create_group_state("solo-delayed", (0, 40, 0), range(6))
        for slot in range(4):
            self.assertFalse(logic.record_member_death(group, slot))
        survivor = logic.member_by_slot(group, 5)
        survivor["formation"] = "waiting_for_leader"
        survivor["formationTick"] = 3
        survivor["visualRole"] = logic.ROLE_AXE

        self.assertTrue(logic.begin_member_death(group, 4, "player"))

        self.assertTrue(group["soloMode"])
        self.assertEqual(0, survivor["number"])
        self.assertEqual(logic.ROLE_SWORD, survivor["role"])
        self.assertEqual(-1, survivor["visualRole"])
        self.assertEqual("waiting_for_leader", survivor["formation"])
        self.assertEqual(3, survivor["formationTick"])

        logic.advance_formation(group, 7)
        self.assertEqual("attack_player_start", survivor["formation"])
        self.assertEqual(0, survivor["formationTick"])

        survivor["role"] = logic.ROLE_PICKAXE
        survivor["visualRole"] = logic.ROLE_PICKAXE
        stale = logic.load_group_state(json.loads(json.dumps(group)))
        stale_survivor = logic.member_by_slot(stale, 5)
        self.assertTrue(stale["soloMode"])
        self.assertEqual(logic.ROLE_SWORD, stale_survivor["role"])
        self.assertEqual(-1, stale_survivor["visualRole"])
        self.assertEqual("attack_player_start", stale_survivor["formation"])

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        driver = server[server.index("def _drive_knight_phantoms"):]
        driver = driver[:driver.index("\n    def ", 1)]
        self.assertIn("knight_route_logic.renumber_living_members(group)", driver)
        self.assertLess(
            driver.index("knight_route_logic.renumber_living_members(group)"),
            driver.index("self._sync_knight_member_equipment"),
        )

    def test_lone_hover_survivor_selects_itself_within_the_source_time_window(self):
        import knight_route_logic as logic

        group = logic.create_group_state("solo-hover-window", (0, 40, 0), range(6))
        survivor = logic.member_by_slot(group, 5)
        survivor["formation"] = "hover"
        survivor["formationTick"] = 0
        for slot in range(5):
            self.assertFalse(logic.record_member_death(group, slot))

        logic.advance_formation(group, 89, formation_roll=0, charger_roll=0)
        self.assertEqual("hover", survivor["formation"])
        self.assertEqual(89, survivor["formationTick"])

        logic.advance_formation(group, 1, formation_roll=0, charger_roll=0)
        self.assertEqual("attack_player_start", survivor["formation"])
        self.assertEqual(0, survivor["formationTick"])
        self.assertEqual(logic.ROLE_SWORD, survivor["role"])

        logic.advance_formation(group, 50)
        self.assertEqual("attack_player_attack", survivor["formation"])
        self.assertEqual(0, survivor["formationTick"])

    def test_all_source_destination_branches_remain_available(self):
        import knight_route_logic as logic

        group = logic.create_group_state("moves", (10, 40, 10), range(6))
        leader = logic.member_state(group, 0)
        destinations = {}
        for formation in (
            "small_clockwise",
            "small_anticlockwise",
            "large_anticlockwise",
            "charge_minus_x",
            "charge_plus_z",
            "charge_minus_z",
            "waiting_for_leader",
        ):
            leader["formation"] = formation
            leader["formationTick"] = 30
            destinations[formation] = logic.formation_destination(group, 0)

        self.assertAlmostEqual(
            logic.CIRCLE_SMALL_RADIUS,
            logic.horizontal_distance(
                destinations["small_clockwise"],
                (10, destinations["small_clockwise"][1], 10),
            ),
        )
        self.assertGreater(
            destinations["small_clockwise"][2],
            destinations["small_anticlockwise"][2],
        )
        self.assertAlmostEqual(
            logic.CIRCLE_LARGE_RADIUS,
            logic.horizontal_distance(
                destinations["large_anticlockwise"],
                (10, destinations["large_anticlockwise"][1], 10),
            ),
        )
        self.assertGreater(
            destinations["charge_minus_x"][2],
            group["home"][2],
        )
        self.assertLess(
            destinations["charge_plus_z"][0],
            group["home"][0],
        )
        self.assertGreater(
            destinations["charge_minus_z"][0],
            group["home"][0],
        )
        self.assertEqual(
            (10.0, 10.0),
            (
                destinations["waiting_for_leader"][0],
                destinations["waiting_for_leader"][2],
            ),
        )

        leader["formation"] = "hover"
        outside = logic.formation_destination(
            group, 0, current_position=(30.0, 41.0, 10.0)
        )
        self.assertAlmostEqual(
            logic.CIRCLE_LARGE_RADIUS,
            logic.horizontal_distance(outside, (10, outside[1], 10)),
        )

    def test_projectiles_damage_and_bonuses_follow_member_roles(self):
        import knight_route_logic as logic

        self.assertEqual([], logic.projectile_pattern(0, 4))
        self.assertEqual([], logic.projectile_pattern(1, 3))
        self.assertEqual(
            [{"kind": "axe", "speed": 0.75, "damage": 0.0}],
            logic.projectile_pattern(1, 4),
        )
        picks = logic.projectile_pattern(2, 4)
        self.assertEqual(8, len(picks))
        self.assertEqual(list(range(0, 360, 45)), [row["yaw"] for row in picks])
        self.assertTrue(all(row["damage"] == 3.0 for row in picks))
        self.assertEqual(
            {"sword": 2.0, "axe": 0.0, "pickaxe": 0.0},
            logic.knightmetal_bonus(1),
        )
        self.assertEqual(
            {"sword": 0.0, "axe": 2.0, "pickaxe": 2.0},
            logic.knightmetal_bonus(0),
        )

        group = logic.create_group_state("damage", (0, 40, 0), range(6))
        self.assertFalse(logic.record_member_damage(group, 0, 5, "alice"))
        self.assertEqual(30.0, logic.member_state(group, 0)["health"])
        self.assertEqual(["alice"], group["participants"])
        self.assertAlmostEqual(205.0 / 210.0, logic.boss_bar_fraction(group))
        self.assertFalse(logic.record_member_damage(group, 99, 5, "bob"))

    def test_projectile_launch_starts_outside_the_owner_and_preserves_speed(self):
        import knight_route_logic as logic

        origin = (10.0, 40.0, 10.0)
        target = (20.0, 40.0, 10.0)
        pick = logic.projectile_launch(
            origin,
            target,
            {"kind": "pickaxe", "yaw": 0, "speed": 0.5},
        )
        self.assertEqual((11.0, 42.0, 10.0), pick["spawn"])
        self.assertEqual((0.5, 0.0, 0.0), pick["motion"])
        # The Bedrock actor yaw must follow the radial flight vector.  Passing
        # the source polar angle through unchanged leaves the item plane a
        # quarter-turn sideways (motion +X with actor yaw 0 faces +Z).
        self.assertEqual(-90.0, pick["yaw"])
        self.assertEqual(1.0, logic.horizontal_distance(pick["spawn"], origin))

        axe = logic.projectile_launch(
            origin,
            target,
            {"kind": "axe", "speed": 0.75},
        )
        self.assertEqual((11.0, 42.0, 10.0), axe["spawn"])
        self.assertEqual(-90.0, axe["yaw"])
        self.assertAlmostEqual(
            0.75,
            sum(value * value for value in axe["motion"]) ** 0.5,
        )

    def test_projectile_yaw_is_explicitly_applied_from_motion_after_spawn_and_each_tick(self):
        import knight_route_logic as logic

        self.assertEqual(-180.0, logic.projectile_yaw_for_motion((0, 0, -1)))
        self.assertEqual(-0.0, logic.projectile_yaw_for_motion((0, 0, 1)))
        self.assertEqual(-90.0, logic.projectile_yaw_for_motion((1, 0, 0)))
        self.assertEqual(90.0, logic.projectile_yaw_for_motion((-1, 0, 0)))
        self.assertEqual(
            37.0,
            logic.projectile_yaw_for_motion((0, 1, 0), fallback_yaw=37.0),
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        orient = server[server.index("def _orient_knight_projectile"):]
        orient = orient[:orient.index("\n    def ", 1)]
        self.assertIn("knight_route_logic.projectile_yaw_for_motion", orient)
        self.assertIn("CF.CreateRot(projectileId).SetRot((0.0, yaw))", orient)

        spawn = server[server.index("def _spawn_knight_projectiles"):]
        spawn = spawn[:spawn.index("\n    def ", 1)]
        self.assertIn("self._orient_knight_projectile", spawn)
        self.assertLess(
            spawn.index("self._set_full_motion"),
            spawn.index("self._orient_knight_projectile"),
        )

        drive = server[server.index("def _drive_knight_projectile_rotations"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn("self._knight_projectiles", drive)
        self.assertIn("self._get_full_motion", drive)
        self.assertIn("self._orient_knight_projectile", drive)

        update = server[server.index("def Update(self)"):]
        update = update[:update.index("\n    def ", 1)]
        self.assertIn("self._drive_knight_projectile_rotations()", update)

    def test_knight_projectile_tracking_prunes_stale_ids_before_motion_and_stays_bounded(self):
        import knight_route_logic as logic

        ttl = logic.KNIGHT_PROJECTILE_TTL_TICKS
        self.assertFalse(logic.projectile_tracking_expired(100, 100 + ttl - 1))
        self.assertTrue(logic.projectile_tracking_expired(100, 100 + ttl))

        limit = logic.KNIGHT_PROJECTILE_REGISTRY_LIMIT
        registry = {
            "p%03d" % index: {"spawnTick": index}
            for index in range(limit + 3)
        }
        self.assertEqual(
            ["p000", "p001", "p002"],
            logic.projectile_registry_overflow_keys(registry),
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = server[server.index("def _drive_knight_projectile_rotations"):]
        drive = drive[:drive.index("\n    def ", 1)]
        self.assertIn("projectile_tracking_expired", drive)
        self.assertIn("self._get_engine_type", drive)
        self.assertIn("self._discard_knight_projectile_tracking", drive)
        self.assertLess(
            drive.index("projectile_tracking_expired"),
            drive.index("self._get_full_motion"),
        )
        self.assertLess(
            drive.index("self._get_engine_type"),
            drive.index("self._get_full_motion"),
        )

        trim = server[server.index("def _trim_knight_projectile_registry"):]
        trim = trim[:trim.index("\n    def ", 1)]
        self.assertIn("projectile_registry_overflow_keys", trim)
        self.assertIn("destroy=True", trim)

        spawn = server[server.index("def _spawn_knight_projectiles"):]
        spawn = spawn[:spawn.index("\n    def ", 1)]
        self.assertIn("self._trim_knight_projectile_registry()", spawn)

        hit = server[server.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        self.assertIn("self._discard_knight_projectile_tracking", hit)

    def test_weapon_projectiles_keep_the_item_face_visible_while_spinning(self):
        expected = {
            "axe": (0.001, "tf_slice:knight_axe_projectile"),
            "pickaxe": (0.015, "tf_slice:knight_pickaxe_projectile"),
        }
        for name, (gravity, identifier) in expected.items():
            behavior = json.loads(
                (
                    BP / "entities" / ("knight_%s_projectile.entity.json" % name)
                ).read_text(encoding="utf-8")
            )["minecraft:entity"]
            self.assertAlmostEqual(
                gravity,
                behavior["components"]["minecraft:projectile"]["gravity"],
            )
            on_hit = behavior["components"]["minecraft:projectile"]["on_hit"]
            self.assertNotIn("remove_on_hit", on_hit)
            self.assertEqual(
                "tf_slice:instant_remove",
                on_hit["definition_event"]["event_trigger"]["event"],
            )
            self.assertIn(
                "minecraft:instant_despawn",
                behavior["component_groups"]["tf_slice:instant_remove"],
            )
            self.assertIn("tf_slice:instant_remove", behavior["events"])
            client = json.loads(
                (
                    RP / "entity" / ("knight_%s_projectile.entity.json" % name)
                ).read_text(encoding="utf-8")
            )["minecraft:client_entity"]["description"]
            self.assertEqual(identifier, client["identifier"])
            self.assertEqual(
                "geometry.tf_slice.knight_%s_projectile" % name,
                client["geometry"]["default"],
            )
            self.assertEqual(
                "animation.tf_slice.knight_weapon_projectile.spin",
                client["animations"]["spin"],
            )

        geometries = json.loads(
            (
                RP / "models" / "entity" / "knight_weapon_projectiles.geo.json"
            ).read_text(encoding="utf-8")
        )["minecraft:geometry"]
        geometries = {
            row["description"]["identifier"]: row for row in geometries
        }
        for name, expected_strips in (("axe", 19), ("pickaxe", 17)):
            geometry = geometries[
                "geometry.tf_slice.knight_%s_projectile" % name
            ]
            root = next(
                bone for bone in geometry["bones"] if bone["name"] == "root"
            )
            weapon = next(
                bone for bone in geometry["bones"] if bone["name"] == "weapon"
            )
            # Bedrock's rendered actor-forward axis is local -Z.  After the
            # head-down X half-turn, the generated tool head points +Z; a Y
            # half-turn therefore makes the head (not the broad face normal)
            # follow projectile-forward.  Radial picks then point outward.
            self.assertEqual([0, 180, 0], root["rotation"])
            self.assertEqual("root", weapon["parent"])
            self.assertEqual(expected_strips, len(weapon["cubes"]))
            self.assertTrue(
                all(float(cube["size"][0]) == 0.75 for cube in weapon["cubes"])
            )
            self.assertTrue(
                all(
                    float(cube["size"][2]) >= float(cube["size"][0])
                    and float(cube["uv"]["west"]["uv_size"][1]) > 0.0
                    and float(cube["uv"]["east"]["uv_size"][0]) > 0.0
                    and float(cube["uv"]["west"]["uv_size"][0]) < 0.0
                    for cube in weapon["cubes"]
                )
            )

        animation = json.loads(
            (
                RP / "animations" / "knight_weapon_projectiles.animation.json"
            ).read_text(encoding="utf-8")
        )["animations"]["animation.tf_slice.knight_weapon_projectile.spin"]
        rotation = animation["bones"]["weapon"]["rotation"]
        # Runtime uses the texture's tool head in positive local Y, so the
        # upstream-rate tumble needs a half-turn phase to launch blade/pick
        # head down.  The corrected vector yaw supplies the target direction.
        self.assertEqual(["query.life_time * 200 + 180", 0, 0], rotation)

        registry = json.loads(
            (ROOT / "model_acceptance" / "registry.json").read_text(
                encoding="utf-8"
            )
        )
        entries = {entry["id"]: entry for entry in registry["entities"]}
        for name in ("axe", "pickaxe"):
            bedrock = entries["knight_%s_projectile" % name]["bedrock"]
            self.assertEqual(
                "geometry.tf_slice.knight_%s_projectile" % name,
                bedrock["identifier"],
            )
            self.assertEqual(
                "TwilightBossSliceR/models/entity/knight_weapon_projectiles.geo.json",
                bedrock["geometry"],
            )
        registry_source = (
            ROOT / "tools" / "phantom_urghast_model_registry.py"
        ).read_text(encoding="utf-8")
        for name in ("axe", "pickaxe"):
            self.assertIn(
                '"geometryId": "geometry.tf_slice.knight_%s_projectile"' % name,
                registry_source,
            )
        self.assertIn(
            '"geometry": "TwilightBossSliceR/models/entity/knight_weapon_projectiles.geo.json"',
            registry_source,
        )

    def test_runtime_missing_knight_members_expire_only_during_an_active_encounter(self):
        import knight_route_logic as logic

        group = logic.create_group_state("runtime-missing", (0, 40, 0), range(6))
        member = logic.member_by_slot(group, 1)
        for _unused in range(logic.RUNTIME_MISSING_GRACE_TICKS - 1):
            self.assertFalse(
                logic.runtime_member_stale(member, False, True)
            )
        self.assertEqual(
            logic.RUNTIME_MISSING_GRACE_TICKS - 1,
            member["runtimeMissingTicks"],
        )
        self.assertFalse(logic.runtime_member_stale(member, True, True))
        self.assertEqual(0, member["runtimeMissingTicks"])

        for _unused in range(logic.RUNTIME_MISSING_GRACE_TICKS + 5):
            self.assertFalse(
                logic.runtime_member_stale(member, False, False)
            )
        self.assertEqual(0, member["runtimeMissingTicks"])

        for _unused in range(logic.RUNTIME_MISSING_GRACE_TICKS - 1):
            self.assertFalse(
                logic.runtime_member_stale(member, False, True)
            )
        self.assertTrue(logic.runtime_member_stale(member, False, True))

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        self.assertIn("def _reconcile_knight_runtime_members", server)
        reconcile = server[server.index("def _reconcile_knight_runtime_members"):]
        reconcile = reconcile[:reconcile.index("\n    def ", 1)]
        self.assertIn("runtime_member_stale", reconcile)
        self.assertIn("record_knight_member_death", reconcile)
        driver = server[server.index("def _drive_knight_phantoms"):]
        driver = driver[:driver.index("\n    def ", 1)]
        self.assertLess(
            driver.index("self._reconcile_knight_runtime_members"),
            driver.index("knight_route_logic.renumber_living_members(group)"),
        )

    def test_wall_escape_detects_real_stall_and_targets_the_safe_room_center(self):
        import knight_route_logic as logic

        group = logic.create_group_state("wall-escape", (0, 40, 0), range(6))
        member = logic.member_by_slot(group, 0)
        current = (7.5, 41.0, 0.0)
        destination = (0.0, 41.0, 0.0)

        self.assertFalse(
            logic.advance_wall_escape(member, current, destination, True)
        )
        for _unused in range(logic.WALL_STALL_TRIGGER_TICKS - 1):
            self.assertFalse(
                logic.advance_wall_escape(member, current, destination, True)
            )
        self.assertTrue(
            logic.advance_wall_escape(member, current, destination, True)
        )
        self.assertEqual(logic.WALL_ESCAPE_TICKS, member["wallEscapeTicks"])
        escape = logic.wall_escape_destination(group, member)
        self.assertEqual((0.0, 0.0), (escape[0], escape[2]))
        self.assertTrue(
            logic.advance_wall_escape(member, (7.0, 41.0, 0.0), escape, True)
        )

        self.assertFalse(
            logic.advance_wall_escape(member, current, destination, False)
        )
        self.assertEqual(0, member["runtimeStallTicks"])
        self.assertEqual(0, member["wallEscapeTicks"])

        same_destination = current
        member["runtimeLastPosition"] = None
        self.assertFalse(
            logic.advance_wall_escape(
                member, current, same_destination, True, blocked=True
            )
        )
        for _unused in range(logic.WALL_STALL_TRIGGER_TICKS - 2):
            self.assertFalse(
                logic.advance_wall_escape(
                    member, current, same_destination, True, blocked=True
                )
            )
        self.assertTrue(
            logic.advance_wall_escape(
                member, current, same_destination, True, blocked=True
            )
        )

        jittering = logic.member_by_slot(
            logic.create_group_state("wall-jitter", (0, 40, 0), range(6)), 0
        )
        triggered = False
        for tick in range(logic.WALL_STALL_TRIGGER_TICKS):
            # Collision resolution can move an embedded Bedrock actor by more
            # than the ordinary stall epsilon every frame.  Continuous solid
            # contact must still trigger recovery.
            triggered = logic.advance_wall_escape(
                jittering,
                (7.5 + tick * 0.10, 41.0, 0.0),
                destination,
                True,
                blocked=True,
            )
        self.assertTrue(triggered)

        rescue = logic.wall_escape_relocation(
            (7.5, 41.0, 0.0),
            logic.wall_escape_destination(group, member),
        )
        self.assertEqual(0.5, logic.WALL_ESCAPE_RELOCATION_STEP)
        self.assertEqual((7.0, 41.0, 0.0), rescue)
        self.assertLess(
            logic.horizontal_distance(rescue, (0.0, 41.0, 0.0)),
            logic.horizontal_distance((7.5, 41.0, 0.0), (0.0, 41.0, 0.0)),
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        driver = server[server.index("def _drive_knight_phantoms"):]
        driver = driver[:driver.index("\n    def ", 1)]
        relocation = server[server.index("def _relocate_knight_from_wall"):]
        relocation = relocation[:relocation.index("\n    def ", 1)]
        self.assertIn("def _knight_wall_contact", server)
        self.assertIn("CF.CreatePos(entityId).SetPos(rescuePosition)", relocation)
        self.assertIn("blockedWall", driver)
        self.assertIn("knight_route_logic.advance_wall_escape", driver)
        self.assertIn("knight_route_logic.wall_escape_destination", driver)
        self.assertIn("self._relocate_knight_from_wall", driver)
        self.assertIn("or escapeActive", driver)
        self.assertLess(
            driver.index("knight_route_logic.advance_wall_escape"),
            driver.index("noClip = bool"),
        )

    def test_knight_motion_uses_slower_separate_cruise_charge_and_escape_speeds(self):
        import knight_route_logic as logic

        self.assertEqual(0.20, logic.knight_move_speed(False, False))
        self.assertEqual(0.40, logic.knight_move_speed(True, False))
        self.assertEqual(0.30, logic.knight_move_speed(False, True))
        self.assertEqual(0.30, logic.knight_move_speed(True, True))

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        driver = server[server.index("def _drive_knight_phantoms"):]
        driver = driver[:driver.index("\n    def ", 1)]
        self.assertIn("knight_route_logic.knight_move_speed", driver)
        self.assertNotIn(
            "speed = 0.65 if charging or escapeActive else 0.30", driver
        )

    def test_single_sword_charge_passes_through_its_snapshot_instead_of_stopping(self):
        import knight_route_logic as logic

        direction = logic.charge_direction((0.0, 41.0, 0.0), (10.0, 41.0, 0.0))
        self.assertEqual((1.0, 0.0, 0.0), direction)
        self.assertEqual(
            (0.4, 0.0, 0.0),
            logic.knight_motion_vector(
                (9.5, 41.0, 0.0),
                (10.0, 41.0, 0.0),
                0.4,
                charge_direction=direction,
            ),
        )
        self.assertEqual(
            (0.4, 0.0, 0.0),
            logic.knight_motion_vector(
                (10.5, 41.0, 0.0),
                (10.0, 41.0, 0.0),
                0.4,
                charge_direction=direction,
            ),
        )
        self.assertEqual(
            (-0.2, 0.0, 0.0),
            logic.knight_motion_vector(
                (10.5, 41.0, 0.0),
                (10.0, 41.0, 0.0),
                0.2,
            ),
        )

        group = logic.create_group_state("solo-through", (0, 40, 0), range(6))
        survivor = logic.member_by_slot(group, 0)
        survivor["chargeVector"] = list(direction)
        restored = logic.load_group_state(json.loads(json.dumps(group)))
        self.assertEqual(
            list(direction), logic.member_by_slot(restored, 0)["chargeVector"]
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        driver = server[server.index("def _drive_knight_phantoms"):]
        driver = driver[:driver.index("\n    def ", 1)]
        self.assertIn('member["chargeVector"]', driver)
        self.assertIn("knight_route_logic.charge_direction", driver)
        self.assertIn("knight_route_logic.knight_motion_vector", driver)

    def test_knight_particle_budget_removes_throw_emitters_and_throttles_repeats(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        driver = server[server.index("def _drive_knight_phantoms"):]
        driver = driver[:driver.index("\n    def ", 1)]
        self.assertIn(
            'int(member.get("formationTick", 0)) % 4 == 0',
            driver,
        )
        death = server[server.index("def _drive_knight_member_death"):]
        death = death[:death.index("\n    def ", 1)]
        self.assertIn("self._tick % 10 == 0", death)

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        effects = client[client.index("def OnKnightPhantomEffect"):]
        effects = effects[:effects.index("\n    def ", 1)]
        self.assertIn('"charge_smoke": 1', effects)
        self.assertIn('"throw_axe": 0', effects)
        self.assertIn('"throw_pick": 0', effects)
        self.assertIn('"death_hold": 1', effects)

    def test_knight_projectiles_cannot_damage_any_phantom_member(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        spawn = source[source.index("def _spawn_knight_projectiles"):]
        spawn = spawn[:spawn.index("\n    def ", 1)]
        hit = source[source.index("def OnProjectileDoHitEffectEvent"):]
        hit = hit[:hit.index("\n    def ", 1)]
        damage = source[source.index("def OnHealthChangeBefore"):]
        damage = damage[:damage.index("\n    def ", 1)]
        self.assertIn("projectile_launch", spawn)
        self.assertIn("self._knight_projectiles", spawn)
        self.assertIn("KNIGHT_PHANTOM_IDENTIFIER", hit)
        self.assertIn("self._knight_projectiles", hit)
        self.assertIn("args[\"cancel\"] = True", hit)
        self.assertIn("_knight_projectile_damage_source", damage)

    def test_zero_combat_members_hide_the_boss_bar_before_death_cleanup(self):
        import boss_hud_logic
        import knight_route_logic as logic

        group = logic.create_group_state("hud", (0, 40, 0), range(6))
        self.assertTrue(logic.boss_bar_visible(group))
        for slot in range(6):
            self.assertTrue(logic.begin_member_death(group, slot, "alice"))
        self.assertEqual(0, logic.combat_member_count(group))
        self.assertFalse(logic.boss_bar_visible(group))

        stale = {
            "id": "knight_group:hud",
            "kind": "knight_phantoms",
            "health": 0.0,
            "maxHealth": 210.0,
            "membersAlive": 0,
            "dimensionId": 1,
            "position": [0, 40, 0],
            "hudVisible": True,
        }
        self.assertEqual(
            [],
            boss_hud_logic.visible_bosses(
                [stale], "knight_phantoms", 1, (0, 40, 0), 64
            ),
        )

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        knight_hud = server[server.index("knightGroups ="):]
        knight_hud = knight_hud[:knight_hud.index("for bossId, state in self._ur_ghasts")]
        self.assertIn("boss_bar_visible", knight_hud)
        self.assertIn("combat_member_count", knight_hud)

    def test_in_wall_damage_is_ignored_and_old_survivors_are_repaired_once(self):
        import knight_route_logic as logic

        for cause in ("suffocation", "in_wall", "inWall", "IN WALL"):
            self.assertTrue(logic.ignores_environmental_damage(cause))
        for cause in ("fire", "lava", "fall", "entity_attack", ""):
            self.assertFalse(logic.ignores_environmental_damage(cause))

        group = logic.create_group_state("repair", (0, 40, 0), range(6))
        logic.member_by_slot(group, 0)["health"] = 3.0
        logic.member_by_slot(group, 1)["health"] = 12.0
        dying = logic.member_by_slot(group, 2)
        dying["health"] = 0.0
        dying["dying"] = True

        repaired = logic.repair_environment_damage(group)

        self.assertEqual([0, 1], [member["slot"] for member in repaired])
        self.assertEqual(35.0, logic.member_by_slot(group, 0)["health"])
        self.assertEqual(35.0, logic.member_by_slot(group, 1)["health"])
        self.assertEqual(0.0, dying["health"])
        self.assertEqual([], logic.repair_environment_damage(group))

    def test_server_cancels_in_wall_damage_before_armor_or_death_logic(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        damage = source[source.index("def OnHealthChangeBefore"):]
        damage = damage[:damage.index("\n    def ", 1)]
        self.assertIn("ignores_environmental_damage", damage)
        self.assertLess(
            damage.index("ignores_environmental_damage"),
            damage.index("shield_blocks"),
        )
        self.assertIn("repair_environment_damage", source)
        self.assertIn("_set_health(entityId, knight_route_logic.MEMBER_MAX_HEALTH)", source)

    def test_depletion_uses_stable_slots_and_renumbers_living_roles(self):
        import knight_route_logic as logic

        group = logic.create_group_state("depletion", (0, 40, 0), range(6))

        self.assertFalse(logic.record_member_death(group, 0))

        self.assertEqual([0], group["deathSlots"])
        survivors = [member for member in group["members"] if member["alive"]]
        self.assertEqual([1, 2, 3, 4, 5], [member["slot"] for member in survivors])
        self.assertEqual([0, 1, 2, 3, 4], [member["number"] for member in survivors])
        self.assertEqual([0, 1, 2, 0, 1], [member["role"] for member in survivors])
        self.assertEqual(1, logic.member_by_slot(group, 1)["slot"])
        self.assertEqual(0, logic.member_by_slot(group, 1)["number"])

        self.assertFalse(logic.record_member_death(group, 3))
        self.assertEqual([0, 3], group["deathSlots"])
        self.assertFalse(logic.member_by_slot(group, 3)["alive"])
        self.assertEqual(
            list(range(4)),
            [member["number"] for member in group["members"] if member["alive"]],
        )

    def test_schema_v2_backfills_stable_slots_without_changing_death_identity(self):
        import knight_route_logic as logic

        group = logic.create_group_state("slots", (0, 40, 0), range(6))
        group["deathSlots"] = [1]
        for member in group["members"]:
            member.pop("slot", None)
        group["members"][1]["alive"] = False

        restored = logic.load_group_state(group)

        self.assertEqual(list(range(6)), [member["slot"] for member in restored["members"]])
        self.assertEqual([1], restored["deathSlots"])
        self.assertFalse(logic.member_by_slot(restored, 1)["alive"])

    def test_hard_mode_slot_five_uses_the_source_guard_cycle(self):
        import knight_route_logic as logic

        group = logic.create_group_state("shield", (0, 40, 0), range(6))
        self.assertEqual(
            [],
            logic.apply_difficulty_equipment(group, 2),
        )
        changed = logic.apply_difficulty_equipment(group, 3)
        self.assertEqual([5], [member["slot"] for member in changed])
        shield = logic.member_by_slot(group, 5)
        self.assertTrue(shield["shieldEquipped"])

        self.assertTrue(logic.advance_guard(shield, has_target=True, ticks=1))
        self.assertTrue(logic.shield_blocks(shield, from_front=True))
        self.assertFalse(logic.shield_blocks(shield, from_front=False))
        self.assertFalse(logic.shield_blocks(shield, from_front=True, bypass=True))

        shield["formation"] = "attack_player_attack"
        self.assertFalse(logic.advance_guard(shield, has_target=True, ticks=1))
        shield["formation"] = "hover"
        logic.advance_guard(shield, has_target=True, ticks=181)
        self.assertFalse(shield["isGuard"])
        self.assertFalse(shield["guarding"])
        logic.advance_guard(shield, has_target=True, ticks=182)
        self.assertTrue(shield["isGuard"])
        self.assertTrue(shield["guarding"])

    def test_server_syncs_dynamic_weapons_offhand_shield_and_front_blocking(self):
        source = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        drive = source[source.index("def _drive_knight_phantoms"):]
        drive = drive[:drive.index("\n    def ", 1)]
        damage = source[source.index("def OnHealthChangeBefore"):]
        damage = damage[:damage.index("\n    def ", 1)]
        self.assertIn("_sync_knight_member_equipment", drive)
        self.assertIn("advance_guard", drive)
        self.assertIn("tf_slice:start_guarding", drive)
        self.assertIn("shield_blocks", damage)
        self.assertIn("fromFront", damage)

        equipment = source[source.index("def _sync_knight_member_equipment"):]
        equipment = equipment[:equipment.index("\n    def ", 1)]
        self.assertIn("_set_entity_offhand_item", equipment)
        self.assertIn("tf_slice:knightmetal_shield", equipment)
        self.assertIn("visualRole", equipment)

    def test_member_death_uses_the_source_eighteen_plus_seventy_tick_timeline(self):
        import knight_route_logic as logic

        group = logic.create_group_state("death", (0, 40, 0), range(6))
        self.assertTrue(logic.begin_member_death(group, 2, "alice"))
        self.assertFalse(logic.begin_member_death(group, 2, "alice"))
        dying = logic.member_by_slot(group, 2)
        self.assertTrue(dying["dying"])
        self.assertEqual(0.0, dying["health"])
        self.assertEqual("alice", dying["deathSourceId"])
        self.assertEqual(
            list(range(5)),
            [member["number"] for member in group["members"] if member["alive"] and not member["dying"]],
        )
        group = logic.load_group_state(json.loads(json.dumps(group)))
        dying = logic.member_by_slot(group, 2)
        self.assertTrue(dying["dying"])

        ascent = logic.advance_member_death(dying, 17)
        self.assertTrue(ascent["ascent"])
        self.assertFalse(ascent["hide"])
        hidden = logic.advance_member_death(dying, 1)
        self.assertTrue(hidden["hide"])
        self.assertFalse(hidden["finish"])
        trail = logic.advance_member_death(dying, 1)
        self.assertAlmostEqual(1.0 / 70.0, trail["trailFraction"])
        finished = logic.advance_member_death(dying, 69)
        self.assertTrue(finished["finish"])
        self.assertEqual(88, dying["deathTick"])

    def test_early_deaths_hold_until_the_full_group_sequence_is_released(self):
        import knight_route_logic as logic

        group = logic.create_group_state("held-deaths", (0, 40, 0), range(6))
        self.assertTrue(logic.begin_member_death(group, 0, "alice"))
        first = logic.member_by_slot(group, 0)
        hidden = logic.advance_member_death(first, 18, release=False)
        self.assertTrue(hidden["hide"])
        held = logic.advance_member_death(first, 200, release=False)
        self.assertTrue(held["hold"])
        self.assertFalse(held["finish"])
        self.assertEqual(18, first["deathTick"])

        for slot in range(1, 6):
            self.assertTrue(logic.begin_member_death(group, slot, "alice"))

        self.assertTrue(group["deathSequenceReleased"])
        self.assertTrue(
            all(member["dying"] for member in group["members"])
        )
        self.assertTrue(
            all(member["deathRestartPending"] for member in group["members"])
        )
        self.assertEqual(
            [0] * 6,
            [member["deathTick"] for member in group["members"]],
        )

    def test_knight_presentation_binds_guard_death_and_builtin_sounds(self):
        entity = json.loads(
            (BP / "entities" / "knight_phantom.entity.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:entity"]
        properties = entity["description"]["properties"]
        self.assertIn("tf_slice:guarding", properties)
        self.assertIn("tf_slice:dying_hidden", properties)
        self.assertIn("minecraft:ambient_sound_interval", entity["components"])
        self.assertTrue(
            entity["events"]["tf_slice:start_guarding"]["set_property"][
                "tf_slice:guarding"
            ]
        )
        self.assertFalse(
            entity["events"]["tf_slice:stop_guarding"]["set_property"][
                "tf_slice:guarding"
            ]
        )
        self.assertTrue(
            entity["events"]["tf_slice:hide_dying"]["set_property"][
                "tf_slice:dying_hidden"
            ]
        )

        client = json.loads(
            (RP / "entity" / "knight_phantom.entity.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:client_entity"]["description"]
        self.assertIn("tf_slice:dying_hidden", client["scripts"]["scale"])

        sounds = json.loads(
            (RP / "sounds.json").read_text(encoding="utf-8")
        )["entity_sounds"]["entities"]["tf_slice:knight_phantom"]
        self.assertEqual("mob.skeleton.say", sounds["events"]["ambient"])
        self.assertEqual("mob.skeleton.hurt", sounds["events"]["hurt"])
        self.assertEqual("mob.skeleton.death", sounds["events"]["death"])

    def test_knight_weapon_role_sync_preserves_the_original_held_item_pose(self):
        entity = json.loads(
            (BP / "entities" / "knight_phantom.entity.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:entity"]
        role = entity["description"]["properties"]["tf_slice:weapon_role"]
        self.assertEqual("int", role["type"])
        self.assertEqual([0, 2], role["range"])
        self.assertTrue(role["client_sync"])
        for name, value in (("sword", 0), ("axe", 1), ("pickaxe", 2)):
            event = entity["events"]["tf_slice:set_weapon_role_%s" % name]
            self.assertEqual(
                value,
                event["set_property"]["tf_slice:weapon_role"],
            )

        animation = json.loads(
            (
                RP / "animations" / "phantom_urghast_route.animation.json"
            ).read_text(encoding="utf-8")
        )["animations"]["animation.tf_slice.knight_phantom.move"]["bones"]
        # Equipment role synchronization must not rotate the held-item bone.
        # The pre-fix grip already matched the runtime reference video.
        self.assertNotIn("rightItem", animation)

        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        equipment = server[server.index("def _sync_knight_member_equipment"):]
        equipment = equipment[:equipment.index("\n    def ", 1)]
        for event in (
            "tf_slice:set_weapon_role_sword",
            "tf_slice:set_weapon_role_axe",
            "tf_slice:set_weapon_role_pickaxe",
        ):
            self.assertIn(event, equipment)
        generator = (
            ROOT / "tools" / "build_phantom_urghast_models.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn('phantom["bones"]["rightItem"]', generator)

    def test_server_and_client_wire_knight_charge_throw_guard_and_death_effects(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        damage = server[server.index("def OnHealthChangeBefore"):]
        damage = damage[:damage.index("\n    def ", 1)]
        self.assertIn("begin_member_death", damage)
        self.assertIn("args[\"cancel\"] = True", damage)
        self.assertIn("def _drive_knight_member_death", server)
        self.assertIn("def _broadcast_knight_phantom_effect", server)
        self.assertIn('BroadcastToAllClient("KnightPhantomEffect"', server)
        self.assertIn('"KnightPhantomEffect"', client)
        self.assertIn("self.OnKnightPhantomEffect", client)
        self.assertIn("def OnKnightPhantomEffect", client)
        effect = client[client.index("def OnKnightPhantomEffect"):]
        effect = effect[:effect.index("\n    def ", 1)]
        for kind in (
            "charge_smoke", "throw_axe", "throw_pick",
            "shield_block", "death_poof", "death_trail",
        ):
            self.assertIn(kind, effect)

    def test_knight_death_smoke_uses_a_bounded_blended_particle(self):
        particle = json.loads(
            (
                RP / "particles" / "knight_phantom_smoke.json"
            ).read_text(encoding="utf-8")
        )["particle_effect"]
        self.assertEqual(
            "tf_slice:knight_phantom_smoke",
            particle["description"]["identifier"],
        )
        self.assertEqual(
            "particles_blend",
            particle["description"]["basic_render_parameters"]["material"],
        )
        size = particle["components"][
            "minecraft:particle_appearance_billboard"
        ]["size"]
        self.assertLessEqual(max(float(value) for value in size), 0.25)
        color = particle["components"][
            "minecraft:particle_appearance_tinting"
        ]["color"]
        self.assertLessEqual(float(color[3]), 0.7)

        client = (PACKAGE / "clientSystem.py").read_text(encoding="utf-8")
        effect = client[client.index("def OnKnightPhantomEffect"):]
        effect = effect[:effect.index("\n    def ", 1)]
        for kind in ("death_start", "death_poof", "death_hold"):
            self.assertIn(
                '"%s": "tf_slice:knight_phantom_smoke"' % kind,
                effect,
            )
        trail = effect[effect.index('if kind == "death_trail"'):]
        trail = trail[:trail.index("return", 1)]
        self.assertIn("tf_slice:knight_phantom_smoke", trail)
        self.assertNotIn("minecraft:basic_smoke_particle", trail)

    def test_reload_and_final_reward_are_idempotent(self):
        import knight_route_logic as logic

        group = logic.create_group_state("g", (0, 64, 0), range(6))
        group["participants"] = ["alice", "bob"]
        for number in range(6):
            self.assertEqual(number == 5, logic.record_member_death(group, number))
        self.assertTrue(group["defeated"])
        self.assertTrue(logic.claim_reward(group))
        self.assertFalse(logic.claim_reward(group))
        restored = logic.load_group_state(json.loads(json.dumps(group)))
        self.assertEqual(list(range(6)), restored["deathSlots"])
        self.assertFalse(logic.claim_reward(restored))

    def test_peaceful_reset_rearms_single_group_marker(self):
        import knight_route_logic as logic

        group = logic.create_group_state("g", (0, 64, 0), range(6))
        group["deathSlots"] = [1, 3]
        reset = logic.reset_for_peaceful(group)
        self.assertEqual("rearm_marker", reset["state"])
        self.assertEqual(6, len(reset["members"]))
        self.assertEqual(list(range(6)), [member["slot"] for member in reset["members"]])
        self.assertEqual(["hover"] * 6, [member["formation"] for member in reset["members"]])
        self.assertTrue(all(member["entityId"] is None for member in reset["members"]))
        self.assertFalse(reset["rewardClaimed"])

    def test_pedestal_only_credits_nearby_lich_winners(self):
        import knight_route_logic as logic

        players = [
            {"id": "alice", "distance": 4, "progress": {"lich_defeated": True}},
            {"id": "bob", "distance": 4, "progress": {"lich_defeated": False}},
            {"id": "cara", "distance": 24, "progress": {"lich_defeated": True}},
        ]
        result = logic.activate_trophy_pedestal(
            "tf_slice:lich_trophy", players, 16
        )
        self.assertEqual(["alice"], result["creditedPlayers"])
        self.assertTrue(result["removeShieldWalls"])
        self.assertFalse(result["consumeTrophy"])

    def test_pedestal_accepts_nearby_creative_players_without_lich_progress(self):
        import knight_route_logic as logic

        result = logic.activate_trophy_pedestal(
            "tf_slice:naga_trophy",
            [
                {
                    "id": "builder",
                    "distance": 3,
                    "creative": True,
                    "progress": {"lich_defeated": False},
                }
            ],
            16,
        )

        self.assertEqual(["builder"], result["creditedPlayers"])
        self.assertTrue(result["removeShieldWalls"])

    def test_placing_a_trophy_checks_the_pedestal_below_like_upstream(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        placement = server[server.index("def OnServerEntityTryPlaceBlockEvent"):]
        placement = placement[:placement.index("\n    def ", 1)]
        activation = server[server.index("def _activate_placed_trophy"):]
        activation = activation[:activation.index("\n    def ", 1)]

        self.assertIn("self._activate_placed_trophy", placement)
        self.assertIn("position[1] - 1", activation)
        self.assertIn('"tf_slice:trophy_pedestal"', activation)
        self.assertIn("_activate_stronghold_pedestal_at", activation)

    def test_placeable_lich_trophy_participates_in_pedestal_activation(self):
        server = (PACKAGE / "serverSystem.py").read_text(encoding="utf-8")
        trophy_blocks = server[server.index("TROPHY_BLOCKS = frozenset("):]
        trophy_blocks = trophy_blocks[:trophy_blocks.index("\n)") + 2]

        self.assertIn('"tf_slice:lich_trophy"', trophy_blocks)


class KnightStrongholdLootParityTests(unittest.TestCase):
    def _loot(self, name):
        return json.loads(
            (
                BP
                / "loot_tables"
                / "chests"
                / "tf_slice"
                / (name + ".json")
            ).read_text(encoding="utf-8")
        )

    def test_source_pool_structure_and_boss_rewards_are_preserved(self):
        self.assertEqual(3, len(self._loot("stronghold_cache")["pools"]))
        self.assertEqual(3, len(self._loot("stronghold_room")["pools"]))
        boss = self._loot("stronghold_boss")
        self.assertEqual(4, len(boss["pools"]))
        names = {
            entry["name"]
            for pool in boss["pools"]
            for entry in pool["entries"]
        }
        self.assertTrue(
            {
                "tf_slice:knightmetal_sword",
                "tf_slice:knightmetal_pickaxe",
                "tf_slice:knightmetal_axe",
                "tf_slice:phantom_helmet",
                "tf_slice:phantom_chestplate",
                "tf_slice:knight_phantom_trophy_item",
            }.issubset(names)
        )

    def test_knight_phantom_trophy_is_a_registered_placeable_block(self):
        path = BP / "netease_blocks" / "knight_phantom_trophy.json"
        self.assertTrue(path.is_file())
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(
            "tf_slice:knight_phantom_trophy",
            document["minecraft:block"]["description"]["identifier"],
        )


if __name__ == "__main__":
    unittest.main()
