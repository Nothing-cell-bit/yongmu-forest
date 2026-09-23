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
SOURCE_ROOT = ROOT / "tmp" / "hydra_audio_research" / "80-CC0-creature-SFX"
CANDIDATE_ROOT = ROOT / "tmp" / "hydra_audio_research" / "candidates"
GENERATOR = ROOT / "tools" / "generate_hydra_sounds.py"
UPSTREAM_ROOT = (
    ROOT.parent
    / "twilightforest-1.20.1-4.3.2508-extracted"
    / "00_original_tree"
    / "assets"
    / "twilightforest"
    / "sounds"
    / "mob"
    / "hydra"
)

TARGETS = {
    "warn.ogg": {
        "min_duration": 0.75,
        "max_duration": 1.25,
        "max_leading_silence": 0.08,
        "min_centroid": 260.0,
    },
    "death.ogg": {
        "min_duration": 1.25,
        "max_duration": 2.40,
        "max_leading_silence": 0.08,
        "min_tail_rms": 0.002,
    },
    "hurt1.ogg": {
        "min_duration": 0.32,
        "max_duration": 0.65,
        "max_leading_silence": 0.06,
        "min_first_50ms_rms": 0.04,
        "min_centroid": 700.0,
        "max_high_frequency_ratio": 0.35,
    },
}
HURT_VARIANTS = ("hurt1.ogg", "hurt2.ogg", "hurt3.ogg", "hurt4.ogg")
HYDRA_BANK_FILES = (
    "death.ogg",
    "growl1.ogg",
    "growl2.ogg",
    "growl3.ogg",
    "hurt1.ogg",
    "hurt2.ogg",
    "hurt3.ogg",
    "hurt4.ogg",
    "roar1.ogg",
    "roar2.ogg",
    "warn.ogg",
)


def decode(path: Path) -> np.ndarray:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise unittest.SkipTest("ffmpeg is required for Hydra audio tests")
    with tempfile.TemporaryDirectory(prefix="hydra_audio_test_") as temp_dir:
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


def leading_silence(signal: np.ndarray, sample_rate: int = 44100) -> float:
    envelope = np.convolve(
        np.abs(signal),
        np.ones(max(1, int(sample_rate * 0.01))) / max(1, int(sample_rate * 0.01)),
        mode="same",
    )
    threshold = max(float(np.max(np.abs(signal))) * 0.10, 1e-5)
    hits = np.flatnonzero(envelope >= threshold)
    return float(hits[0] / sample_rate) if hits.size else 999.0


def spectral_centroid(signal: np.ndarray, sample_rate: int = 44100) -> float:
    spectrum = np.abs(np.fft.rfft(signal * np.hanning(signal.size))) ** 2
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / sample_rate)
    return float((frequencies * spectrum).sum() / (spectrum.sum() + 1e-12))


