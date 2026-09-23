# -*- coding: utf-8 -*-
import json
import pathlib
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_lich_models


ANIMATIONS = (
    ROOT / "TwilightBossSliceR" / "animations" / "lich_entities.animation.json"
)
SPLIT_ANIMATIONS = {
    "lich": ROOT / "TwilightBossSliceR" / "animations" / "lich.animation.json",
    "zombie": ROOT / "TwilightBossSliceR" / "animations" / "zombie.animation.json",
    "death_tome": (
        ROOT / "TwilightBossSliceR" / "animations" / "death_tome.animation.json"
    ),
    "fortification_shields": (
        ROOT
        / "TwilightBossSliceR"
        / "animations"
        / "fortification_shields.animation.json"
    ),
}
CHANNELS = ("position", "rotation", "scale")


def read_combined_animations():
    combined = {"format_version": "1.8.0", "animations": {}}
    for path in SPLIT_ANIMATIONS.values():
        payload = json.loads(path.read_text(encoding="utf-8"))
        combined["animations"].update(payload["animations"])
    return combined


def iter_channel_values(channel):
    if isinstance(channel, list):
        for value in channel:
            yield value
        return
    if isinstance(channel, dict):
        for keyframe in channel.values():
            if isinstance(keyframe, list):
                for value in keyframe:
                    yield value
            elif isinstance(keyframe, dict):
                for side in ("pre", "post"):
                    for value in keyframe.get(side, []):
                        yield value


