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
ORIGINAL_ROOT = ROOT.parent / "twilightforest-1.20.1-4.3.2508-extracted" / "00_original_tree" / "assets" / "twilightforest" / "sounds" / "mob" / "tiny_bird"
SOURCE_ROOT = ROOT / "tools" / "audio_sources" / "tiny_bird" / "cc0_birds"
SOURCE_SHA256 = {
    "separated_chirps.ogg": "59e49e5bfc8f3b0dee8f925f2731af5333c5e04ec251547c664e58d0afb9f2ac",
    "phylloscopus_thiru.ogg": "474f8e7f7b186edecc3e6079d73970f3646bee975896370070c15758579e6884",
}
CANDIDATE_ROOT = ROOT / "tmp" / "tiny_bird_audio_research" / "candidates"
GENERATOR = ROOT / "tools" / "generate_tiny_bird_sounds.py"
BIRD_FILES = ("chirp1.ogg", "chirp2.ogg", "chirp3.ogg", "hurt1.ogg", "hurt2.ogg", "song1.ogg", "song2.ogg")


def decode(path: Path) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise unittest.SkipTest("ffmpeg is required for Tiny Bird audio tests")
    with tempfile.TemporaryDirectory(prefix="tiny_bird_audio_test_") as temp_dir:
        wav_path = Path(temp_dir) / "decoded.wav"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "44100", str(wav_path)], check=True)
        with wave.open(str(wav_path), "rb") as wav:
            return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").astype(np.float64) / 32768.0


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TinyBirdAudioRepairTests(unittest.TestCase):
    def test_generator_and_reviewed_candidate_bank_exist(self):
        self.assertTrue(GENERATOR.is_file())
        self.assertTrue(CANDIDATE_ROOT.is_dir())
        for filename in BIRD_FILES:
            self.assertTrue((CANDIDATE_ROOT / filename).is_file(), filename)

    def test_event_routes_keep_all_tiny_bird_audio_paths(self):
        definitions = json.loads((RP / "sounds" / "sound_definitions.json").read_text(encoding="utf-8"))["sound_definitions"]
        self.assertEqual(definitions["tf_slice.tiny_bird.chirp"]["sounds"], ["sounds/mob/tiny_bird/chirp%d" % index for index in range(1, 4)])
        self.assertEqual(definitions["tf_slice.tiny_bird.hurt"]["sounds"], ["sounds/mob/tiny_bird/hurt1", "sounds/mob/tiny_bird/hurt2"])
        self.assertEqual(definitions["tf_slice.tiny_bird.song"]["sounds"], ["sounds/mob/tiny_bird/song1", "sounds/mob/tiny_bird/song2"])
        for filename in BIRD_FILES:
            self.assertTrue((RP / "sounds" / "mob" / "tiny_bird" / filename).is_file(), filename)

    def test_pinned_cc0_bird_sources_are_hash_locked(self):
        for filename, expected_hash in SOURCE_SHA256.items():
            path = SOURCE_ROOT / filename
            self.assertTrue(path.is_file(), filename)
            self.assertEqual(sha256(path), expected_hash, filename)

    def test_candidates_are_not_unmodified_twilight_bird_audio(self):
        for filename in BIRD_FILES:
            self.assertNotEqual(sha256(CANDIDATE_ROOT / filename), sha256(ORIGINAL_ROOT / filename), filename)

    def test_generator_rebuilds_from_cc0_bird_sources(self):
        with tempfile.TemporaryDirectory(prefix="tiny_bird_audio_rebuild_") as output_dir:
            command = [__import__("sys").executable, str(GENERATOR), "--source-root", str(SOURCE_ROOT), "--output-root", output_dir]
            result = subprocess.run(command, check=False, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for filename in BIRD_FILES:
                self.assertEqual((Path(output_dir) / filename).read_bytes(), (CANDIDATE_ROOT / filename).read_bytes(), filename)

    def test_bird_variants_are_not_near_duplicates(self):
        signals = []
        for filename in BIRD_FILES:
            signal = decode(CANDIDATE_ROOT / filename)
            signals.append(np.interp(np.linspace(0.0, signal.size - 1.0, 20_000), np.arange(signal.size), signal))
        correlations = [float(np.corrcoef(signals[i], signals[j])[0, 1]) for i in range(len(signals)) for j in range(i + 1, len(signals))]
        self.assertLess(max(correlations), 0.97)

    def test_outputs_are_short_clean_and_role_shaped(self):
        limits = {"chirp": (0.25, 1.1), "hurt": (0.20, 0.75), "song": (1.5, 6.5)}
        for filename in BIRD_FILES:
            role = "chirp" if filename.startswith("chirp") else "hurt" if filename.startswith("hurt") else "song"
            signal = decode(CANDIDATE_ROOT / filename)
            duration = signal.size / 44100.0
            self.assertGreaterEqual(duration, limits[role][0], filename)
            self.assertLessEqual(duration, limits[role][1], filename)
            self.assertGreater(float(np.max(np.abs(signal))), 0.03, filename)
            self.assertLessEqual(float(np.max(np.abs(signal))), 0.95, filename)

