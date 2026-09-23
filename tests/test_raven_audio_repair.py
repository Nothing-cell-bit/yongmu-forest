import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np
from tools import generate_raven_sounds as generator


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
ORIGINAL_ROOT = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree" / "assets" / "twilightforest" / "sounds" / "mob" / "raven"
SOURCE_ROOT = ROOT / "tools" / "audio_sources" / "raven" / "public_domain"
SOURCE_SHA256 = {
    "cc0_crow_caw.wav": "bba22883209b435905471d057160f1badae59b89a62e9a8b3199d7e327b17339",
    "public_domain_hooded_crow.ogg": "16026c1a65e185bdee21c95f341c306d3687ebf2d4660e7ff2fcaa2538396098",
}
CANDIDATE_ROOT = ROOT / "tmp" / "raven_audio_research" / "candidates"
GENERATOR = ROOT / "tools" / "generate_raven_sounds.py"
RAVEN_FILES = ("caw1.ogg", "caw2.ogg", "squawk1.ogg", "squawk2.ogg")


def decode(path: Path) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise unittest.SkipTest("ffmpeg is required for Raven audio tests")
    with tempfile.TemporaryDirectory(prefix="raven_audio_test_") as temp_dir:
        wav_path = Path(temp_dir) / "decoded.wav"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "44100", str(wav_path)], check=True)
        with wave.open(str(wav_path), "rb") as wav:
            return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64) / 32768.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RavenAudioRepairTests(unittest.TestCase):
    def test_generator_helpers_handle_short_and_silent_inputs(self):
        silent = np.zeros(round(0.2 * generator.SAMPLE_RATE), dtype=np.float64)
        self.assertEqual(len(generator.split_calls(silent)), 1)
        fitted = generator.fit(np.ones(100, dtype=np.float64), 0.1, 0.5)
        self.assertEqual(fitted.size, round(0.1 * generator.SAMPLE_RATE))
        target = np.zeros(10, dtype=np.float64)
        generator.place(target, np.ones(3, dtype=np.float64), 1.0, 1.0)
        self.assertTrue(np.all(target == 0.0))

    def test_generator_and_reviewed_candidate_bank_exist(self):
        self.assertTrue(GENERATOR.is_file())
        self.assertTrue(CANDIDATE_ROOT.is_dir())
        for filename in RAVEN_FILES:
            self.assertTrue((CANDIDATE_ROOT / filename).is_file(), filename)

    def test_event_routes_keep_all_raven_audio_paths(self):
        definitions = json.loads((RP / "sounds" / "sound_definitions.json").read_text(encoding="utf-8"))["sound_definitions"]
        self.assertEqual(definitions["tf_slice.raven.ambient"]["sounds"], ["sounds/mob/raven/caw1", "sounds/mob/raven/caw2"])
        self.assertEqual(definitions["tf_slice.raven.hurt"]["sounds"], ["sounds/mob/raven/squawk1", "sounds/mob/raven/squawk2"])
        self.assertEqual(definitions["tf_slice.raven.death"]["sounds"], ["sounds/mob/raven/squawk1", "sounds/mob/raven/squawk2"])
        for filename in RAVEN_FILES:
            self.assertTrue((RP / "sounds" / "mob" / "raven" / filename).is_file(), filename)

    def test_pinned_public_domain_raven_sources_are_hash_locked(self):
        for filename, expected_hash in SOURCE_SHA256.items():
            path = SOURCE_ROOT / filename
            self.assertTrue(path.is_file(), filename)
            self.assertEqual(sha256(path), expected_hash, filename)

    def test_candidates_depend_on_distinct_crow_and_hooded_crow_sources(self):
        source_signals = [decode(SOURCE_ROOT / filename) for filename in SOURCE_SHA256]
        candidate_signals = [decode(CANDIDATE_ROOT / filename) for filename in RAVEN_FILES]
        source_peaks = [float(np.max(np.abs(signal))) for signal in source_signals]
        self.assertGreater(source_peaks[0], 0.03)
        self.assertGreater(source_peaks[1], 0.30)
        def activity(signal):
            frame_size = round(0.01 * 44100)
            values = [
                np.sqrt(np.mean(signal[index : index + frame_size] ** 2))
                for index in range(0, signal.size - frame_size + 1, frame_size)
            ]
            return np.interp(np.linspace(0.0, 1.0, 100), np.linspace(0.0, 1.0, len(values)), values)

        source_activity = [activity(signal) for signal in source_signals]
        candidate_correlations = [
            [float(np.corrcoef(source_activity[index], activity(candidate))[0, 1]) for index in range(2)]
            for candidate in candidate_signals
        ]
        self.assertGreater(candidate_correlations[0][0], 0.30)
        for correlations in candidate_correlations[1:]:
            self.assertGreater(max(correlations), 0.30)

    def test_candidates_are_not_unmodified_twilight_raven_audio(self):
        for filename in RAVEN_FILES:
            self.assertNotEqual(sha256(CANDIDATE_ROOT / filename), sha256(ORIGINAL_ROOT / filename), filename)

    def test_generator_rebuilds_from_public_domain_raven_sources(self):
        with tempfile.TemporaryDirectory(prefix="raven_audio_rebuild_") as output_dir:
            result = subprocess.run([__import__("sys").executable, str(GENERATOR), "--source-root", str(SOURCE_ROOT), "--output-root", output_dir], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for filename in RAVEN_FILES:
                self.assertEqual((Path(output_dir) / filename).read_bytes(), (CANDIDATE_ROOT / filename).read_bytes(), filename)

    def test_outputs_are_short_clean_and_distinct(self):
        limits = {"caw": (0.12, 0.75), "squawk": (0.15, 0.90)}
        signals = []
        for filename in RAVEN_FILES:
            role = "caw" if filename.startswith("caw") else "squawk"
            signal = decode(CANDIDATE_ROOT / filename)
            duration = signal.size / 44100.0
            self.assertGreaterEqual(duration, limits[role][0], filename)
            self.assertLessEqual(duration, limits[role][1], filename)
            self.assertGreater(float(np.max(np.abs(signal))), 0.03, filename)
            self.assertLessEqual(float(np.max(np.abs(signal))), 0.95, filename)
            signals.append(np.interp(np.linspace(0.0, signal.size - 1.0, 16_000), np.arange(signal.size), signal))
        correlations = [float(np.corrcoef(signals[i], signals[j])[0, 1]) for i in range(len(signals)) for j in range(i + 1, len(signals))]
        self.assertLess(max(correlations), 0.98)

    def test_caw1_contains_a_full_audible_raven_call(self):
        signal = decode(CANDIDATE_ROOT / "caw1.ogg")
        frame_size = round(0.01 * 44100)
        rms = np.array([np.sqrt(np.mean(signal[i : i + frame_size] ** 2)) for i in range(0, signal.size - frame_size + 1, frame_size)])
        self.assertGreater(float(np.mean(rms > 0.12 * rms.max())), 0.55)
        self.assertGreater(float(rms.max()), 0.10)
