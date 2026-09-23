import json
import pathlib
import tempfile
import unittest

from tools import native_structure_worldgen_safety as safety


ROOT = pathlib.Path(__file__).resolve().parents[1]
BP = ROOT / "TwilightBossSliceB"
FEATURES = BP / "netease_features"
FEATURE_RULES = BP / "netease_feature_rules"
DISABLED_TAG = "tf_slice_native_structure_worldgen_disabled"
STAGING_BLOCK_X = 8192
STAGING_BLOCK_Z = 8192
LANDMARK_GRID_BLOCKS = 256
LANDMARK_ENVELOPE_RADIUS = 80
LANDMARK_RULE_PREFIX = "tf_slice:ruin_landmark_surface_"

POST_LANDMARK_ENVIRONMENT_RULES = {
    "tf_slice:enchanted_fallen_log_feature_rule",
    "tf_slice:fallen_hollow_log_feature_rule",
    "tf_slice:hollow_stump_feature_rule",
    "tf_slice:hollow_tree_feature_rule",
    "tf_slice:mushroom_canopy_dense_feature_rule",
    "tf_slice:mushroom_canopy_sparse_feature_rule",
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def nested_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from nested_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from nested_strings(item)


def feature_graph():
    features = {}
    feature_types = {}
    for path in FEATURES.glob("*.json"):
        document = read_json(path)
        component_names = [
            name for name in document if name != "format_version"
        ]
        if not component_names:
            continue
        component_name = component_names[0]
        component = document[component_name]
        identifier = component.get("description", {}).get("identifier")
        if identifier:
            features[identifier] = component
            feature_types[identifier] = component_name

    dependencies = {
        identifier: {
            value
            for value in nested_strings(component)
            if value in features and value != identifier
        }
        for identifier, component in features.items()
    }
    return features, feature_types, dependencies


class NativeStructureWorldgenSafetyTests(unittest.TestCase):
    def test_entry_mode_controls_the_staging_guard(self):
        for direct_entry_enabled in (True, False):
            with self.subTest(direct_entry_enabled=direct_entry_enabled):
                with tempfile.TemporaryDirectory() as directory:
                    root = pathlib.Path(directory)
                    config_path = (
                        root
                        / "TwilightBossSliceB"
                        / "TwilightBossSlice"
                        / "config.py"
                    )
                    config_path.parent.mkdir(parents=True, exist_ok=True)
                    config_path.write_text(
                        "PORTAL_DIRECT_ENTRY_ENABLED = %s\n"
                        % ("True" if direct_entry_enabled else "False"),
                        encoding="utf-8",
                    )
                    write_json(
                        root
                        / "TwilightBossSliceB"
                        / "netease_features"
                        / "test_structure_feature.json",
                        {
                            "format_version": "1.20.30",
                            "netease:structure_feature": {
                                "description": {
                                    "identifier": "tf_slice:test_structure_feature"
                                },
                                "places_structure": "tf_slice:test_structure",
                            },
                        },
                    )
                    rule_path = (
                        root
                        / "TwilightBossSliceB"
                        / "netease_feature_rules"
                        / "test_structure_feature_rule.json"
                    )
                    write_json(
                        rule_path,
                        {
                            "format_version": "1.14.0",
                            "minecraft:feature_rules": {
                                "description": {
                                    "identifier": (
                                        "tf_slice:test_structure_feature_rule"
                                    ),
                                    "places_feature": (
                                        "tf_slice:test_structure_feature"
                                    ),
                                },
                                "conditions": {
                                    "placement_pass": "after_surface_pass",
                                    "minecraft:biome_filter": [],
                                },
                                "distribution": {
                                    "iterations": safety._guarded_iterations(3),
                                    "coordinate_eval_order": "xzy",
                                    "x": 0,
                                    "y": 0,
                                    "z": 0,
                                },
                            },
                        },
                    )

                    result = safety.guard_native_structure_rules(root)
                    iterations = read_json(rule_path)[
                        "minecraft:feature_rules"
                    ]["distribution"]["iterations"]

                    self.assertEqual(
                        not direct_entry_enabled,
                        result["stagingGuardEnabled"],
                    )
                    if direct_entry_enabled:
                        self.assertEqual(3, iterations)
                    else:
                        self.assertIn(str(STAGING_BLOCK_X), str(iterations))
                        self.assertIn(str(STAGING_BLOCK_Z), str(iterations))
                        self.assertEqual(3, safety.base_iterations(iterations))

    def test_staging_guard_preserves_the_original_iteration_budget(self):
        for original in (
            6,
            "2 + (math.random_integer(0, 9) == 0 ? 1 : 0)",
        ):
            guarded = safety._guarded_iterations(
                original,
                exclude_landmark_envelope=True,
            )
            self.assertEqual(original, safety.base_iterations(guarded))

    def test_surface_ruins_are_rejected_before_entering_a_landmark_envelope(self):
        features, feature_types, dependencies = feature_graph()
        memo = {}

        def reaches_native_structure(identifier, visiting=frozenset()):
            if feature_types.get(identifier) == "netease:structure_feature":
                return True
            if identifier in memo:
                return memo[identifier]
            if identifier in visiting:
                return False
            result = any(
                reaches_native_structure(child, visiting | {identifier})
                for child in dependencies.get(identifier, ())
            )
            memo[identifier] = result
            return result

        unsafe_rules = []
        structure_backed_rule_count = 0
        for path in FEATURE_RULES.glob("*.json"):
            rule = read_json(path)["minecraft:feature_rules"]
            places_feature = rule["description"]["places_feature"]
            if not reaches_native_structure(places_feature):
                continue
            structure_backed_rule_count += 1
            condition_text = json.dumps(
                rule["conditions"]["minecraft:biome_filter"],
                sort_keys=True,
            )
            iterations = str(rule["distribution"]["iterations"])
            identifier = rule["description"]["identifier"]
            placement_pass = rule["conditions"]["placement_pass"]
            if (
                DISABLED_TAG in condition_text
                or str(STAGING_BLOCK_X) in iterations
                or str(STAGING_BLOCK_Z) in iterations
            ):
                unsafe_rules.append(path.name)
                continue
            if (
                placement_pass == "surface_pass"
                and not identifier.startswith(LANDMARK_RULE_PREFIX)
                and (
                    str(LANDMARK_GRID_BLOCKS) not in iterations
                    or str(LANDMARK_ENVELOPE_RADIUS) not in iterations
                    or "math.floor((variable.originx + 128)" not in iterations
                    or "math.floor((variable.originz + 128)" not in iterations
                )
            ):
                unsafe_rules.append(path.name)

        # Direct entry never visits the fixed staging coordinate, so the
        # compiled matrix must not reserve a 1024x1024 structure-free square.
        # Surface-pass small ruins still keep the independent landmark guard.
        # Dark-forest and dark-forest-center trees use bounded native tree
        # features.  They deliberately no longer contribute two cross-chunk
        # structure-backed rules to this safety inventory.
        for identifier in (
            "tf_slice:dark_forest_tree_profile_landmark_surface_project_feature",
            "tf_slice:dark_forest_center_tree_profile_landmark_surface_project_feature",
        ):
            self.assertFalse(reaches_native_structure(identifier))
        self.assertEqual(35, structure_backed_rule_count)
        self.assertEqual([], unsafe_rules)

    def test_structural_environment_runs_after_surface_landmarks(self):
        actual = {}
        for path in FEATURE_RULES.glob("*.json"):
            rule = read_json(path)["minecraft:feature_rules"]
            identifier = rule["description"]["identifier"]
            if identifier in POST_LANDMARK_ENVIRONMENT_RULES:
                actual[identifier] = rule["conditions"]["placement_pass"]

        self.assertEqual(POST_LANDMARK_ENVIRONMENT_RULES, set(actual))
        self.assertEqual(
            {"after_surface_pass"},
            set(actual.values()),
        )


if __name__ == "__main__":
    unittest.main()
