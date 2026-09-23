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
    / "kobold"
)
CANDIDATE_ROOT = ROOT / "tmp" / "kobold_audio_research" / "candidates"
GENERATOR = ROOT / "tools" / "generate_kobold_sounds.py"
SOURCE_AUDIO = (
    ROOT / "tools" / "audio_sources" / "kobold" / "barking_of_a_dog.ogg",
    ROOT / "tools" / "audio_sources" / "kobold" / "barking_of_a_dog_2.ogg",
)
SOURCE_SHA256 = (
    "e4438897b68360e54c9e9319a8aea14a78527f022c2b78086f4b2348c03b2fa1",
    "d4e62e278cc0d7c9e502b7cb0041cdffb2b2dde31f1dba1016bb9f3866c03c27",
)

KOBOLD_FILES = (
    "ambient1.ogg",
    "ambient2.ogg",
    "ambient3.ogg",
    "ambient4.ogg",
    "ambient5.ogg",
    "ambient6.ogg",
    "death1.ogg",
    "death2.ogg",
    "death3.ogg",
    "hurt1.ogg",
    "hurt2.ogg",
    "hurt3.ogg",
    "shorfle.ogg",
)


def decode(path: Path) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise unittest.SkipTest("ffmpeg is required for Kobold audio tests")
    with tempfile.TemporaryDirectory(prefix="kobold_audio_test_") as temp_dir:
        wav_path = Path(temp_dir) / "decoded.wav"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(path),
                "-ac",
                "1",
                "-ar",
                "44100",
                str(wav_path),
            ],
            check=True,
        )
        with wave.open(str(wav_path), "rb") as wav:
            return (
                np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2")
                .astype(np.float64)
                / 32768.0
            )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def frame_rms(signal: np.ndarray, frame_seconds: float = 0.02) -> np.ndarray:
    frame_size = round(frame_seconds * 44100)
    return np.array(
        [
            np.sqrt(np.mean(signal[start : start + frame_size] ** 2))
            for start in range(0, signal.size - frame_size + 1, frame_size)
        ]
    )


def spectral_flatness(signal: np.ndarray) -> float:
    values = []
    frequencies = np.fft.rfftfreq(1024, 1.0 / 44100.0)
    band = (frequencies >= 200.0) & (frequencies <= 9_000.0)
    for start in range(0, signal.size - 1024, 512):
        frame = signal[start : start + 1024] * np.hanning(1024)
        magnitude = np.abs(np.fft.rfft(frame))[band]
        if float(np.sqrt(np.mean(frame**2))) < 0.01:
            continue
        values.append(
            float(np.exp(np.mean(np.log(magnitude + 1e-8))) / (np.mean(magnitude) + 1e-8))
        )
    return float(np.mean(values)) if values else 0.0


