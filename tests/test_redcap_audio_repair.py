import hashlib
import importlib.util
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
    / "redcap"
)
LAUGH_SOURCES = (
    ROOT / "tools" / "audio_sources" / "redcap" / "cc0_laughter" / "sinister_laugh.ogg",
    ROOT / "tools" / "audio_sources" / "redcap" / "cc0_laughter" / "evil_cackle_laugh_2.ogg",
    ROOT / "tools" / "audio_sources" / "redcap" / "cc0_laughter" / "evil_laugh_2.ogg",
    ROOT / "tools" / "audio_sources" / "redcap" / "cc0_laughter" / "witch_cackle.ogg",
    ROOT / "tools" / "audio_sources" / "redcap" / "cc0_laughter" / "evil_laughter_0.ogg",
)
LAUGH_SOURCE_SHA256 = (
    "8de8e205e6ce8542609d709718a46a94388d859bef337ee0af3abdf02eb87454",
    "215caebb11ca96d22eea36a68e16ffcfa7479c835e3927a21fe90a7880c8bc9c",
    "41e69ed7eb6e0b82746429b1abbb74c16f2ff2b9aa02a3a700c3ada4563b559e",
    "6698c4f70facd5e9b4285ff34897099f70c95a826c6775ba4fba7ef5afbc4caf",
    "9dcf890d2ed763e71013fcca6dd885bde98cf7caac6e901bffbc531f459e0e9e",
)
MINECRAFT_REPLACEMENT_ROOT = ROOT / "tools" / "audio_sources" / "redcap" / "minecraft_1.20.1"
MINECRAFT_REPLACEMENT_OBJECTS = {
    "minecraft/sounds/entity/witch/hurt1.ogg": "d4f9f7adb9789781a3a0ca1a94262a474cbee1db",
    "minecraft/sounds/entity/witch/hurt2.ogg": "608ce4dc409ef39df6b0409647b89f2f1a2d9ded",
    "minecraft/sounds/entity/witch/hurt3.ogg": "591bb8451ac56723d2b689d9bc95c8020bb4809b",
    "minecraft/sounds/entity/witch/death1.ogg": "627c939e2aa48a5e3f516848e66a76acb992c2a8",
    "minecraft/sounds/entity/witch/death2.ogg": "b5e67bcc0f5af24fa6d01f377215143ee7a1cf67",
    "minecraft/sounds/entity/witch/death3.ogg": "4c02a13757318403e7837260c1b30069dcb7be69",
    "minecraft/sounds/mob/pillager/hurt1.ogg": "3f2e8691d05ab35ba956159e76ad89b267bb9a9f",
    "minecraft/sounds/mob/pillager/hurt2.ogg": "977e87e9f30b5b4b35d7a8fc7355a1d891f7c2c8",
    "minecraft/sounds/mob/pillager/hurt3.ogg": "dcfac8650527f90c0ea202504497436b716ae37a",
    "minecraft/sounds/mob/pillager/death1.ogg": "12365c224970df985cce386bbcaeb357b4b85496",
    "minecraft/sounds/mob/pillager/death2.ogg": "b440f29191234eb91f36354bbf43d62dcba0973e",
}
CANDIDATE_ROOT = ROOT / "tmp" / "redcap_audio_research" / "candidates"
GENERATOR = ROOT / "tools" / "generate_redcap_sounds.py"
REDCAP_FILES = (
    "redcap1.ogg",
    "redcap2.ogg",
    "redcap3.ogg",
    "redcap4.ogg",
    "redcap5.ogg",
    "redcap6.ogg",
    "redcap7.ogg",
    "hurt1.ogg",
    "hurt2.ogg",
    "hurt3.ogg",
    "hurt4.ogg",
    "die1.ogg",
    "die2.ogg",
    "die3.ogg",
)


