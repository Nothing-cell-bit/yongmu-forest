# -*- coding: utf-8 -*-
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np

from tools import generate_original_naga_sounds as naga_generator


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "tools" / "generate_original_naga_sounds.py"
PACKAGED_DIR = (
    ROOT / "TwilightBossSliceR" / "sounds" / "mob" / "naga"
)
SOUND_DEFINITIONS = (
    ROOT / "TwilightBossSliceR" / "sounds" / "sound_definitions.json"
)
MINECRAFT_ASSETS = Path("D:/MC/.minecraft/assets")
EXPECTED_FILES = {
    "hiss1.ogg",
    "hiss2.ogg",
    "hiss3.ogg",
    "hurt1.ogg",
    "hurt2.ogg",
    "hurt3.ogg",
    "rattle1.ogg",
    "rattle2.ogg",
}
EXPECTED_MINECRAFT_HURT_SOURCES = {
    0: (
        "minecraft/sounds/mob/enderdragon/hit1.ogg",
        "aedeb53dd3315f964ff4d10d0003e4c5f41d1bb0",
    ),
    1: (
        "minecraft/sounds/mob/enderdragon/hit2.ogg",
        "46e5db05b1e91ce33c9c4c63260227fa629230f4",
    ),
    2: (
        "minecraft/sounds/mob/enderdragon/hit3.ogg",
        "e96237fdf5e5e1aca09496b9192243651525d0ac",
    ),
}
EXPECTED_HURT_PLAYBACK_RATES = (0.90, 0.84, 0.95)
EXPECTED_MINECRAFT_RATTLE_SOURCES = {
    0: (
        "minecraft/sounds/mob/skeleton/step1.ogg",
        "68e0a58848bbdad12ad2b216d7244754459c9516",
    ),
    1: (
        "minecraft/sounds/mob/skeleton/step2.ogg",
        "4609ec723b4e724f44c653b82de40ec159d2eea1",
    ),
}
UPSTREAM_SHA256 = {
    "hiss1.ogg": "A161D9C117008F3EDF82F5E858DEF0E32B7365B545F387A0A20928C8C6CB7B84",
    "hiss2.ogg": "B6D290D44EBB16F32AD9930175C87FA83C5BB694517E7E1159BD721B65D47300",
    "hiss3.ogg": "193AFCA1416ADF1994A0970F9A9B53A20539B3D98A6E5D40C19B23D3960F36AD",
    "hurt1.ogg": "C46DCD43839A55591AD4F344F23460AA5ECD62A1504694DC4F870E6ABC9F5BB5",
    "hurt2.ogg": "B71792658BD82B6563553301D708BA58EACCFEE9D0A29EFE6AA78D4DDF225E46",
    "hurt3.ogg": "63E2D40665DE42CB83EEC73A934EB205FB63D479AC04E17E3D5A1FFFD142796F",
    "rattle1.ogg": "21EA4E751ABFD81E07AB895EAAD74D33A7C0B65E019C98F95E1D5342AA417DF5",
    "rattle2.ogg": "538308BDF005B063F977A20D75C454CD5BB30C9000ED217C5DE99BACE8BAF44F",
}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


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
            str(naga_generator.SAMPLE_RATE),
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype="<f4")


