# -*- coding: utf-8 -*-
import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_cc0_roe_deer_sounds.py"
PACKAGED_DIR = ROOT / "TwilightBossSliceR" / "sounds" / "mob" / "deer"
SOUND_DEFINITIONS = (
    ROOT / "TwilightBossSliceR" / "sounds" / "sound_definitions.json"
)
SOURCE_AUDIO = (
    ROOT
    / "tools"
    / "audio_sources"
    / "deer"
    / "roe_deer_calls_forest_of_saou_724578_hq.mp3"
)
SOURCE_MANIFEST = SOURCE_AUDIO.with_suffix(".source.json")
EXPECTED_SOURCE_SHA256 = (
    "ae5294dc9aa810abb03f1e9b6680488a18ea3b06226b7fc17ba75db4d8ec5b1b"
)
EXPECTED_FILES = {
    "idle1.ogg",
    "idle2.ogg",
    "idle3.ogg",
    "hurt1.ogg",
    "hurt2.ogg",
    "death.ogg",
}
UPSTREAM_SHA256 = {
    "idle1.ogg": "6289427fa936fba6d58b3f0d0892bda138cd7d734760cca20355a70b7d75e6b9",
    "idle2.ogg": "f59d38fb90213c9647927eadc3a526646424383fc346af3e95d6acf499502b3c",
    "idle3.ogg": "292e8175f212609ba5f1c2ee6dd7c4dfc1f7ca9af0851ebe0e56ec3637b42842",
    "hurt1.ogg": "9821ad84beac0282b17fb196fa2ea1ff77b95a8a5684618f15f36f2c9c74af51",
    "hurt2.ogg": "c6694a881984609d2c376683e636fde44a681da998e98814b63cb7efbcdd81aa",
    "death.ogg": "cff8df1389cd571eda3b39c946519e5191a4270f32110e1178e0ae68e91e9712",
}
PREVIOUS_GOAT_BUILD_SHA256 = {
    "idle1.ogg": "27d7de0c0922acf7f46c0007556acac2cb5d45aa6219d06bd1cf6d1f118a59bc",
    "idle2.ogg": "878ef2e8b3292f9a2a0b66fa145ab057b834efa771e076d355fd4e4aad126e0c",
    "idle3.ogg": "22c7bf67aa7307d246818450386549c49f388a4d59800141cabfa9c31d073ceb",
    "hurt1.ogg": "3f9e32868130d3a9f7de4908f2f0885c49d0b44beef1b77ca13dd112363d1126",
    "hurt2.ogg": "d2cc2448c19b85b26a5377b58cd11d4e2e51f9131b536e340d6fad1c9f4147da",
    "death.ogg": "dd24eb051cb54a34530f73be98d862591f86c1303e000bae87bb19eb227b0746",
}
EXPECTED_SEGMENTS = {
    "idle1.ogg": (20.6, 1.8, 1.30, "idle", 0),
    "idle2.ogg": (29.0, 1.8, 1.30, "idle", 1),
    "idle3.ogg": (61.6, 1.8, 1.18, "idle", 2),
    "hurt1.ogg": (37.5, 1.8, 0.72, "hurt", 0),
    "hurt2.ogg": (29.0, 1.8, 0.70, "hurt", 1),
    "death.ogg": (20.4, 2.0, 1.42, "death", 0),
}


def load_generator():
    spec = importlib.util.spec_from_file_location("deer_audio_generator", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


def decode_ogg(path):
    result = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            "44100",
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype="<f4")


def frame_contrast_db(signal):
    frame_size = int(44_100 * 0.025)
    frame_rms = []
    for start in range(0, max(1, signal.size - frame_size), frame_size):
        frame = signal[start : start + frame_size]
        if frame.size:
            frame_rms.append(float(np.sqrt(np.mean(frame**2))))
    values = np.asarray(frame_rms)
    event = float(np.percentile(values, 90))
    noise = float(np.percentile(values, 20))
    return 20.0 * np.log10((event + 1e-8) / (noise + 1e-8))


def active_spectral_signature(signal):
    fft_size = 2_048
    hop_size = 512
    window = np.hanning(fft_size)
    rows = []
    for start in range(0, max(1, signal.size - fft_size), hop_size):
        frame = signal[start : start + fft_size]
        if frame.size != fft_size:
            continue
        rms = float(np.sqrt(np.mean(frame**2)))
        power = np.abs(np.fft.rfft(frame * window)) ** 2 + 1e-16
        frequencies = np.fft.rfftfreq(fft_size, 1.0 / 44_100)
        band = (frequencies >= 100.0) & (frequencies <= 6_000.0)
        band_power = power[band]
        band_frequencies = frequencies[band]
        total = float(band_power.sum())
        centroid = float((band_frequencies * band_power).sum() / total)
        bandwidth = float(
            np.sqrt(
                (((band_frequencies - centroid) ** 2) * band_power).sum()
                / total
            )
        )
        rows.append(
            (
                rms,
                float(band_frequencies[np.argmax(band_power)]),
                bandwidth,
                float(band_power.max() / total),
            )
        )
    values = np.asarray(rows)
    active = values[:, 0] >= np.percentile(values[:, 0], 65)
    selected = values[active]
    return tuple(float(np.median(selected[:, index])) for index in range(1, 4))