class HydraAudioRepairTests(unittest.TestCase):
    def test_formal_hydra_bank_matches_the_reviewed_candidate_bank(self):
        for filename in HYDRA_BANK_FILES:
            formal = RP / "sounds" / "mob" / "hydra" / filename
            candidate = CANDIDATE_ROOT / filename
            self.assertTrue(candidate.is_file(), filename)
            self.assertEqual(
                formal.read_bytes(),
                candidate.read_bytes(),
                filename + " is not promoted from the reviewed Hydra bank",
            )

    def test_all_hurt_variants_rebuild_without_upstream_audio(self):
        with tempfile.TemporaryDirectory(prefix="hydra_hurt_rebuild_") as output_dir:
            subprocess.run(
                [
                    __import__("sys").executable,
                    str(GENERATOR),
                    "--source-root",
                    str(SOURCE_ROOT),
                    "--output-root",
                    output_dir,
                ],
                check=True,
            )
            for filename in HURT_VARIANTS:
                generated = Path(output_dir) / filename
                packaged = CANDIDATE_ROOT / filename
                self.assertTrue(generated.is_file(), filename)
                self.assertEqual(
                    generated.read_bytes(),
                    packaged.read_bytes(),
                    filename + " is not rebuilt in the local candidate set",
                )
                signal = decode(generated)
                self.assertGreaterEqual(signal.size / 44100.0, 0.32, filename)
                self.assertLessEqual(signal.size / 44100.0, 0.65, filename)
                self.assertLessEqual(
                    leading_silence(signal),
                    0.06,
                    filename + " starts too late",
                )
                self.assertGreaterEqual(
                    spectral_centroid(signal),
                    700.0,
                    filename + " is too low and flat",
                )
                self.assertGreaterEqual(
                    float(np.sqrt(np.mean(signal[: int(0.05 * 44100)] ** 2))),
                    0.04,
                    filename + " lacks an immediate hurt attack",
                )

    def test_formal_bank_contains_no_unmodified_upstream_recordings(self):
        for filename in HYDRA_BANK_FILES:
            packaged = RP / "sounds" / "mob" / "hydra" / filename
            upstream = UPSTREAM_ROOT / filename
            self.assertNotEqual(
                sha256(packaged),
                sha256(upstream),
                filename + " must not remain the upstream Twilight Forest recording",
            )

    def test_repaired_audio_has_role_specific_shape(self):
        for filename, spec in TARGETS.items():
            signal = decode(RP / "sounds" / "mob" / "hydra" / filename)
            duration = signal.size / 44100.0
            self.assertGreaterEqual(duration, spec["min_duration"], filename)
            self.assertLessEqual(duration, spec["max_duration"], filename)
            self.assertLessEqual(
                leading_silence(signal),
                spec["max_leading_silence"],
                filename + " starts too late",
            )
            if "min_centroid" in spec:
                self.assertGreaterEqual(
                    spectral_centroid(signal),
                    spec["min_centroid"],
                    filename + " is too low and flat",
                )
            if "max_high_frequency_ratio" in spec:
                spectrum = np.abs(np.fft.rfft(signal * np.hanning(signal.size))) ** 2
                frequencies = np.fft.rfftfreq(signal.size, 1.0 / 44100.0)
                high_frequency_ratio = float(
                    spectrum[frequencies >= 4000.0].sum()
                    / (spectrum.sum() + 1e-12)
                )
                self.assertLessEqual(
                    high_frequency_ratio,
                    spec["max_high_frequency_ratio"],
                    filename + " has an overly sharp high-frequency layer",
                )
            if "min_tail_rms" in spec:
                tail = signal[-int(0.2 * 44100) :]
                self.assertGreaterEqual(
                    float(np.sqrt(np.mean(tail * tail))),
                    spec["min_tail_rms"],
                    filename + " has an empty tail",
                )
            if "min_first_50ms_rms" in spec:
                first = signal[: int(0.05 * 44100)]
                self.assertGreaterEqual(
                    float(np.sqrt(np.mean(first * first))),
                    spec["min_first_50ms_rms"],
                    filename + " lacks an immediate hurt attack",
                )

    def test_generator_is_deterministic_and_matches_packaged_targets(self):
        self.assertTrue(GENERATOR.is_file())
        with tempfile.TemporaryDirectory(prefix="hydra_audio_rebuild_") as first_dir:
            with tempfile.TemporaryDirectory(prefix="hydra_audio_rebuild_") as second_dir:
                for output_dir in (Path(first_dir), Path(second_dir)):
                    subprocess.run(
                        [
                            __import__("sys").executable,
                            str(GENERATOR),
                            "--source-root",
                            str(SOURCE_ROOT),
                            "--output-root",
                            str(output_dir),
                        ],
                        check=True,
                    )
                for filename in TARGETS:
                    first = Path(first_dir) / filename
                    second = Path(second_dir) / filename
                    packaged = RP / "sounds" / "mob" / "hydra" / filename
                    self.assertEqual(first.read_bytes(), second.read_bytes(), filename)
                    self.assertEqual(first.read_bytes(), packaged.read_bytes(), filename)

    def test_hydra_event_paths_remain_closed(self):
        definitions = json.loads(
            (
                RP / "sounds" / "sound_definitions.json"
            ).read_text(encoding="utf-8")
        )["sound_definitions"]
        for event in ("death", "hurt", "warn"):
            self.assertIn("tf_slice.hydra." + event, definitions)
