import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

import numpy as np

from tools import generate_wraith_sounds as generator


ROOT = Path(__file__).resolve().parents[1]
RP = ROOT / "TwilightBossSliceR"
ORIGINAL_ROOT = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree" / "assets" / "twilightforest" / "sounds" / "mob" / "wraith"
SOURCE_ROOT = ROOT / "tools" / "audio_sources" / "wraith" / "cc0_ghosts"
SOURCE_SHA256 = {
    "cc0_ghost_breath.mp3": "4155c6cdad6120400ebebedf746786cb0ebbccb62d51f88a1d9e44862d158842",
    "cc0_ghostly_humming.ogg": "270954cff9f076c81e0a16fac391cfcd1cedf6786fcb05cfa813a955ae539678",
    "cc0_atmospheric_ghostly_loops.mp3": "0bf2b0ec840e55c8d4fe93365279853c68d3dc1bd641d59601a310ec18ffbe2f",
    "cc0_ghost_moan_growl.mp3": "f481134439aadd6afedbf68d050817d27ccb62b8c52305f7e6b96bd9ce0582f9",
}
CANDIDATE_ROOT = ROOT / "tmp" / "wraith_audio_research" / "candidates"
GENERATOR = ROOT / "tools" / "generate_wraith_sounds.py"
WRAITH_FILES = ("wraith1.ogg", "wraith2.ogg", "wraith3.ogg", "wraith4.ogg")


def decode(path: Path) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for Wraith audio tests")
    with tempfile.TemporaryDirectory(prefix="wraith_audio_test_") as temp_dir:
        wav_path = Path(temp_dir) / "decoded.wav"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "44100", str(wav_path)], check=True)
        with wave.open(str(wav_path), "rb") as wav:
            return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64) / 32768.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WraithAudioRepairTests(unittest.TestCase):
    def test_wraith1_has_audible_voiced_body(self):
        signal = decode(CANDIDATE_ROOT / "wraith1.ogg")
        rms = float(np.sqrt(np.mean(signal**2)))
        zero_crossing_rate = float(np.mean(np.abs(np.diff(np.signbit(signal)))))
        self.assertGreater(rms, 0.12)
        self.assertLess(zero_crossing_rate, 0.04)

    def test_generator_and_reviewed_candidate_bank_exist(self):
        self.assertTrue(GENERATOR.is_file())
        self.assertTrue(CANDIDATE_ROOT.is_dir())
        for filename in WRAITH_FILES:
            self.assertTrue((CANDIDATE_ROOT / filename).is_file(), filename)

    def test_event_routes_keep_all_wraith_audio_paths(self):
        definitions = json.loads((RP / "sounds" / "sound_definitions.json").read_text(encoding="utf-8"))["sound_definitions"]
        expected = ["sounds/mob/wraith/wraith1", "sounds/mob/wraith/wraith2", "sounds/mob/wraith/wraith3", "sounds/mob/wraith/wraith4"]
        for event in ("ambient", "hurt", "death"):
            self.assertEqual(definitions[f"tf_slice.wraith.{event}"]["sounds"], expected)
        for filename in WRAITH_FILES:
            self.assertTrue((RP / "sounds" / "mob" / "wraith" / filename).is_file(), filename)

    def test_pinned_cc0_ghost_sources_are_hash_locked(self):
        for filename, expected_hash in SOURCE_SHA256.items():
            path = SOURCE_ROOT / filename
            self.assertTrue(path.is_file(), filename)
            self.assertEqual(sha256(path), expected_hash, filename)

    def test_candidates_are_not_unmodified_twilight_wraith_audio(self):
        for filename in WRAITH_FILES:
            self.assertNotEqual(sha256(CANDIDATE_ROOT / filename), sha256(ORIGINAL_ROOT / filename), filename)

    def test_generator_rebuilds_from_cc0_ghost_sources(self):
        with tempfile.TemporaryDirectory(prefix="wraith_audio_rebuild_") as output_dir:
            result = subprocess.run([__import__("sys").executable, str(GENERATOR), "--source-root", str(SOURCE_ROOT), "--output-root", output_dir], check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for filename in WRAITH_FILES:
                self.assertEqual((Path(output_dir) / filename).read_bytes(), (CANDIDATE_ROOT / filename).read_bytes(), filename)

    def test_outputs_are_clean_and_distinct(self):
        signals = []
        for filename in WRAITH_FILES:
            signal = decode(CANDIDATE_ROOT / filename)
            duration = signal.size / 44100.0
            expected_duration = generator.OUTPUT_SPECS[filename][0]
            self.assertAlmostEqual(duration, expected_duration, delta=0.02, msg=filename)
            self.assertGreater(float(np.max(np.abs(signal))), 0.03, filename)
            self.assertLessEqual(float(np.max(np.abs(signal))), 0.95, filename)
            self.assertLess(float(np.sqrt(np.mean(signal**2))), 0.35, filename)
            signals.append(np.interp(np.linspace(0.0, 1.0, 16_000), np.linspace(0.0, 1.0, signal.size), signal))
        correlations = [float(np.corrcoef(signals[i], signals[j])[0, 1]) for i in range(len(signals)) for j in range(i + 1, len(signals))]
        self.assertLess(max(correlations), 0.98)