class KoboldAudioRepairTests(unittest.TestCase):
    def test_generator_and_reviewed_candidate_bank_exist(self):
        self.assertTrue(GENERATOR.is_file())
        self.assertTrue(CANDIDATE_ROOT.is_dir())
        for filename in KOBOLD_FILES:
            self.assertTrue((CANDIDATE_ROOT / filename).is_file(), filename)

    def test_formal_bank_has_all_kobold_audio_paths(self):
        formal_root = RP / "sounds" / "mob" / "kobold"
        for filename in KOBOLD_FILES:
            self.assertTrue((formal_root / filename).is_file(), filename)

        definitions = json.loads(
            (RP / "sounds" / "sound_definitions.json").read_text(encoding="utf-8")
        )["sound_definitions"]
        self.assertEqual(
            definitions["tf_slice.kobold.ambient"]["sounds"],
            [
                "sounds/mob/kobold/ambient%d" % index
                for index in range(1, 7)
            ],
        )
        self.assertEqual(
            definitions["tf_slice.kobold.hurt"]["sounds"],
            ["sounds/mob/kobold/hurt%d" % index for index in range(1, 4)],
        )
        self.assertEqual(
            definitions["tf_slice.kobold.death"]["sounds"],
            ["sounds/mob/kobold/death%d" % index for index in range(1, 4)],
        )

    def test_candidate_bank_is_not_unmodified_upstream_audio(self):
        for filename in KOBOLD_FILES:
            self.assertNotEqual(
                sha256(CANDIDATE_ROOT / filename),
                sha256(ORIGINAL_ROOT / filename),
                filename,
            )

    def test_generated_bank_matches_reviewed_candidate_bank(self):
        with tempfile.TemporaryDirectory(prefix="kobold_audio_rebuild_") as output_dir:
            subprocess.run(
                [
                    __import__("sys").executable,
                    str(GENERATOR),
                    "--source-audio",
                    str(SOURCE_AUDIO[0]),
                    "--source-audio",
                    str(SOURCE_AUDIO[1]),
                    "--output-root",
                    output_dir,
                ],
                check=True,
            )
            for filename in KOBOLD_FILES:
                self.assertEqual(
                    (Path(output_dir) / filename).read_bytes(),
                    (CANDIDATE_ROOT / filename).read_bytes(),
                    filename,
                )

    def test_generator_uses_pinned_dog_audio_not_kobold_audio(self):
        with tempfile.TemporaryDirectory(prefix="kobold_procedural_rebuild_") as output_dir:
            result = subprocess.run(
                [
                    __import__("sys").executable,
                    str(GENERATOR),
                    "--source-audio",
                    str(SOURCE_AUDIO[0]),
                    "--source-audio",
                    str(SOURCE_AUDIO[1]),
                    "--output-root",
                    output_dir,
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("original-root", result.stderr)
            for filename in KOBOLD_FILES:
                self.assertTrue((Path(output_dir) / filename).is_file(), filename)

    def test_pinned_dog_sources_are_present_and_hash_locked(self):
        for path, expected_hash in zip(SOURCE_AUDIO, SOURCE_SHA256):
            self.assertTrue(path.is_file(), path)
            self.assertEqual(sha256(path), expected_hash, path.name)

    def test_ambient_has_separated_bark_like_syllables(self):
        signal = decode(CANDIDATE_ROOT / "ambient1.ogg")
        rms = frame_rms(signal)
        rms /= max(float(rms.max()), 1e-9)
        central = rms[3:-4]
        active = central > 0.15 * float(rms.max())
        active_runs = np.count_nonzero(active & ~np.r_[False, active[:-1]])
        self.assertGreaterEqual(active_runs, 2)
        self.assertLess(float(np.min(central)), 0.45)

    def test_vocal_layers_are_noise_dominant_like_a_bark(self):
        for filename in ("ambient1.ogg", "hurt1.ogg", "death1.ogg"):
            self.assertGreater(
                spectral_flatness(decode(CANDIDATE_ROOT / filename)),
                0.035,
                filename,
            )

    def test_shorfle_is_a_single_muted_snuffle(self):
        signal = decode(CANDIDATE_ROOT / "shorfle.ogg")
        frequencies = np.fft.rfftfreq(signal.size, 1.0 / 44100.0)
        magnitude = np.abs(np.fft.rfft(signal))
        centroid = float((frequencies * magnitude).sum() / max(magnitude.sum(), 1e-9))
        self.assertLess(centroid, 3_200.0)
        rms = frame_rms(signal)
        active = rms > 0.15 * float(rms.max())
        active_runs = np.count_nonzero(active & ~np.r_[False, active[:-1]])
        self.assertLessEqual(active_runs, 3)

    def test_candidate_audio_is_short_clean_and_role_shaped(self):
        limits = {
            "ambient": (0.35, 1.35),
            "hurt": (0.25, 0.80),
            "death": (0.55, 1.55),
            "shorfle": (0.25, 0.90),
        }
        for filename in KOBOLD_FILES:
            kind = filename.rstrip("123.ogg")
            if kind not in limits:
                kind = "shorfle"
            signal = decode(CANDIDATE_ROOT / filename)
            duration = signal.size / 44100.0
            minimum, maximum = limits[kind]
            self.assertGreaterEqual(duration, minimum, filename)
            self.assertLessEqual(duration, maximum, filename)
            self.assertGreater(float(np.max(np.abs(signal))), 0.05, filename)
            self.assertLessEqual(float(np.max(np.abs(signal))), 0.95, filename)