class DeerSoundRightsResetTests(unittest.TestCase):
    def test_generator_exists_for_reproducible_deer_audio(self):
        self.assertTrue(GENERATOR.is_file())

    def test_generator_records_the_exact_cc0_field_segments(self):
        generator = load_generator()
        self.assertEqual(EXPECTED_SEGMENTS, generator.SPECS)

    def test_cc0_source_and_manifest_are_pinned(self):
        self.assertTrue(SOURCE_AUDIO.is_file())
        self.assertEqual(EXPECTED_SOURCE_SHA256, sha256(SOURCE_AUDIO))
        manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual("CC0-1.0", manifest["license"])
        self.assertEqual(EXPECTED_SOURCE_SHA256, manifest["sha256"])
        self.assertEqual(
            "https://freesound.org/people/Sacha.Julien/sounds/724578/",
            manifest["sourcePage"],
        )

    def test_packaged_deer_audio_no_longer_matches_upstream(self):
        self.assertEqual(EXPECTED_FILES, {path.name for path in PACKAGED_DIR.glob("*.ogg")})
        for name, upstream_hash in UPSTREAM_SHA256.items():
            self.assertNotEqual(upstream_hash, sha256(PACKAGED_DIR / name))
            self.assertNotEqual(
                PREVIOUS_GOAT_BUILD_SHA256[name],
                sha256(PACKAGED_DIR / name),
            )

    def test_deer_sound_definitions_keep_the_stable_runtime_paths(self):
        definitions = json.loads(SOUND_DEFINITIONS.read_text(encoding="utf-8"))[
            "sound_definitions"
        ]
        paths = set()
        for event in (
            "tf_slice.deer.ambient",
            "tf_slice.deer.hurt",
            "tf_slice.deer.death",
        ):
            for entry in definitions[event]["sounds"]:
                paths.add(entry if isinstance(entry, str) else entry["name"])
        self.assertEqual(
            {"sounds/mob/deer/" + name[:-4] for name in EXPECTED_FILES},
            paths,
        )

    def test_noise_reduction_improves_call_to_background_contrast(self):
        generator = load_generator()
        source = generator.decode_source(SOURCE_AUDIO)
        for name, (start, source_duration, _, kind, _) in generator.SPECS.items():
            with self.subTest(name=name):
                raw = generator.extract_segment(
                    source,
                    start,
                    source_duration,
                )
                reduced = generator.reduce_field_noise(
                    raw,
                    kind,
                )
                self.assertGreater(
                    frame_contrast_db(reduced),
                    frame_contrast_db(raw) + 2.5,
                )

    def test_packaged_deer_audio_has_controlled_loudness_and_treble(self):
        for name in EXPECTED_FILES:
            with self.subTest(name=name):
                signal = decode_ogg(PACKAGED_DIR / name)
                peak = float(np.max(np.abs(signal)))
                rms = float(np.sqrt(np.mean(signal**2)))
                frequencies = np.fft.rfftfreq(signal.size, 1.0 / 44_100)
                power = np.abs(np.fft.rfft(signal)) ** 2
                treble_ratio = float(power[frequencies >= 5_000.0].sum())
                treble_ratio /= float(power.sum())
                self.assertGreater(peak, 0.35)
                self.assertLess(peak, 0.90)
                self.assertLess(rms, 0.30)
                self.assertLess(treble_ratio, 0.15)

    def test_packaged_deer_audio_rejects_narrowband_bird_whistles(self):
        for name in EXPECTED_FILES:
            with self.subTest(name=name):
                signal = decode_ogg(PACKAGED_DIR / name)
                dominant_hz, bandwidth_hz, peak_share = active_spectral_signature(
                    signal
                )
                self.assertLess(dominant_hz, 2_300.0)
                self.assertGreater(bandwidth_hz, 350.0)
                self.assertLess(peak_share, 0.25)

    def test_generator_reproduces_the_packaged_deer_audio(self):
        generator = load_generator()
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                sys,
                "argv",
                [
                    str(GENERATOR),
                    "--output-root",
                    temp_dir,
                    "--source-audio",
                    str(SOURCE_AUDIO),
                ],
            ):
                generator.main()
            generated = Path(temp_dir)
            for name in EXPECTED_FILES:
                self.assertEqual(sha256(PACKAGED_DIR / name), sha256(generated / name))


if __name__ == "__main__":
    unittest.main()
