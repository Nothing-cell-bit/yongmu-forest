# -*- coding: utf-8 -*-
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import build_phantom_urghast_models
import build_hydra_route_models


def assert_supported_golem_attack_state(test_case, animations):
    bones = animations["animation.tf_slice.carminite_golem.move"]["bones"]
    for arm_name in ("right_arm", "left_arm"):
        expression = bones[arm_name]["rotation"][0]
        test_case.assertNotIn("query.is_swinging", expression, arm_name)
        test_case.assertIn("variable.attack_time", expression, arm_name)


class MolangRuntimeCompatibilityTests(unittest.TestCase):
    def test_built_animation_uses_supported_attack_animation_state(self):
        document = json.loads(
            (
                RP
                / "animations"
                / "phantom_urghast_route.animation.json"
            ).read_text(encoding="utf-8")
        )
        assert_supported_golem_attack_state(self, document["animations"])

    def test_generator_preserves_supported_attack_animation_state(self):
        assert_supported_golem_attack_state(
            self,
            build_phantom_urghast_models.build_animations()["animations"],
        )

    def test_hydra_head_complex_script_statements_are_terminated(self):
        generated = build_hydra_route_models.client_entity(
            "hydra_head", "hydra4.png"
        )["minecraft:client_entity"]["description"]["scripts"]
        built = json.loads(
            (RP / "entity" / "hydra_head.entity.json").read_text(
                encoding="utf-8"
            )
        )["minecraft:client_entity"]["description"]["scripts"]

        for source in (generated, built):
            for section in ("initialize", "pre_animation"):
                for expression in source[section]:
                    self.assertTrue(
                        expression.rstrip().endswith(";"),
                        "%s expression must end with a semicolon: %s"
                        % (section, expression),
                    )


if __name__ == "__main__":
    unittest.main()
