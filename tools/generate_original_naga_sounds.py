#!/usr/bin/env python3
"""Generate adapted Naga audio for the NetEase resource pack.

The hiss bank is procedural and consumes no Twilight Forest audio. The hurt
and rattle banks adapt installed Minecraft Java 1.20.1 Ender Dragon hit and
Skeleton step sounds, verified by Mojang asset-object SHA-1 before use. Keeping
the runtime paths stable lets the existing entity and combat-event wiring
continue to work without carrying the original Twilight Forest recordings.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 44_100
MINECRAFT_HURT_SOURCES = {
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
HURT_PLAYBACK_RATES = (0.90, 0.84, 0.95)
MINECRAFT_RATTLE_SOURCES = {
    0: (
        "minecraft/sounds/mob/skeleton/step1.ogg",
        "68e0a58848bbdad12ad2b216d7244754459c9516",
    ),
    1: (
        "minecraft/sounds/mob/skeleton/step2.ogg",
        "4609ec723b4e724f44c653b82de40ec159d2eea1",
    ),
}
SPECS = {
    "hiss1.ogg": (1.906939, 20_260_831, "hiss", 0),
    "hiss2.ogg": (1.285487, 20_260_832, "hiss", 1),
    "hiss3.ogg": (1.009741, 20_260_833, "hiss", 2),
    "hurt1.ogg": (0.484308, 20_260_841, "hurt", 0),
    "hurt2.ogg": (0.692018, 20_260_842, "hurt", 1),
    "hurt3.ogg": (0.365578, 20_260_843, "hurt", 2),
    "rattle1.ogg": (1.475057, 20_260_851, "rattle", 0),
    "rattle2.ogg": (1.208481, 20_260_852, "rattle", 1),
}


def spectral_band(
    noise: np.ndarray,
    center_hz: float,
    width_hz: float,
) -> np.ndarray:
    spectrum = np.fft.rfft(noise)
    frequencies = np.fft.rfftfreq(noise.size, 1.0 / SAMPLE_RATE)
    curve = np.exp(-0.5 * ((frequencies - center_hz) / width_hz) ** 2)
    curve *= 1.0 - np.exp(-frequencies / 700.0)
    return np.fft.irfft(spectrum * curve, noise.size)


def smooth_random_envelope(
    rng: np.random.Generator,
    size: int,
    duration: float,
    knot_seconds: float,
    low: float,
    high: float,
) -> np.ndarray:
    knot_count = max(4, int(math.ceil(duration / knot_seconds)) + 1)
    knot_x = np.linspace(0, size - 1, knot_count)
    knot_y = rng.uniform(low, high, knot_count)
    envelope = np.interp(np.arange(size), knot_x, knot_y)
    window_size = max(3, int(SAMPLE_RATE * 0.018))
    window = np.hanning(window_size)
    window /= window.sum()
    return np.convolve(envelope, window, mode="same")


def gaussian_burst(
    time: np.ndarray,
    center: float,
    width: float,
) -> np.ndarray:
    return np.exp(-0.5 * ((time - center) / width) ** 2)


def edge_envelope(
    time: np.ndarray,
    duration: float,
    attack: float,
    release: float,
) -> np.ndarray:
    return np.clip(time / attack, 0.0, 1.0) * np.clip(
        (duration - time) / release,
        0.0,
        1.0,
    )


def normalize(signal: np.ndarray, peak: float = 0.51) -> np.ndarray:
    signal = np.tanh(signal * 1.35)
    current_peak = float(np.max(np.abs(signal)))
    if current_peak:
        signal *= peak / current_peak
    return signal


def unit_rms(signal: np.ndarray) -> np.ndarray:
    current_rms = float(np.sqrt(np.mean(signal**2)))
    if not current_rms:
        return signal
    return signal / current_rms


def generate_hiss(duration: float, seed: int, variant: int) -> np.ndarray:
    sample_count = int(round(SAMPLE_RATE * duration))
    time = np.arange(sample_count) / SAMPLE_RATE
    rng = np.random.default_rng(seed)

    center_shift = (0.0, 420.0, -280.0)[variant]
    low_air = spectral_band(
        rng.standard_normal(sample_count),
        3_100.0 + center_shift * 0.35,
        1_250.0,
    )
    mid_hiss = spectral_band(
        rng.standard_normal(sample_count),
        5_700.0 + center_shift,
        1_650.0,
    )
    bright_hiss = spectral_band(
        rng.standard_normal(sample_count),
        8_600.0 + center_shift * 1.25,
        2_050.0,
    )

    low_air *= smooth_random_envelope(
        rng, sample_count, duration, 0.19, 0.25, 0.70
    )
    mid_hiss *= smooth_random_envelope(
        rng, sample_count, duration, 0.11, 0.55, 1.00
    )
    bright_hiss *= smooth_random_envelope(
        rng, sample_count, duration, 0.075, 0.30, 0.95
    )

    flick_noise = spectral_band(
        rng.standard_normal(sample_count),
        9_800.0 + center_shift,
        1_500.0,
    )
    flick_fractions = (
        ((0.205, 0.232), (0.566, 0.592)),
        ((0.265, 0.302), (0.690, 0.724)),
        ((0.185, 0.220), (0.515, 0.553)),
    )[variant]
    flicks = np.zeros(sample_count)
    for first, second in flick_fractions:
        flicks += 0.46 * gaussian_burst(time, duration * first, 0.017)
        flicks += 0.30 * gaussian_burst(time, duration * second, 0.013)

    signal = (
        0.22 * low_air
        + 0.62 * mid_hiss
        + 0.46 * bright_hiss
        + flick_noise * flicks
    )
    breath_shape = np.sin(
        np.pi * np.clip(time / duration, 0.0, 1.0)
    ) ** 0.22
    signal *= edge_envelope(time, duration, 0.085, min(0.38, duration * 0.34))
    signal *= breath_shape
    return normalize(signal)


def transform_minecraft_hurt(
    source: np.ndarray,
    duration: float,
    seed: int,
    variant: int,
) -> np.ndarray:
    sample_count = int(round(SAMPLE_RATE * duration))
    time = np.arange(sample_count) / SAMPLE_RATE
    rng = np.random.default_rng(seed)

    constant_positions = np.arange(sample_count) * HURT_PLAYBACK_RATES[variant]
    vanilla_attack = np.interp(
        constant_positions,
        np.arange(source.size),
        source,
        left=0.0,
        right=0.0,
    )

    # Bend the source progressively downward instead of replaying it at one
    # fixed rate. The first few milliseconds remain recognizably Minecraft;
    # the body quickly diverges into a heavier, lower serpent rasp.
    progress = np.clip(time / duration, 0.0, 1.0)
    end_rates = (0.62, 0.56, 0.68)
    instantaneous_rate = HURT_PLAYBACK_RATES[variant] + (
        end_rates[variant] - HURT_PLAYBACK_RATES[variant]
    ) * progress**1.15
    warped_positions = np.cumsum(instantaneous_rate)
    warped_positions -= warped_positions[0]
    warped_hit = np.interp(
        warped_positions,
        np.arange(source.size),
        source,
        left=0.0,
        right=0.0,
    )

    envelope_window_size = max(3, int(SAMPLE_RATE * 0.012))
    envelope_window = np.ones(envelope_window_size) / envelope_window_size
    source_envelope = np.convolve(
        np.abs(warped_hit),
        envelope_window,
        mode="same",
    )
    source_envelope /= max(float(source_envelope.max()), 1e-9)

    start_hz = (285.0, 245.0, 325.0)[variant]
    end_hz = (118.0, 96.0, 142.0)[variant]
    throat_frequency = end_hz + (start_hz - end_hz) * np.exp(
        -time / (duration * 0.34)
    )
    throat_frequency *= 1.0 + 0.025 * np.sin(
        2.0 * np.pi * (24.0 + variant * 3.0) * time
    )
    throat_phase = 2.0 * np.pi * np.cumsum(throat_frequency) / SAMPLE_RATE
    throat = np.sin(throat_phase)
    throat += 0.27 * np.sin(2.01 * throat_phase + 0.35)
    throat += 0.09 * np.sin(3.04 * throat_phase + 0.90)

    # The hiss sits mainly between 2.5 and 5 kHz: audible as a snake exhale,
    # but below the brittle top end that made the earlier procedural take harsh.
    breath = unit_rms(
        spectral_band(
            rng.standard_normal(sample_count),
            (3_450.0, 3_200.0, 3_700.0)[variant],
            820.0,
        )
    )
    attack = np.clip(time / 0.0035, 0.0, 1.0)
    release_seconds = (0.140, 0.120, 0.135)[variant]
    release = np.clip((duration - time) / release_seconds, 0.0, 1.0)
    voice_envelope = attack * release
    breath_envelope = edge_envelope(
        time,
        duration,
        0.018,
        release_seconds,
    ) * np.exp(-time / (duration * 0.56))

    direct_attack_weight = np.exp(-time / (0.070 + variant * 0.008))
    throat_flutter = 0.78 + 0.22 * np.sin(
        2.0 * np.pi * (28.0 + variant * 4.0) * time + 0.40
    )
    signal = 0.54 * vanilla_attack * direct_attack_weight
    signal += 0.34 * warped_hit * throat_flutter
    signal += 0.30 * throat * source_envelope
    signal += 0.105 * breath * breath_envelope
    signal *= voice_envelope
    return normalize(signal, peak=0.82)


def minecraft_hurt_source_path(
    minecraft_assets_root: Path,
    variant: int,
) -> Path:
    _, expected_sha1 = MINECRAFT_HURT_SOURCES[variant]
    path = (
        minecraft_assets_root
        / "objects"
        / expected_sha1[:2]
        / expected_sha1
    )
    if not path.is_file():
        raise FileNotFoundError(
            f"Minecraft hurt source is missing for variant {variant}: {path}"
        )
    actual_sha1 = hashlib.sha1(path.read_bytes()).hexdigest()
    if actual_sha1 != expected_sha1:
        raise ValueError(
            f"Minecraft hurt source hash mismatch for variant {variant}: "
            f"expected {expected_sha1}, got {actual_sha1}"
        )
    return path


def minecraft_rattle_source_path(
    minecraft_assets_root: Path,
    variant: int,
) -> Path:
    _, expected_sha1 = MINECRAFT_RATTLE_SOURCES[variant]
    path = (
        minecraft_assets_root
        / "objects"
        / expected_sha1[:2]
        / expected_sha1
    )
    if not path.is_file():
        raise FileNotFoundError(
            f"Minecraft rattle source is missing for variant {variant}: {path}"
        )
    actual_sha1 = hashlib.sha1(path.read_bytes()).hexdigest()
    if actual_sha1 != expected_sha1:
        raise ValueError(
            f"Minecraft rattle source hash mismatch for variant {variant}: "
            f"expected {expected_sha1}, got {actual_sha1}"
        )
    return path


def decode_ogg(ffmpeg: str, source_path: Path) -> np.ndarray:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(source_path),
            "-f",
            "f32le",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype="<f4").copy()


def transform_minecraft_rattle(
    source: np.ndarray,
    duration: float,
    seed: int,
    variant: int,
) -> np.ndarray:
    sample_count = int(round(SAMPLE_RATE * duration))
    time = np.arange(sample_count) / SAMPLE_RATE
    rng = np.random.default_rng(seed)

    shell_noise = unit_rms(
        spectral_band(
            rng.standard_normal(sample_count),
            3_550.0 + variant * 300.0,
            1_100.0,
        )
    )
    body_noise = unit_rms(
        spectral_band(
            rng.standard_normal(sample_count),
            1_120.0 + variant * 110.0,
            520.0,
        )
    )
    pulse_envelope = np.zeros(sample_count)
    source_grains = np.zeros(sample_count)
    low_clicks = np.zeros(sample_count)
    rate = (14.0, 17.0)[variant]
    pulse_time = 0.028
    while pulse_time < duration - 0.05:
        width = rng.uniform(0.0045, 0.0075)
        strength = rng.uniform(0.55, 1.0)
        pulse_envelope += strength * gaussian_burst(time, pulse_time, width)

        grain_duration = rng.uniform(0.014, 0.023)
        grain_size = max(8, int(round(grain_duration * SAMPLE_RATE)))
        source_start = rng.uniform(0.0, min(0.18, source.size / SAMPLE_RATE))
        source_rate = rng.uniform(0.55, 0.92)
        source_positions = source_start * SAMPLE_RATE + (
            np.arange(grain_size) * source_rate
        )
        grain = np.interp(
            source_positions,
            np.arange(source.size),
            source,
            left=0.0,
            right=0.0,
        )
        grain -= float(grain.mean())
        grain_rms = float(np.sqrt(np.mean(grain**2)))
        if grain_rms > 1e-7:
            grain = grain / grain_rms
            grain *= np.hanning(grain_size)
            output_start = int(round(pulse_time * SAMPLE_RATE))
            output_end = min(sample_count, output_start + grain_size)
            source_grains[output_start:output_end] += (
                strength * grain[: output_end - output_start]
            )

        click_frequency = rng.uniform(620.0, 920.0)
        click_phase = 2.0 * np.pi * click_frequency * (time - pulse_time)
        low_clicks += (
            0.10
            * strength
            * np.sin(click_phase)
            * gaussian_burst(time, pulse_time, width * 0.72)
        )
        jitter = rng.uniform(-0.010, 0.010)
        pulse_time += 1.0 / rate + jitter

    pulse_envelope = np.clip(pulse_envelope, 0.0, 1.35)
    movement = smooth_random_envelope(
        rng, sample_count, duration, 0.12, 0.68, 1.00
    )
    procedural_body = 0.62 * shell_noise + 0.38 * body_noise
    procedural_body *= pulse_envelope * movement
    source_peak = max(float(np.max(np.abs(source_grains))), 1e-9)
    procedural_peak = max(float(np.max(np.abs(procedural_body))), 1e-9)
    signal = 0.48 * source_grains / source_peak
    signal += 0.34 * procedural_body / procedural_peak
    signal += 0.05 * low_clicks
    signal *= edge_envelope(time, duration, 0.045, min(0.20, duration * 0.22))
    return normalize(signal, peak=0.42)


def write_wav(path: Path, signal: np.ndarray) -> None:
    pcm = np.asarray(np.clip(signal, -1.0, 1.0) * 32767.0, dtype="<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())


def encode_ogg(ffmpeg: str, wav_path: Path, output_path: Path) -> None:
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(wav_path),
            "-map_metadata",
            "-1",
            "-fflags",
            "+bitexact",
            "-flags:a",
            "+bitexact",
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "libvorbis",
            "-q:a",
            "5",
            str(output_path),
        ],
        check=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--minecraft-assets-root",
        type=Path,
        required=True,
        help="Minecraft Java assets directory containing objects/",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to encode Vorbis OGG files")

    with tempfile.TemporaryDirectory(prefix="naga_sound_build_") as temp_dir:
        temp_root = Path(temp_dir)
        for name, (duration, seed, kind, variant) in SPECS.items():
            if kind == "hurt":
                source_path = minecraft_hurt_source_path(
                    args.minecraft_assets_root,
                    variant,
                )
                source = decode_ogg(ffmpeg, source_path)
                signal = transform_minecraft_hurt(
                    source,
                    duration,
                    seed,
                    variant,
                )
            elif kind == "rattle":
                source_path = minecraft_rattle_source_path(
                    args.minecraft_assets_root,
                    variant,
                )
                source = decode_ogg(ffmpeg, source_path)
                signal = transform_minecraft_rattle(
                    source,
                    duration,
                    seed,
                    variant,
                )
            else:
                signal = generate_hiss(duration, seed, variant)
            wav_path = temp_root / (Path(name).stem + ".wav")
            write_wav(wav_path, signal)
            encode_ogg(ffmpeg, wav_path, args.output_root / name)
            print(args.output_root / name)


if __name__ == "__main__":
    main()
