# -*- coding: utf-8 -*-
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / ".agents" / "skills" / "port-boss-entities"
SCRIPT = SKILL_ROOT / "scripts" / "validate_boss_evidence.py"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class BossEntitySkillTests(unittest.TestCase):
    def make_fixture(self, runtime_verified=False):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)

        files = {
            "upstream.jar": b"locked upstream boss jar",
            "sources/Lich.java": b"class Lich {}",
            "sources/ModelLich.java": b"class ModelLich {}",
            "sources/RenderLich.java": b"class RenderLich {}",
            "source/lich.png": b"source lich texture",
            "rp/textures/entity/lich.png": b"source lich texture",
            "bp/entities/lich.json": b"{}",
            "bp/scripts/lich_runtime.py": b"STATE = 'phase_one'",
            "rp/entity/lich.entity.json": b"{}",
            "evidence/lich_phase_two.png": b"runtime screenshot",
        }
        for relative, data in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        visual_status = "client_accepted" if runtime_verified else "candidate"
        behavior_status = "runtime_verified" if runtime_verified else "implemented"
        evidence = {
            "boss": "twilightforest:lich",
            "status": "runtime_verified" if runtime_verified else "implemented",
            "source": {
                "jar_path": "upstream.jar",
                "jar_sha256": sha256(root / "upstream.jar"),
                "classes": [
                    {
                        "role": "entity",
                        "class": "Lich",
                        "path": "sources/Lich.java",
                        "sha256": sha256(root / "sources/Lich.java"),
                    },
                    {
                        "role": "model",
                        "class": "ModelLich",
                        "path": "sources/ModelLich.java",
                        "sha256": sha256(root / "sources/ModelLich.java"),
                    },
                    {
                        "role": "renderer",
                        "class": "RenderLich",
                        "path": "sources/RenderLich.java",
                        "sha256": sha256(root / "sources/RenderLich.java"),
                    },
                ],
                "textures": [
                    {
                        "source": "source/lich.png",
                        "target": "rp/textures/entity/lich.png",
                        "sha256": sha256(root / "source/lich.png"),
                    }
                ],
            },
            "tracks": {
                "model": {
                    "status": visual_status,
                    "tests": ["geometry loads and pivots match"],
                    "production_hashes": [
                        {
                            "path": "rp/entity/lich.entity.json",
                            "sha256": sha256(root / "rp/entity/lich.entity.json"),
                        }
                    ],
                },
                "ai": {
                    "status": behavior_status,
                    "tests": ["phase and goal priority contract"],
                    "production_hashes": [
                        {
                            "path": "bp/scripts/lich_runtime.py",
                            "sha256": sha256(root / "bp/scripts/lich_runtime.py"),
                        }
                    ],
                },
                "interactions": {
                    "status": behavior_status,
                    "tests": ["shield and health damage are distinct"],
                    "production_hashes": [
                        {
                            "path": "bp/entities/lich.json",
                            "sha256": sha256(root / "bp/entities/lich.json"),
                        }
                    ],
                },
                "assets": {
                    "status": visual_status,
                    "tests": ["texture and particle references resolve"],
                    "production_hashes": [
                        {
                            "path": "rp/textures/entity/lich.png",
                            "sha256": sha256(root / "rp/textures/entity/lich.png"),
                        }
                    ],
                },
                "items_rewards": {
                    "status": behavior_status,
                    "tests": ["loot is granted once"],
                    "production_hashes": [
                        {
                            "path": "bp/entities/lich.json",
                            "sha256": sha256(root / "bp/entities/lich.json"),
                        }
                    ],
                },
                "integration": {
                    "status": behavior_status,
                    "tests": ["server authority and restart"],
                    "production_hashes": [
                        {
                            "path": "bp/scripts/lich_runtime.py",
                            "sha256": sha256(root / "bp/scripts/lich_runtime.py"),
                        }
                    ],
                },
            },
            "contracts": {
                "phases": [{"id": "shielded", "entry": "spawn", "exit": "shields == 0"}],
                "goals": [{"priority": 1, "name": "ranged_attack", "interrupt": "higher priority"}],
                "damage": [{"input": "projectile", "result": "shield contact"}],
                "interactions": [{"trigger": "player hit", "result": "phase-aware response"}],
                "presentation_assets": [{"asset": "lich texture", "result": "resolved"}],
                "items_rewards": [{"item": "scepter", "role": "held gear and loot"}],
                "death_rewards": [{"trigger": "death sequence end", "result": "atomic reward"}],
                "persistence_multiplayer": [{"case": "restart", "result": "state restored"}],
            },
            "runtime": {
                "cold_restart": runtime_verified,
                "client_build": "1.21.0.03" if runtime_verified else "",
                "pack_version": [1, 0, 0] if runtime_verified else [],
                "reviewer": "fixture" if runtime_verified else "",
                "captured_at": "2026-08-05T18:45:00+08:00" if runtime_verified else "",
                "scenarios": [
                    {
                        "id": "phase_two",
                        "setup": "cold client restart and summon boss",
                        "timeline": "break shields and observe transition",
                        "expected": "phase two begins once",
                        "evidence": ["evidence/lich_phase_two.png"],
                    }
                ] if runtime_verified else [],
            },
        }
        evidence_path = root / "boss_acceptance" / "lich.json"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return temporary, root, evidence_path, evidence

    def run_validator(self, root, evidence_path, *extra):
        self.assertTrue(SCRIPT.is_file(), "boss skill must ship an evidence validator")
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(evidence_path), "--root", str(root), *extra],
            capture_output=True,
            text=True,
        )

    def test_skill_routes_all_six_boss_tracks_and_supporting_references(self):
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
        for term in (
            "建模与动画",
            "AI、战斗与状态机",
            "互动、世界与进度",
            "材质与演出资源",
            "相关物品与奖励",
            "集成与实机验收",
            "--require-runtime-verified",
        ):
            self.assertIn(term, skill)
        for relative in (
            "references/boss-contract.md",
            "references/boss-test-matrix.md",
            "references/boss-evidence-template.json",
        ):
            self.assertTrue((SKILL_ROOT / relative).is_file(), relative)

    def test_implemented_fixture_passes_hash_and_track_gate(self):
        temporary, root, evidence_path, unused = self.make_fixture(False)
        self.addCleanup(temporary.cleanup)
        result = self.run_validator(root, evidence_path, "--require-implemented")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("implemented gate: PASS", result.stdout)

    def test_production_hash_drift_is_rejected(self):
        temporary, root, evidence_path, unused = self.make_fixture(False)
        self.addCleanup(temporary.cleanup)
        (root / "bp/scripts/lich_runtime.py").write_bytes(b"drifted")
        result = self.run_validator(root, evidence_path, "--require-implemented")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("production hash does not match", result.stdout + result.stderr)

    def test_runtime_gate_requires_cold_client_evidence(self):
        temporary, root, evidence_path, unused = self.make_fixture(False)
        self.addCleanup(temporary.cleanup)
        result = self.run_validator(root, evidence_path, "--require-runtime-verified")
        self.assertNotEqual(0, result.returncode)
        self.assertIn("cold_restart must be true", result.stdout + result.stderr)

    def test_runtime_verified_fixture_passes_strict_gate(self):
        temporary, root, evidence_path, unused = self.make_fixture(True)
        self.addCleanup(temporary.cleanup)
        result = self.run_validator(root, evidence_path, "--require-runtime-verified")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("runtime_verified gate: PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
