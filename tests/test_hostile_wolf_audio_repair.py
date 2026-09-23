import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
ORIGINAL_ROOT = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "sounds"
    / "mob"
    / "mist_wolf"
)
MINECRAFT_ASSETS_ROOT = ROOT / "tools" / "audio_sources" / "hostile_wolf" / "minecraft_1.20.1"
SOURCE_OBJECTS = {
    "minecraft/sounds/mob/wolf/bark1.ogg": "2452c64a55eaef86bf1b668bb4d5f3b641cd8f25",
    "minecraft/sounds/mob/wolf/bark2.ogg": "9f1708a6409d04370ec12d0add015b11abbd5371",
    "minecraft/sounds/mob/wolf/growl1.ogg": "0b29f5ce8c4c10fa4184e5d29244f3bc121468a0",
    "minecraft/sounds/mob/wolf/howl1.ogg": "84556bac99c01ad006552cf5d96494817e9b1700",
    "minecraft/sounds/mob/wolf/howl2.ogg": "cdb0293c5e2bdbda21798af4e61a4c171c8b1ec0",
    "minecraft/sounds/mob/wolf/hurt1.ogg": "71b5fc7aa050892f8c9a9ed2713cc1ad8874742a",
    "minecraft/sounds/mob/wolf/hurt2.ogg": "bc2f6a5a1b6646eac1681b7414b098089aedf3c6",
    "minecraft/sounds/mob/wolf/whine.ogg": "fcf4f90c452b7b511d50e3959ae05036d13a7cf8",
}
CANDIDATE_ROOT = ROOT / "tmp" / "hostile_wolf_audio_research" / "candidates"
GENERATOR = ROOT / "tools" / "generate_hostile_wolf_sounds.py"
WOLF_FILES = (
    "idle1.ogg",
    "idle2.ogg",
    "idle3.ogg",
    "hurt1.ogg",
    "hurt2.ogg",
    "target.ogg",
)


def decode(path: Path) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise unittest.SkipTest("ffmpeg is required for hostile wolf audio tests")
    with tempfile.TemporaryDirectory(prefix="hostile_wolf_audio_test_") as temp_dir:
        wav_path = Path(temp_dir) / "decoded.wav"
        subprocess.run(
            [ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "44100", str(wav_path)],
            check=True,
        )
        with wave.open(str(wav_path), "rb") as wav:
            return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64) / 32768.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_rms(signal: np.ndarray, frame_seconds: float = 0.02) -> np.ndarray:
    frame_size = round(frame_seconds * 44100)
    return np.array([np.sqrt(np.mean(signal[start : start + frame_size] ** 2)) for start in range(0, signal.size - frame_size + 1, frame_size)])


class HostileWolfAudioRepairTests(unittest.TestCase):
    def test_generator_and_reviewed_candidate_bank_exist(self):
        self.assertTrue(GENERATOR.is_file())
        self.assertTrue(CANDIDATE_ROOT.is_dir())
        for filename in WOLF_FILES:
            self.assertTrue((CANDIDATE_ROOT / filename).is_file(), filename)

    def test_event_routes_keep_all_six_hostile_wolf_files(self):
        definitions = json.loads((RP / "sounds" / "sound_definitions.json").read_text(encoding="utf-8"))["sound_definitions"]
        self.assertEqual(
            definitions["tf_slice.hostile_wolf.ambient"]["sounds"],
            ["sounds/mob/hostile_wolf/idle%d" % index for index in range(1, 4)],
        )
        self.assertEqual(
            definitions["tf_slice.hostile_wolf.hurt"]["sounds"],
            ["sounds/mob/hostile_wolf/hurt1", "sounds/mob/hostile_wolf/hurt2"],
        )
        self.assertEqual(
            definitions["tf_slice.hostile_wolf.target"]["sounds"],
            ["sounds/mob/hostile_wolf/target"],
        )
        for filename in WOLF_FILES:
            self.assertTrue((RP / "sounds" / "mob" / "hostile_wolf" / filename).is_file(), filename)

    def test_pinned_minecraft_wolf_sources_are_sha1_locked(self):
        for logical_path, expected_sha1 in SOURCE_OBJECTS.items():
            object_path = MINECRAFT_ASSETS_ROOT / "objects" / expected_sha1[:2] / expected_sha1
            self.assertTrue(object_path.is_file(), logical_path)
            actual_sha1 = hashlib.sha1(object_path.read_bytes()).hexdigest()
            self.assertEqual(actual_sha1, expected_sha1, logical_path)

    def test_candidates_are_not_unmodified_mist_wolf_audio(self):
        for filename in WOLF_FILES:
            self.assertNotEqual(sha256(CANDIDATE_ROOT / filename), sha256(ORIGINAL_ROOT / filename), filename)

    def test_generator_rebuilds_from_minecraft_wolf_sources_without_mist_wolf_root(self):
        with tempfile.TemporaryDirectory(prefix="hostile_wolf_audio_rebuild_") as output_dir:
            result = subprocess.run(
                [
                    __import__("sys").executable,
                    str(GENERATOR),
                    "--minecraft-assets-root",
                    str(MINECRAFT_ASSETS_ROOT),
                    "--output-root",
                    output_dir,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("mist_wolf", result.stderr)
            for filename in WOLF_FILES:
                self.assertEqual((Path(output_dir) / filename).read_bytes(), (CANDIDATE_ROOT / filename).read_bytes(), filename)

    def test_idle_uses_one_complete_vanilla_wolf_call(self):
        for filename in ("idle1.ogg", "idle2.ogg", "idle3.ogg"):
            rms = frame_rms(decode(CANDIDATE_ROOT / filename))
            active = rms > 0.18 * float(rms.max())
            active_runs = np.count_nonzero(active & ~np.r_[False, active[:-1]])
            self.assertGreaterEqual(active_runs, 1, filename)
            self.assertLessEqual(active_runs, 3, filename)

    def test_idle_loudness_has_the_three_db_reduction(self):
        for filename in ("idle1.ogg", "idle2.ogg", "idle3.ogg"):
            self.assertLessEqual(float(np.max(np.abs(decode(CANDIDATE_ROOT / filename)))), 0.45, filename)

    def test_outputs_are_short_clean_and_role_shaped(self):
        limits = {
            "idle": (2.5, 4.5),
            "hurt": (0.45, 1.0),
            "target": (2.5, 4.5),
        }
        for filename in WOLF_FILES:
            role = "idle" if filename.startswith("idle") else "hurt" if filename.startswith("hurt") else "target"
            signal = decode(CANDIDATE_ROOT / filename)
            duration = signal.size / 44100.0
            self.assertGreaterEqual(duration, limits[role][0], filename)
            self.assertLessEqual(duration, limits[role][1], filename)
            self.assertGreater(float(np.max(np.abs(signal))), 0.05, filename)
            self.assertLessEqual(float(np.max(np.abs(signal))), 0.95, filename)