class NagaSoundRightsResetTests(unittest.TestCase):
    def test_generator_exists_for_reproducible_naga_audio(self):
        self.assertTrue(GENERATOR.is_file())

    def test_hurt_generator_records_the_vanilla_ender_dragon_sources(self):
        self.assertEqual(
            EXPECTED_MINECRAFT_HURT_SOURCES,
            naga_generator.MINECRAFT_HURT_SOURCES,
        )
        self.assertEqual(
            EXPECTED_HURT_PLAYBACK_RATES,
            naga_generator.HURT_PLAYBACK_RATES,
        )

    def test_rattle_generator_records_the_vanilla_skeleton_sources(self):
        self.assertEqual(
            EXPECTED_MINECRAFT_RATTLE_SOURCES,
            naga_generator.MINECRAFT_RATTLE_SOURCES,
        )

    def test_rattle_transform_uses_grains_without_replaying_the_source(self):
        rattle_specs = [
            spec for spec in naga_generator.SPECS.values() if spec[2] == "rattle"
        ]
        for variant, (_, source_hash) in EXPECTED_MINECRAFT_RATTLE_SOURCES.items():
            with self.subTest(variant=variant):
                source_path = (
                    MINECRAFT_ASSETS
                    / "objects"
                    / source_hash[:2]
                    / source_hash
                )
                source = decode_ogg(source_path)
                duration, seed, _, _ = rattle_specs[variant]
                transformed = naga_generator.transform_minecraft_rattle(
                    source,
                    duration,
                    seed,
                    variant,
                )
                without_source = naga_generator.transform_minecraft_rattle(
                    np.zeros_like(source),
                    duration,
                    seed,
                    variant,
                )

                source_contribution = transformed - without_source
                contribution_ratio = float(
                    np.sqrt(np.mean(source_contribution**2))
                    / np.sqrt(np.mean(transformed**2))
                )
                comparison_size = min(source.size, transformed.size)
                direct_correlation = float(
                    np.corrcoef(
                        transformed[:comparison_size],
                        source[:comparison_size],
                    )[0, 1]
                )

                self.assertGreater(contribution_ratio, 0.30)
                self.assertLess(contribution_ratio, 0.82)
                self.assertLess(abs(direct_correlation), 0.40)

    def test_packaged_rattle_has_controlled_loudness_and_treble(self):
        for variant in EXPECTED_MINECRAFT_RATTLE_SOURCES:
            with self.subTest(variant=variant):
                signal = decode_ogg(PACKAGED_DIR / f"rattle{variant + 1}.ogg")
                peak = float(np.max(np.abs(signal)))
                rms = float(np.sqrt(np.mean(signal**2)))
                frequencies = np.fft.rfftfreq(
                    signal.size,
                    1.0 / naga_generator.SAMPLE_RATE,
                )
                power = np.abs(np.fft.rfft(signal)) ** 2
                high_ratio = float(power[frequencies >= 4_000.0].sum())
                high_ratio /= float(power.sum())

                self.assertLess(peak, 0.72)
                self.assertLess(rms, 0.18)
                self.assertLess(rms / peak, 0.28)
                self.assertLess(high_ratio, 0.50)

    def test_packaged_hurt_sounds_transform_but_retain_the_vanilla_attack(self):
        for variant, (_, source_hash) in EXPECTED_MINECRAFT_HURT_SOURCES.items():
            with self.subTest(variant=variant):
                source_path = (
                    MINECRAFT_ASSETS
                    / "objects"
                    / source_hash[:2]
                    / source_hash
                )
                source = decode_ogg(source_path)
                output = decode_ogg(PACKAGED_DIR / f"hurt{variant + 1}.ogg")
                positions = np.arange(output.size) * EXPECTED_HURT_PLAYBACK_RATES[
                    variant
                ]
                reference = np.interp(
                    positions,
                    np.arange(source.size),
                    source,
                )
                attack_size = max(1, int(output.size * 0.18))
                attack_correlation = float(
                    np.corrcoef(
                        output[:attack_size],
                        reference[:attack_size],
                    )[0, 1]
                )
                body_size = max(1, int(output.size * 0.65))
                body_correlation = float(
                    np.corrcoef(
                        output[:body_size],
                        reference[:body_size],
                    )[0, 1]
                )
                self.assertGreater(attack_correlation, 0.45)
                self.assertLess(body_correlation, 0.78)

    def test_packaged_naga_audio_no_longer_matches_upstream(self):
        self.assertEqual(
            EXPECTED_FILES,
            {path.name for path in PACKAGED_DIR.glob("*.ogg")},
        )
        for name, upstream_hash in UPSTREAM_SHA256.items():
            self.assertNotEqual(upstream_hash, sha256(PACKAGED_DIR / name))

    def test_naga_sound_definitions_keep_the_stable_runtime_paths(self):
        definitions = json.loads(
            SOUND_DEFINITIONS.read_text(encoding="utf-8")
        )["sound_definitions"]
        paths = set()
        for event in (
            "tf_slice.naga.ambient",
            "tf_slice.naga.hurt",
            "tf_slice.naga.death",
            "tf_slice.naga.rattle",
        ):
            for entry in definitions[event]["sounds"]:
                paths.add(entry if isinstance(entry, str) else entry["name"])
        self.assertEqual(
            {"sounds/mob/naga/" + name[:-4] for name in EXPECTED_FILES},
            paths,
        )

    def test_generator_reproduces_the_packaged_naga_audio(self):
        self.assertTrue(GENERATOR.is_file())
        with tempfile.TemporaryDirectory() as temp_dir:
            with mock.patch.object(
                sys,
                "argv",
                [
                    str(GENERATOR),
                    "--output-root",
                    temp_dir,
                    "--minecraft-assets-root",
                    str(MINECRAFT_ASSETS),
                ],
            ):
                naga_generator.main()
            generated = Path(temp_dir)
            for name in EXPECTED_FILES:
                self.assertEqual(
                    sha256(PACKAGED_DIR / name),
                    sha256(generated / name),
                    name,
                )

    def test_minecraft_based_hurt_sounds_are_short_and_clean(self):
        for name, (duration, seed, kind, variant) in naga_generator.SPECS.items():
            if kind != "hurt":
                continue

            with self.subTest(name=name):
                signal = decode_ogg(PACKAGED_DIR / name)
                frequencies = np.fft.rfftfreq(
                    signal.size,
                    1.0 / naga_generator.SAMPLE_RATE,
                )
                power = np.abs(np.fft.rfft(signal)) ** 2
                total_power = float(power.sum())
                centroid_hz = float((frequencies * power).sum() / total_power)
                treble_ratio = float(power[frequencies >= 5_000.0].sum())
                treble_ratio /= total_power
                snake_band_ratio = float(
                    power[frequencies >= 2_500.0].sum()
                )
                snake_band_ratio /= total_power

                head = signal[: max(1, int(signal.size * 0.50))]
                tail = signal[int(signal.size * 0.80) :]
                head_rms = float(np.sqrt(np.mean(head**2)))
                tail_rms = float(np.sqrt(np.mean(tail**2)))

                self.assertAlmostEqual(
                    signal.size / naga_generator.SAMPLE_RATE,
                    duration,
                    delta=0.03,
                )
                self.assertGreater(centroid_hz, 150.0)
                self.assertLess(centroid_hz, 900.0)
                self.assertLess(treble_ratio, 0.075)
                self.assertGreater(snake_band_ratio, 0.025)
                self.assertLess(tail_rms, head_rms * 0.32)
                self.assertGreater(float(np.max(np.abs(signal))), 0.70)


if __name__ == "__main__":
    unittest.main()
