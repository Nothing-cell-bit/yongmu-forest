import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "model_acceptance" / "registry.json"
VALIDATOR_PATH = (
    ROOT
    / ".agents"
    / "skills"
    / "port-entity-models"
    / "scripts"
    / "validate_model_acceptance.py"
)


class EntityBehaviorAcceptanceWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "validate_entity_acceptance", VALIDATOR_PATH
        )
        cls.validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.validator)

    def test_three_beetles_pass_implemented_behavior_gate(self):
        for entity_id in ("fire_beetle", "slime_beetle", "pinch_beetle"):
            errors, unused = self.validator.validate_registry(
                ROOT,
                REGISTRY,
                False,
                entity_id,
                True,
                False,
            )
            self.assertEqual([], errors, entity_id + ": " + "; ".join(errors))

    def test_source_hash_drift_fails_behavior_gate(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        fire = next(
            entity for entity in registry["entities"]
            if entity["id"] == "fire_beetle"
        )
        fire["behavior"]["sources"][0]["sha256"] = "0" * 64
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registry.json"
            path.write_text(json.dumps(registry), encoding="utf-8")
            errors, unused = self.validator.validate_registry(
                ROOT, path, False, "fire_beetle", True, False
            )
        self.assertTrue(
            any("behavior source hash does not match" in error for error in errors),
            errors,
        )

    def test_complete_entity_gate_cannot_confuse_candidate_with_accepted(self):
        errors, unused = self.validator.validate_registry(
            ROOT,
            REGISTRY,
            True,
            "fire_beetle",
            False,
            True,
        )
        self.assertTrue(any("not client_accepted" in error for error in errors))
        self.assertTrue(any("not runtime_verified" in error for error in errors))

    def test_skill_makes_dual_gate_and_non_reviewed_reporting_mandatory(self):
        skill = (
            ROOT / ".agents" / "skills" / "port-entity-models" / "SKILL.md"
        ).read_text(encoding="utf-8")
        self.assertIn("complete-entity", skill)
        self.assertIn("--require-behavior-implemented", skill)
        self.assertIn("--require-complete-entity", skill)
        self.assertIn("behavior: not_reviewed", skill)


if __name__ == "__main__":
    unittest.main()