def decode(path: Path) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise unittest.SkipTest("ffmpeg is required for Redcap audio tests")
    with tempfile.TemporaryDirectory(prefix="redcap_audio_test_") as temp_dir:
        wav_path = Path(temp_dir) / "decoded.wav"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "44100", str(wav_path)], check=True)
        with wave.open(str(wav_path), "rb") as wav:
            return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64) / 32768.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RedcapAudioRepairTests(unittest.TestCase):
    def test_generator_and_reviewed_candidate_bank_exist(self):
        self.assertTrue(GENERATOR.is_file())
        self.assertTrue(CANDIDATE_ROOT.is_dir())
        for filename in REDCAP_FILES:
            self.assertTrue((CANDIDATE_ROOT / filename).is_file(), filename)

    def test_event_routes_keep_all_redcap_audio_paths(self):
        definitions = json.loads((RP / "sounds" / "sound_definitions.json").read_text(encoding="utf-8"))["sound_definitions"]
        ambient = definitions["tf_slice.redcap.ambient"]["sounds"]
        self.assertEqual([entry["name"] for entry in ambient], ["sounds/mob/redcap/redcap%d" % index for index in range(1, 8)])
        self.assertEqual([entry["weight"] for entry in ambient], [100, 100, 100, 100, 100, 100, 1])
        self.assertEqual(definitions["tf_slice.redcap.hurt"]["sounds"], ["sounds/mob/redcap/hurt%d" % index for index in range(1, 5)])
        self.assertEqual(definitions["tf_slice.redcap.death"]["sounds"], ["sounds/mob/redcap/die%d" % index for index in range(1, 4)])
        for filename in REDCAP_FILES:
            self.assertTrue((RP / "sounds" / "mob" / "redcap" / filename).is_file(), filename)

    def test_pinned_cc0_laugh_sources_are_hash_locked(self):
        for path, expected_hash in zip(LAUGH_SOURCES, LAUGH_SOURCE_SHA256):
            self.assertTrue(path.is_file(), path)
            self.assertEqual(sha256(path), expected_hash, path.name)

    def test_pinned_minecraft_hurt_death_sources_are_sha1_locked(self):
        for logical_path, expected_sha1 in MINECRAFT_REPLACEMENT_OBJECTS.items():
            object_path = MINECRAFT_REPLACEMENT_ROOT / "objects" / expected_sha1[:2] / expected_sha1
            self.assertTrue(object_path.is_file(), logical_path)
            self.assertEqual(hashlib.sha1(object_path.read_bytes()).hexdigest(), expected_sha1, logical_path)

    def test_laughter_candidate_keeps_the_source_contour(self):
        spec = importlib.util.spec_from_file_location("redcap_generator", GENERATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        source = decode(LAUGH_SOURCES[0])
        candidate = decode(CANDIDATE_ROOT / "redcap1.ogg")
        source = module.trim_active(source)
        source_fit = np.interp(
            np.linspace(0.0, source.size - 1.0, candidate.size),
            np.arange(source.size),
            source,
        )
        correlation = float(np.corrcoef(source_fit, candidate)[0, 1])
        self.assertGreater(correlation, 0.15)

    def test_six_laughter_candidates_are_not_near_duplicates(self):
        signals = []
        for index in range(1, 7):
            signal = decode(CANDIDATE_ROOT / ("redcap%d.ogg" % index))
            signals.append(
                np.interp(
                    np.linspace(0.0, signal.size - 1.0, 20_000),
                    np.arange(signal.size),
                    signal,
                )
            )
        correlations = []
        for first in range(len(signals)):
            for second in range(first + 1, len(signals)):
                correlations.append(float(np.corrcoef(signals[first], signals[second])[0, 1]))
        self.assertLess(max(correlations), 0.90)

    def test_redcap6_and_redcap7_are_procedural(self):
        spec = importlib.util.spec_from_file_location("redcap_generator", GENERATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for filename, duration, seed, variant in (
            ("redcap6.ogg", 1.300317, 20_261_415, 5),
            ("redcap7.ogg", 1.750000, 20_261_511, 7),
        ):
            expected = module.build_procedural_laugh(duration, seed, variant)
            self.assertEqual(expected.size, round(duration * module.SAMPLE_RATE))
            self.assertGreater(float(np.max(np.abs(expected))), 0.05, filename)

    def test_candidates_are_not_unmodified_twilight_redcap_audio(self):
        for filename in REDCAP_FILES:
            if filename == "redcap7.ogg":
                continue
            self.assertNotEqual(sha256(CANDIDATE_ROOT / filename), sha256(ORIGINAL_ROOT / filename), filename)

    def test_procedural_laughter_builds_without_redcap_audio_input(self):
        spec = importlib.util.spec_from_file_location("redcap_generator", GENERATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        for variant in range(6):
            signal = module.build_procedural_laugh(1.2, 20_260_906 + variant, variant)
            self.assertEqual(signal.size, round(1.2 * module.SAMPLE_RATE))
            self.assertGreater(float(np.max(np.abs(signal))), 0.05, variant)

    def test_generator_rebuilds_from_locked_redcap_sources(self):
        with tempfile.TemporaryDirectory(prefix="redcap_audio_rebuild_") as output_dir:
            command = [__import__("sys").executable, str(GENERATOR), "--minecraft-assets-root", str(MINECRAFT_REPLACEMENT_ROOT)]
            for source_path in LAUGH_SOURCES:
                command.extend(["--laugh-source", str(source_path)])
            command.extend(["--output-root", output_dir])
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for filename in REDCAP_FILES:
                self.assertEqual((Path(output_dir) / filename).read_bytes(), (CANDIDATE_ROOT / filename).read_bytes(), filename)

    def test_outputs_are_short_clean_and_role_shaped(self):
        limits = {"ambient": (0.65, 2.2), "hurt": (0.35, 1.35), "death": (0.65, 2.3)}
        for filename in REDCAP_FILES:
            role = "easter_egg" if filename == "redcap7.ogg" else "ambient" if filename.startswith("redcap") else "hurt" if filename.startswith("hurt") else "death"
            if role == "easter_egg":
                minimum, maximum = 0.65, 2.2
            else:
                minimum, maximum = limits[role]
            signal = decode(CANDIDATE_ROOT / filename)
            duration = signal.size / 44100.0
            self.assertGreaterEqual(duration, minimum, filename)
            self.assertLessEqual(duration, maximum, filename)
            self.assertGreater(float(np.max(np.abs(signal))), 0.05, filename)
            self.assertLessEqual(float(np.max(np.abs(signal))), 0.95, filename)