class LichAnimationCheckerCompatibilityTests(unittest.TestCase):
    def test_mixed_animation_container_is_replaced_by_four_named_groups(self):
        self.assertFalse(ANIMATIONS.exists())
        expected_counts = {
            "lich": 21,
            "zombie": 8,
            "death_tome": 18,
            "fortification_shields": 12,
        }
        all_ids = set()
        for group, path in SPLIT_ANIMATIONS.items():
            self.assertTrue(path.is_file(), str(path))
            payload = json.loads(path.read_text(encoding="utf-8"))
            definitions = payload["animations"]
            self.assertEqual(expected_counts[group], len(definitions), group)
            self.assertFalse(all_ids.intersection(definitions), group)
            all_ids.update(definitions)
        self.assertEqual(59, len(all_ids))

    def test_generated_bundle_matches_checked_in_outputs(self):
        outputs = build_lich_models.generated_files()
        for path, expected in outputs.items():
            actual = (
                path.read_bytes()
                if isinstance(expected, bytes)
                else path.read_text(encoding="utf-8")
            )
            self.assertEqual(expected, actual, str(path))

    def test_dynamic_scale_is_rejected_instead_of_silently_changed(self):
        source = {
            "format_version": "1.8.0",
            "animations": {
                "animation.test": {
                    "bones": {"root": {"scale": ["query.life_time", 1, 1]}}
                }
            },
        }
        with self.assertRaisesRegex(ValueError, "dynamic scale"):
            build_lich_models.build_compatible_animations(source)

    def test_transform_vectors_do_not_contain_molang_strings(self):
        payload = read_combined_animations()
        failures = []
        for animation_id, animation in payload["animations"].items():
            for bone_name, bone in animation.get("bones", {}).items():
                for channel_name in CHANNELS:
                    if channel_name not in bone:
                        continue
                    for value in iter_channel_values(bone[channel_name]):
                        if isinstance(value, str):
                            failures.append(
                                "%s/%s/%s=%s"
                                % (animation_id, bone_name, channel_name, value)
                            )
        self.assertEqual([], failures)

    def test_basis_animations_preserve_each_source_expression_component(self):
        source = build_lich_models.build_source_animations()
        compatible, companions = build_lich_models.build_compatible_animations(source)

        for animation_id, source_animation in source["animations"].items():
            base = compatible["animations"][animation_id]
            helpers = [
                (compatible["animations"][helper_id], weight)
                for helper_id, weight in companions[animation_id]
            ]
            for bone_name, source_bone in source_animation.get("bones", {}).items():
                for channel_name in CHANNELS:
                    source_channel = source_bone.get(channel_name)
                    if not isinstance(source_channel, list):
                        continue
                    base_channel = base["bones"][bone_name][channel_name]
                    for axis, source_value in enumerate(source_channel):
                        if not isinstance(source_value, str):
                            self.assertEqual(source_value, base_channel[axis])
                            continue
                        base_value, weight, helper_value = (
                            build_lich_models.compatibility_basis(
                                source_value, channel_name
                            )
                        )
                        self.assertEqual(base_value, base_channel[axis])
                        matching = []
                        for helper, helper_weight in helpers:
                            helper_channel = (
                                helper.get("bones", {})
                                .get(bone_name, {})
                                .get(channel_name)
                            )
                            if helper_channel is None:
                                continue
                            if helper_channel[axis] != 0:
                                matching.append(
                                    (helper_weight, helper_channel[axis])
                                )
                        self.assertEqual([(weight, helper_value)], matching)

    def test_compatibility_weights_are_normalized_and_signed(self):
        for channel_name in ("position", "rotation"):
            base_value, weight, helper_value = build_lich_models.compatibility_basis(
                "query.test_value", channel_name
            )
            amplitude = (
                build_lich_models.COMPATIBILITY_CHANNEL_AMPLITUDES[channel_name]
            )
            self.assertEqual(-amplitude, base_value)
            self.assertEqual(amplitude * 2, helper_value)
            self.assertIn("math.clamp", weight)
            self.assertIn("0, 1", weight)
            if channel_name == "rotation":
                self.assertIn("math.mod", weight)

    def test_generated_animation_counts_stay_within_cloud_packager_budget(self):
        payload = read_combined_animations()
        definitions = payload["animations"]
        helpers = [
            key
            for key in definitions
            if key.startswith(build_lich_models.COMPATIBILITY_ANIMATION_PREFIX)
        ]
        self.assertEqual(59, len(definitions))
        self.assertEqual(52, len(helpers))

        expected_entries = {
            "lich.entity.json": 21,
            "lich_shadow_clone.entity.json": 12,
            "lich_minion.entity.json": 8,
            "loyal_zombie.entity.json": 8,
            "death_tome.entity.json": 18,
            "fortification_shield_visual.entity.json": 12,
        }
        for file_name, expected in expected_entries.items():
            description = json.loads(
                (ROOT / "TwilightBossSliceR" / "entity" / file_name).read_text(
                    encoding="utf-8"
                )
            )["minecraft:client_entity"]["description"]
            self.assertEqual(expected, len(description["animations"]), file_name)
            self.assertEqual(expected, len(description["scripts"]["animate"]), file_name)

    def test_every_helper_animation_is_activated_by_its_consuming_entity(self):
        source = build_lich_models.build_source_animations()
        unused_payload, companions = build_lich_models.build_compatible_animations(
            source
        )
        for relative_path, animation_ids in (
            build_lich_models.COMPATIBILITY_ENTITY_GROUPS.items()
        ):
            description = json.loads(
                (ROOT / relative_path).read_text(encoding="utf-8")
            )["minecraft:client_entity"]["description"]
            aliases = description["animations"]
            animate = description["scripts"]["animate"]
            weighted = {
                alias: weight
                for entry in animate
                if isinstance(entry, dict)
                for alias, weight in entry.items()
            }
            for animation_id in animation_ids:
                for helper_id, weight in companions[animation_id]:
                    alias = build_lich_models.compatibility_alias(helper_id)
                    self.assertEqual(helper_id, aliases.get(alias))
                    self.assertEqual(weight, weighted.get(alias))

    def test_animation_file_contains_no_runtime_molang_values(self):
        payload = read_combined_animations()
        strings = []

        def collect(value, path=()):
            if isinstance(value, dict):
                for key, child in value.items():
                    collect(child, path + (key,))
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    collect(child, path + (index,))
            elif isinstance(value, str):
                strings.append((path, value))

        collect(payload)
        self.assertEqual([(("format_version",), "1.8.0")], strings)


if __name__ == "__main__":
    unittest.main()
