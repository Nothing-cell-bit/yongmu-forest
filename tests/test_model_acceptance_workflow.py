# -*- coding: utf-8 -*-
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / ".agents"
    / "skills"
    / "port-entity-models"
    / "scripts"
    / "validate_model_acceptance.py"
)
REGISTRY = ROOT / "model_acceptance" / "registry.json"


def sha256(data):
    return hashlib.sha256(data).hexdigest().upper()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def write_png(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (64, 64), (90, 70, 140, 255)).save(path)


class ModelAcceptanceWorkflowTests(unittest.TestCase):
    def run_validator(self, repo_root, registry, *extra):
        self.assertTrue(
            SCRIPT.is_file(),
            "the project skill must ship its acceptance validator",
        )
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--repo-root",
                str(repo_root),
                "--registry",
                str(registry),
            ]
            + list(extra),
            capture_output=True,
            text=True,
        )

    def make_fixture(self, accepted):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        jar_bytes = b"locked upstream jar"
        texture_bytes = b"source texture"
        geometry = {
            "minecraft:geometry": [
                {
                    "description": {
                        "identifier": "geometry.test.example",
                    },
                    "bones": [],
                }
            ]
        }
        client = {
            "minecraft:client_entity": {
                "description": {
                    "identifier": "test:example",
                    "geometry": {
                        "default": "geometry.test.example",
                    },
                    "textures": {
                        "default": "textures/entity/example",
                    },
                }
            }
        }

        (root / "upstream.jar").write_bytes(jar_bytes)
        (root / "source.png").write_bytes(texture_bytes)
        target_texture = root / "rp" / "textures" / "entity" / "example.png"
        target_texture.parent.mkdir(parents=True, exist_ok=True)
        target_texture.write_bytes(texture_bytes)
        write_json(root / "rp" / "example.geo.json", geometry)
        write_json(root / "rp" / "example.entity.json", client)

        registry = {
            "schema_version": 1,
            "upstream": {
                "version": "test",
                "jar": "upstream.jar",
                "sha256": sha256(jar_bytes),
            },
            "required_client_views": [
                "front",
                "back",
                "left",
                "right",
                "top",
                "three_quarter",
            ],
            "required_client_poses": [
                "rest",
                "walk_extreme",
                "look_up",
                "look_down",
            ],
            "entities": [
                {
                    "id": "example",
                    "status": (
                        "client_accepted" if accepted else "candidate"
                    ),
                    "source": {
                        "model_class": "example.Model",
                        "textures": [
                            {
                                "source": "source.png",
                                "target": (
                                    "rp/textures/entity/example.png"
                                ),
                                "sha256": sha256(texture_bytes),
                            }
                        ],
                    },
                    "bedrock": {
                        "geometry": "rp/example.geo.json",
                        "identifier": "geometry.test.example",
                        "client_entity": "rp/example.entity.json",
                    },
                    "offline_evidence": "offline/example.json",
                    "evidence": "evidence/example.json",
                }
            ],
        }
        registry_path = root / "registry.json"
        write_json(registry_path, registry)
        return temporary, root, registry_path

    def write_focused_test(self, root, failing=False):
        test_path = root / "tests" / "test_example_model.py"
        test_path.parent.mkdir(parents=True, exist_ok=True)
        test_path.write_text(
            "import unittest\n\n"
            "class ExampleModelTests(unittest.TestCase):\n"
            "    def test_model_contract(self):\n"
            "        self.assert%s(True)\n"
            % ("False" if failing else "True"),
            encoding="utf-8",
        )
        return {
            "path": "tests/test_example_model.py",
            "sha256": sha256(test_path.read_bytes()),
        }

    def write_complete_evidence(self, root):
        geometry_path = root / "rp" / "example.geo.json"
        texture_path = root / "rp" / "textures" / "entity" / "example.png"
        views = {}
        for name in (
            "front",
            "back",
            "left",
            "right",
            "top",
            "three_quarter",
        ):
            path = root / "evidence" / "images" / ("%s.png" % name)
            write_png(path)
            views[name] = str(path.relative_to(root)).replace("\\", "/")
        poses = {}
        for name in ("rest", "walk_extreme", "look_up", "look_down"):
            path = root / "evidence" / "images" / ("%s.png" % name)
            if not path.exists():
                write_png(path)
            poses[name] = str(path.relative_to(root)).replace("\\", "/")

        write_json(
            root / "evidence" / "example.json",
            {
                "entity": "example",
                "status": "client_accepted",
                "source_jar_sha256": sha256(
                    (root / "upstream.jar").read_bytes()
                ),
                "geometry_sha256": sha256(geometry_path.read_bytes()),
                "texture_sha256": {
                    "rp/textures/entity/example.png": sha256(
                        texture_path.read_bytes()
                    )
                },
                "automated": {
                    "tests_passed": True,
                    "validator_passed": True,
                    "focused_tests": [self.write_focused_test(root)],
                },
                "client": {
                    "cold_restart": True,
                    "client_build": "test-client",
                    "pack_version": [1, 0, 0],
                    "captured_at": "2026-07-29T12:00:00+08:00",
                    "reviewer": "tester",
                    "views": views,
                    "poses": poses,
                },
            },
        )

    def write_complete_offline_evidence(self, root):
        geometry_path = root / "rp" / "example.geo.json"
        texture_path = root / "rp" / "textures" / "entity" / "example.png"
        views = {}
        for name in (
            "front",
            "back",
            "left",
            "right",
            "top",
            "three_quarter",
        ):
            path = root / "offline" / "images" / ("%s.png" % name)
            write_png(path)
            views[name] = str(path.relative_to(root)).replace("\\", "/")
        poses = {}
        for name in ("rest", "walk_extreme", "look_up", "look_down"):
            path = root / "offline" / "images" / ("%s.png" % name)
            if not path.exists():
                write_png(path)
            poses[name] = str(path.relative_to(root)).replace("\\", "/")

        write_json(
            root / "offline" / "example.json",
            {
                "entity": "example",
                "status": "candidate",
                "source_jar_sha256": sha256(
                    (root / "upstream.jar").read_bytes()
                ),
                "geometry_sha256": sha256(geometry_path.read_bytes()),
                "texture_sha256": {
                    "rp/textures/entity/example.png": sha256(
                        texture_path.read_bytes()
                    )
                },
                "automated": {
                    "source_lock_passed": True,
                    "focused_tests_passed": True,
                    "focused_tests": [self.write_focused_test(root)],
                },
                "generated_at": "2026-07-29T12:00:00+08:00",
                "renderer": "independent-test-renderer",
                "offline": {
                    "views": views,
                    "poses": poses,
                },
            },
        )

    def test_repository_registry_tracks_all_reported_models_without_false_acceptance(
        self,
    ):
        result = self.run_validator(ROOT, REGISTRY)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        entities = dict(
            (entry["id"], entry["status"])
            for entry in registry["entities"]
        )
        self.assertEqual(
            {
                "quest_ram",
                "tiny_bird",
                "squirrel",
                "dwarf_rabbit",
                "redcap",
                "redcap_sapper",
                "fire_beetle",
                "slime_beetle",
                "pinch_beetle",
                "penguin",
                "lich",
                "death_tome",
                "lich_minion",
                "loyal_zombie",
                "forest_wyrm",
                "minotaur",
                "minoshroom",
                "maze_slime",
                "mosquito_swarm",
                "hydra",
                "hydra_head",
                "hydra_neck",
                "hydra_mortar",
                "block_chain_goblin",
                "lower_goblin_knight",
                "upper_goblin_knight",
                "helmet_crab",
                "knight_phantom",
                "knight_axe_projectile",
                "knight_pickaxe_projectile",
                "block_chain_projectile",
                "carminite_golem",
                "tower_broodling",
                "mini_ghast",
                "tower_ghast",
                "towerwood_borer",
                "ur_ghast",
            },
            set(entities),
        )
        self.assertNotIn("client_accepted", entities.values())
        for identifier in (
            "block_chain_goblin",
            "lower_goblin_knight",
            "upper_goblin_knight",
            "helmet_crab",
            "carminite_golem",
            "towerwood_borer",
        ):
            self.assertEqual("candidate", entities[identifier])
        for identifier in (
            "knight_phantom",
            "tower_broodling",
            "mini_ghast",
            "tower_ghast",
            "ur_ghast",
        ):
            self.assertEqual("rejected", entities[identifier])
        for identifier in (
            "knight_axe_projectile",
            "knight_pickaxe_projectile",
            "block_chain_projectile",
        ):
            self.assertEqual("converted", entities[identifier])

    def test_rejected_ur_ghast_behavior_survives_evidence_rebuild(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        entries = {entry["id"]: entry for entry in registry["entities"]}
        self.assertEqual(
            "rejected", entries["ur_ghast"]["behavior"]["status"]
        )
        behavior = json.loads(
            (
                ROOT
                / "model_acceptance"
                / "behavior"
                / "ur_ghast.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual("rejected", behavior["status"])

    def test_reported_tower_broodling_failure_stays_rejected_on_native_geometry(self):
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        entries = {entry["id"]: entry for entry in registry["entities"]}
        broodling = entries["tower_broodling"]

        self.assertEqual("rejected", broodling["status"])
        self.assertEqual(
            "geometry.spider.v1.8", broodling["bedrock"]["identifier"]
        )
        self.assertTrue(broodling["bedrock"]["builtin_geometry"])
        self.assertNotIn("geometry", broodling["bedrock"])

    def test_client_accepted_status_rejects_missing_client_evidence(self):
        temporary, root, registry = self.make_fixture(accepted=True)
        self.addCleanup(temporary.cleanup)

        result = self.run_validator(root, registry)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("missing evidence file", result.stdout)

    def test_complete_actual_client_evidence_passes_the_strict_gate(self):
        temporary, root, registry = self.make_fixture(accepted=True)
        self.addCleanup(temporary.cleanup)
        self.write_complete_evidence(root)

        result = self.run_validator(
            root,
            registry,
            "--require-client-accepted",
        )

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("CLIENT_ACCEPTED: example", result.stdout)

    def test_truncated_png_cannot_masquerade_as_client_evidence(self):
        temporary, root, registry = self.make_fixture(accepted=True)
        self.addCleanup(temporary.cleanup)
        self.write_complete_evidence(root)
        (root / "evidence" / "images" / "front.png").write_bytes(
            b"\x89PNG\r\n\x1a\n"
        )

        result = self.run_validator(
            root,
            registry,
            "--require-client-accepted",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("is not a decodable PNG", result.stdout)

    def test_candidate_cannot_pass_the_strict_client_gate(self):
        temporary, root, registry = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)

        result = self.run_validator(
            root,
            registry,
            "--require-client-accepted",
        )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("status is candidate", result.stdout)

    def test_candidate_without_offline_evidence_fails_default_gate(self):
        temporary, root, registry = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)

        result = self.run_validator(root, registry)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("missing offline evidence file", result.stdout)

    def test_rejected_entity_can_bind_an_explicit_builtin_geometry(self):
        temporary, root, registry_path = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        entity = registry["entities"][0]
        entity["status"] = "rejected"
        entity["bedrock"].pop("geometry")
        entity["bedrock"]["identifier"] = "geometry.spider.v1.8"
        entity["bedrock"]["builtin_geometry"] = True
        write_json(registry_path, registry)

        client_path = root / "rp" / "example.entity.json"
        client = json.loads(client_path.read_text(encoding="utf-8"))
        client["minecraft:client_entity"]["description"]["geometry"][
            "default"
        ] = "geometry.spider.v1.8"
        write_json(client_path, client)

        result = self.run_validator(root, registry_path)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_complete_offline_evidence_passes_candidate_gate(self):
        temporary, root, registry = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)

        result = self.run_validator(root, registry)

        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("STATUS: example (candidate)", result.stdout)

    def test_candidate_rejects_declared_animation_hash_drift(self):
        temporary, root, registry_path = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)

        animation_path = root / "rp" / "example.animation.json"
        write_json(animation_path, {"animations": {"walk": {}}})
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["entities"][0]["bedrock"]["animation"] = (
            "rp/example.animation.json"
        )
        write_json(registry_path, registry)

        evidence_path = root / "offline" / "example.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["animation_sha256"] = sha256(animation_path.read_bytes())
        write_json(evidence_path, evidence)
        write_json(animation_path, {"animations": {"walk": {"broken": True}}})

        result = self.run_validator(root, registry_path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("offline animation hash does not match", result.stdout)

    def test_declared_attachment_cannot_be_omitted_from_offline_evidence(self):
        temporary, root, registry_path = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["entities"][0]["required_attachments"] = ["mainhand"]
        write_json(registry_path, registry)

        result = self.run_validator(root, registry_path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("offline attachments missing mainhand", result.stdout)

    def test_candidate_rejects_missing_attachment_contract(self):
        temporary, root, registry_path = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)
        attachment_path = root / "offline" / "images" / "mainhand.png"
        write_png(attachment_path)

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["entities"][0]["required_attachments"] = ["mainhand"]
        write_json(registry_path, registry)
        evidence_path = root / "offline" / "example.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["offline"]["attachments"] = {
            "mainhand": "offline/images/mainhand.png"
        }
        write_json(evidence_path, evidence)

        result = self.run_validator(root, registry_path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("attachment contract missing mainhand", result.stdout)

    def test_candidate_rejects_failed_attachment_semantic_check(self):
        temporary, root, registry_path = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)
        attachment_path = root / "offline" / "images" / "mainhand.png"
        item_texture_path = root / "rp" / "textures" / "items" / "axe.png"
        write_png(attachment_path)
        write_png(item_texture_path)

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["entities"][0]["required_attachments"] = ["mainhand"]
        write_json(registry_path, registry)
        evidence_path = root / "offline" / "example.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["offline"]["attachments"] = {
            "mainhand": "offline/images/mainhand.png"
        }
        evidence["attachment_contracts"] = {
            "mainhand": {
                "bone": "rightItem",
                "texture_path": "rp/textures/items/axe.png",
                "texture_sha256": sha256(item_texture_path.read_bytes()),
                "focused_tests": ["tests/test_example_model.py"],
                "checks": {
                    "equipment_source": True,
                    "grip_contacts_hand": True,
                    "tool_head_clear_of_hand": True,
                    "front_depth_visible": True,
                    "orientation_reviewed": False,
                },
            }
        }
        write_json(evidence_path, evidence)

        result = self.run_validator(root, registry_path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn(
            "attachment mainhand failed orientation_reviewed",
            result.stdout,
        )

    def test_candidate_rejects_missing_required_animation_check(self):
        temporary, root, registry_path = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)
        animation_path = root / "rp" / "example.animation.json"
        write_json(animation_path, {"animations": {"walk": {}}})

        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        entity = registry["entities"][0]
        entity["bedrock"]["animation"] = "rp/example.animation.json"
        entity["required_animation_checks"] = [
            "phase_amplitude_roles",
            "bounded_long_horizon",
            "source_extreme_preview",
        ]
        write_json(registry_path, registry)
        evidence_path = root / "offline" / "example.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["animation_sha256"] = sha256(animation_path.read_bytes())
        evidence["animation_contract"] = {
            "focused_test": "tests/test_example_model.py",
            "checks": {
                "phase_amplitude_roles": True,
                "bounded_long_horizon": True,
            },
        }
        write_json(evidence_path, evidence)

        result = self.run_validator(root, registry_path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn(
            "animation contract failed source_extreme_preview",
            result.stdout,
        )

    def test_candidate_does_not_trust_focused_test_boolean_alone(self):
        temporary, root, registry = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)
        evidence_path = root / "offline" / "example.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        del evidence["automated"]["focused_tests"]
        write_json(evidence_path, evidence)

        result = self.run_validator(root, registry)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("focused test records are missing", result.stdout)

    def test_candidate_rejects_focused_test_hash_drift(self):
        temporary, root, registry = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)
        test_path = root / "tests" / "test_example_model.py"
        test_path.write_text("# silently changed\n", encoding="utf-8")

        result = self.run_validator(root, registry)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("focused test hash does not match", result.stdout)

    def test_candidate_rejects_recorded_generator_hash_drift(self):
        temporary, root, registry = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)
        evidence_path = root / "offline" / "example.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["automated"]["generator"] = {
            "path": "tests/test_example_model.py",
            "sha256": "0" * 64,
            "check_args": [],
        }
        write_json(evidence_path, evidence)

        result = self.run_validator(root, registry)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("generator hash does not match", result.stdout)

    def test_locked_model_class_hash_is_verified_inside_upstream_jar(self):
        temporary, root, registry_path = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        class_bytes = b"locked model bytecode"
        with zipfile.ZipFile(root / "upstream.jar", "w") as archive:
            archive.writestr("example/Model.class", class_bytes)
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        registry["upstream"]["sha256"] = sha256(
            (root / "upstream.jar").read_bytes()
        )
        source = registry["entities"][0]["source"]
        source["model_class"] = "example.Model"
        source["model_class_sha256"] = "0" * 64
        write_json(registry_path, registry)
        self.write_complete_offline_evidence(root)

        result = self.run_validator(root, registry_path)

        self.assertNotEqual(0, result.returncode)
        self.assertIn("source model class hash does not match", result.stdout)

    def test_release_gate_executes_locked_focused_tests(self):
        temporary, root, registry = self.make_fixture(accepted=False)
        self.addCleanup(temporary.cleanup)
        self.write_complete_offline_evidence(root)
        evidence_path = root / "offline" / "example.json"
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["automated"]["focused_tests"] = [
            self.write_focused_test(root, failing=True)
        ]
        write_json(evidence_path, evidence)

        result = self.run_validator(root, registry, "--run-focused-tests")

        self.assertNotEqual(0, result.returncode)
        self.assertIn("focused tests failed", result.stdout)

    def test_formal_packager_runs_the_model_acceptance_registry_gate(self):
        validator_source = (
            ROOT / "tools" / "validate_slice.py"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "def validate_model_acceptance_registry(",
            validator_source,
        )
        self.assertIn(
            "require_client_accepted=True,\n"
            "            run_focused_tests=True,",
            validator_source,
        )
        from tools import validate_slice

        gate = validate_slice.Gate()
        validate_slice.validate_model_acceptance_registry(gate)
        self.assertGreater(gate.checks, 0)
        self.assertEqual([], gate.failures)

    def test_development_sync_uses_candidate_gate_without_packaging_release(self):
        sync_source = (ROOT / "tools" / "sync_packs.py").read_text(
            encoding="utf-8"
        )
        self.assertIn('"--allow-model-candidates"', sync_source)
        self.assertIn('"--no-package"', sync_source)


if __name__ == "__main__":
    unittest.main()
