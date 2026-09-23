# -*- coding: utf-8 -*-
import hashlib
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
RP = ROOT / "TwilightBossSliceR"
sys.path.insert(0, str(BP))

from TwilightBossSlice import release_metadata


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_animations():
    animations = {}
    for name in (
        "lich.animation.json",
        "zombie.animation.json",
        "death_tome.animation.json",
        "fortification_shields.animation.json",
    ):
        animations.update(read_json(RP / "animations" / name)["animations"])
    return animations


class LichResourceContractTests(unittest.TestCase):
    def test_fortification_visual_reuses_the_lich_shield_assets(self):
        client = read_json(RP / "entity" / "fortification_shield_visual.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        controllers = read_json(
            RP / "render_controllers" / "lich.render_controllers.json"
        )["render_controllers"]
        animations = read_animations()

        self.assertEqual("tf_slice:fortification_shield_visual", client["identifier"])
        lich = read_json(RP / 'entity/lich.entity.json')['minecraft:client_entity']['description']
        self.assertEqual(lich['materials']['shield'], client['materials']['shield'])
        self.assertEqual("geometry.tf_slice.fortification_shields", client["geometry"]["default"])
        visual_geometry = read_json(RP / 'models/entity/fortification_shields.geo.json')['minecraft:geometry'][0]
        lich_geometry = read_json(
            RP / 'models/entity/lich_shields.geo.json'
        )['minecraft:geometry'][0]
        self.assertEqual(lich_geometry['bones'], [b for b in visual_geometry['bones'] if not b['name'].startswith('tf_')])
        probes = {b['name'] for b in visual_geometry['bones'] if b['name'].startswith('tf_')}
        self.assertEqual({'tf_anchor', 'tf_basis_x', 'tf_basis_y', 'tf_basis_z'}, probes)
        self.assertGreaterEqual(visual_geometry['description']['visible_bounds_width'], 24)
        self.assertGreaterEqual(visual_geometry['description']['visible_bounds_height'], 24)
        self.assertEqual(
            "animation.tf_slice.fortification_shields",
            client["animations"]["shields"],
        )
        self.assertIn("shields", client["scripts"]["animate"])
        animation = animations["animation.tf_slice.fortification_shields"]
        self.assertEqual([-4096, -4096, -4096], animation['bones']['root']['position'])
        fortification_animate = client['scripts']['animate']
        fortification_weights = [
            weight
            for entry in fortification_animate
            if isinstance(entry, dict)
            for alias, weight in entry.items()
            if alias.startswith('checker_compat_fortification_shields_')
        ]
        lich_animate = lich['scripts']['animate']
        lich_weights = [
            weight
            for entry in lich_animate
            if isinstance(entry, dict)
            for alias, weight in entry.items()
            if alias.startswith('checker_compat_lich_shields_')
        ]
        serialized_weights = json.dumps(fortification_weights)
        self.assertIn("query.mod.tf_fortification_shields", serialized_weights)
        self.assertNotIn('query.life_time', serialized_weights)
        self.assertIn('query.mod.tf_fortification_time', serialized_weights)
        for expression in lich_weights:
            expected = expression.replace(
                'query.life_time', 'query.mod.tf_fortification_time'
            ).replace(
                'query.variant', 'query.mod.tf_fortification_shields'
            )
            self.assertIn(expected, fortification_weights)

        for name in (
            "controller.render.tf_slice.fortification_shield_fill",
            "controller.render.tf_slice.fortification_shield_frame",
        ):
            self.assertIn(name, client["render_controllers"])
            self.assertEqual('Geometry.default', controllers[name]['geometry'])
            visibility = controllers[name]["part_visibility"]
            for index in range(5):
                self.assertEqual(
                    "query.mod.tf_fortification_shields >= %d" % (index + 1),
                    visibility[index]["shield_%d" % index],
                )
            self.assertFalse(visibility[5]["shield_5"])

        self.assertFalse((RP / "particles" / "fortification_shield_fill.json").exists())
        self.assertFalse((RP / "particles" / "fortification_shield_frame.json").exists())
        behavior = read_json(
            BP / "entities" / "fortification_shield_visual.entity.json"
        )["minecraft:entity"]
        self.assertEqual(client["identifier"], behavior["description"]["identifier"])
        self.assertFalse(behavior["description"]["is_spawnable"])
        self.assertFalse(behavior["components"]["minecraft:physics"]["has_collision"])
        self.assertFalse(behavior["components"]["minecraft:physics"]["has_gravity"])

    def test_twilight_wand_bolt_uses_a_small_dedicated_crossed_plane_model(self):
        client = read_json(RP / "entity" / "twilight_wand_bolt.entity.json")[
            "minecraft:client_entity"
        ]["description"]
        geometry = read_json(
            RP / "models" / "entity" / "twilight_wand_bolt.geo.json"
        )["minecraft:geometry"][0]
        animation = read_json(
            RP / "animations" / "twilight_wand_bolt.animation.json"
        )["animations"]["animation.tf_slice.twilight_wand_bolt.spin"]

        self.assertEqual(
            "geometry.tf_slice.twilight_wand_bolt",
            client["geometry"]["default"],
        )
        cubes = geometry["bones"][1]["cubes"]
        self.assertEqual(2, len(cubes))
        self.assertTrue(all(max(cube["size"]) <= 4 for cube in cubes))
        self.assertTrue(all(0 in cube["size"] for cube in cubes))
        rotation = animation["bones"]["bolt"]["rotation"]
        self.assertEqual([0, "query.life_time * 120", 0], rotation)

    def test_player_scepter_particles_are_dedicated_and_lightweight(self):
        for name, expected_size in (
            ("lifedrain_beam", [0.08, 0.08]),
            ("twilight_scepter_trail", [0.07, 0.07]),
            ("fortification_shield", [0.12, 0.12]),
        ):
            particle = read_json(RP / "particles" / (name + ".json"))[
                "particle_effect"
            ]
            self.assertEqual(
                "tf_slice:" + name,
                particle["description"]["identifier"],
            )
            billboard = particle["components"][
                "minecraft:particle_appearance_billboard"
            ]
            self.assertEqual(expected_size, billboard["size"])

    def test_lich_boss_spawner_has_resource_pack_block_and_texture_mappings(self):
        blocks = read_json(RP / "blocks.json")
        terrain = read_json(RP / "textures" / "terrain_texture.json")
        self.assertIn("tf_slice:lich_boss_spawner", blocks)
        texture_key = blocks["tf_slice:lich_boss_spawner"]["textures"]
        self.assertIn(texture_key, terrain["texture_data"])
        self.assertEqual(
            "textures/blocks/boss_spawner",
            terrain["texture_data"][texture_key]["textures"],
        )

    def test_pack_versions_and_dependency_are_current(self):
        behavior = read_json(BP / "manifest.json")
        resources = read_json(RP / "manifest.json")
        expected = list(release_metadata.PACK_VERSION)
        self.assertEqual(expected, behavior["header"]["version"])
        self.assertEqual(expected, behavior["modules"][0]["version"])
        self.assertEqual(expected, behavior["dependencies"][0]["version"])
        self.assertEqual(expected, resources["header"]["version"])
        self.assertEqual(expected, resources["modules"][0]["version"])

    def test_all_entities_and_projectiles_have_both_pack_contracts(self):
        identifiers = (
            "lich",
            "lich_shadow_clone",
            "lich_minion",
            "death_tome",
            "loyal_zombie",
            "lich_bolt",
            "lich_bomb",
            "tome_bolt",
            "twilight_wand_bolt",
        )
        for name in identifiers:
            behavior = read_json(BP / "entities" / (name + ".entity.json"))
            client = read_json(RP / "entity" / (name + ".entity.json"))
            self.assertEqual(
                "tf_slice:" + name,
                behavior["minecraft:entity"]["description"]["identifier"],
            )
            self.assertEqual(
                "tf_slice:" + name,
                client["minecraft:client_entity"]["description"]["identifier"],
            )

    def test_locked_asset_hashes_match_resource_pack(self):
        expected = {
            "textures/entity/tf_slice/twilightlich64.png": "0E0F4DCBC967997892F26385E77A4A7DDD8507BEBEFDA67D502B2FB8BA35A9FD",
            "textures/entity/tf_slice/twilightlich64_clone.png": "3E010B51119079DA081866086C43E3C5EF116D7C1FABFCE7E69C2CA65A666EEB",
            "textures/items/twilight_scepter.png": "2EAC8E932BD378ADA9D4DA9396531B74B345758BE1BB2B2AAB57345D74F090C7",
            "textures/items/lifedrain_scepter.png": "3E850CA750408FAC3E0EAB6392B5E0121FBDB858FF713E14FFACF4C67107E522",
            "textures/items/zombie_scepter.png": "D533C853207A5EDA7B1CBAE0304C4C1A8C31A152725FAE1BF283D8FC586DC9BD",
            "textures/items/fortification_scepter.png": "E168D1F3AEF0B55024FECBD5957ECDA8ED67E4F538C36114A82575C519757FB0",
            "textures/items/lich_trophy.png": "A25D5A9E8B6D6B3308C733E33C3F2BEDCEEDF8187FFAD4DDA0178151AD812B80",
            "textures/ui/tf_slice/lich_shield_fill.png": "6493E8C27B53FEC337C118C5F3EED95562B8458AC5717F194962B7350D778B9C",
            "textures/ui/tf_slice/lich_shield_frame.png": "C52AAC5B292EAF89E12566A77B9F0B224B8DBED5E72085A8208B408E5BBA27B7",
        }
        for relative, digest in expected.items():
            actual = hashlib.sha256((RP / relative).read_bytes()).hexdigest().upper()
            self.assertEqual(digest, actual, relative)

    def test_complete_entity_entries_stop_at_offline_states(self):
        registry = read_json(ROOT / "model_acceptance" / "registry.json")
        entries = dict((entry["id"], entry) for entry in registry["entities"])
        for name in ("lich", "death_tome", "lich_minion", "loyal_zombie"):
            expected = "rejected" if name in ("lich", "death_tome") else "candidate"
            self.assertEqual(expected, entries[name]["status"])
            self.assertEqual("implemented", entries[name]["behavior"]["status"])
            self.assertTrue(entries[name].get("offline_evidence"))
            self.assertTrue(entries[name]["behavior"].get("evidence"))


if __name__ == "__main__":
    unittest.main()
