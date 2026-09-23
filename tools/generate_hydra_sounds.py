"""Generate the Hydra warning, death and hurt sounds from the local CC0 bank."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 44_100
SOURCE_FILES = {
    "warn_main": "roar_03.ogg",
    "warn_accent": "roar_02.ogg",
    "death_main": "monster_04.ogg",
    "death_accent": "roar_03.ogg",
    "hurt_body": "hurt_05.ogg",
    "hurt1_main": "hurt_01.ogg",
    "hurt2_main": "hurt_02.ogg",
    "hurt3_main": "cough_01.ogg",
    "hurt4_main": "grunt_04.ogg",
    "growl1_main": "monster_01.ogg",
    "growl2_main": "troll_01.ogg",
    "growl3_main": "burble_01.ogg",
    "roar1_main": "roar_01.ogg",
    "roar2_main": "scream_01.ogg",
}
OUTPUT_SPECS = {
    "warn.ogg": (1.05, "warn"),
    "death.ogg": (1.90, "death"),
    "hurt1.ogg": (0.45, "hurt1"),
    "hurt2.ogg": (0.45, "hurt2"),
    "hurt3.ogg": (0.45, "hurt3"),
    "hurt4.ogg": (0.45, "hurt4"),
    "growl1.ogg": (1.20, "growl1"),
    "growl2.ogg": (1.35, "growl2"),
    "growl3.ogg": (1.50, "growl3"),
    "roar1.ogg": (1.60, "roar1"),
    "roar2.ogg": (1.80, "roar2"),
}


def decode_ogg(ffmpeg: str, path: Path) -> np.ndarray:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(path),
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-f",
            "f32le",
            "pipe:1",
        ],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)


def resample(signal: np.ndarray, sample_count: int) -> np.ndarray:
    sample_count = max(1, int(sample_count))
    if signal.size == sample_count:
        return signal.copy()
    positions = np.linspace(0.0, signal.size - 1.0, sample_count)
    return np.interp(positions, np.arange(signal.size), signal)


def fit(signal: np.ndarray, duration: float) -> np.ndarray:
    return resample(signal, round(duration * SAMPLE_RATE))


def trim_active(signal: np.ndarray, activity_ratio: float = 0.08) -> np.ndarray:
    window = max(1, round(0.01 * SAMPLE_RATE))
    envelope = np.convolve(
        np.abs(signal),
        np.ones(window) / window,
        mode="same",
    )
    threshold = max(float(np.max(envelope)) * activity_ratio, 1e-5)
    active = np.flatnonzero(envelope >= threshold)
    if not active.size:
        return signal.copy()
    padding = round(0.012 * SAMPLE_RATE)
    start = max(0, int(active[0]) - padding)
    end = min(signal.size, int(active[-1]) + padding + 1)
    return signal[start:end]


def band_limit(
    signal: np.ndarray,
    low_hz: float,
    high_hz: float,
) -> np.ndarray:
    spectrum = np.fft.rfft(signal)
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / SAMPLE_RATE)
    mask = np.ones_like(frequencies)
    low_start = max(0.0, low_hz * 0.55)
    low_ramp = np.clip((frequencies - low_start) / max(low_hz - low_start, 1.0), 0.0, 1.0)
    high_ramp = np.clip(
        (high_hz - frequencies) / max(high_hz * 0.16, 1.0),
        0.0,
        1.0,
    )
    mask *= 0.5 - 0.5 * np.cos(np.pi * low_ramp)
    mask *= 0.5 - 0.5 * np.cos(np.pi * high_ramp)
    mask[frequencies > high_hz] = 0.0
    return np.fft.irfft(spectrum * mask, n=signal.size)


def normalize(signal: np.ndarray, peak: float = 0.72) -> np.ndarray:
    maximum = float(np.max(np.abs(signal)))
    if maximum <= 1e-9:
        return signal
    return signal * (peak / maximum)


def edge_envelope(
    sample_count: int,
    attack_seconds: float,
    release_seconds: float,
) -> np.ndarray:
    envelope = np.ones(sample_count, dtype=np.float64)
    attack = min(sample_count, max(1, round(attack_seconds * SAMPLE_RATE)))
    release = min(sample_count, max(1, round(release_seconds * SAMPLE_RATE)))
    envelope[:attack] *= np.linspace(0.0, 1.0, attack)
    envelope[-release:] *= np.linspace(1.0, 0.0, release)
    return envelope


def place(target: np.ndarray, source: np.ndarray, start_seconds: float, gain: float) -> None:
    start = max(0, round(start_seconds * SAMPLE_RATE))
    end = min(target.size, start + source.size)
    if end > start:
        target[start:end] += source[: end - start] * gain


def build_warn(sources: dict[str, np.ndarray]) -> np.ndarray:
    main = band_limit(fit(trim_active(sources["warn_main"]), 0.72), 250.0, 7600.0)
    accent = band_limit(fit(trim_active(sources["warn_accent"]), 0.40), 300.0, 8200.0)
    output = np.zeros(round(1.05 * SAMPLE_RATE), dtype=np.float64)
    place(output, main, 0.015, 0.92)
    place(output, accent, 0.38, 0.42)
    time = np.arange(output.size, dtype=np.float64) / SAMPLE_RATE
    pulse = 0.82 + 0.18 * np.sin(2.0 * np.pi * 2.4 * time + 0.4)
    output *= pulse * edge_envelope(output.size, 0.012, 0.14)
    return normalize(output, 0.66)


def build_death(sources: dict[str, np.ndarray]) -> np.ndarray:
    first = band_limit(fit(trim_active(sources["death_main"]), 1.18), 85.0, 6900.0)
    second = band_limit(fit(trim_active(sources["death_accent"]), 1.10), 120.0, 7600.0)
    onset = band_limit(fit(trim_active(sources["death_accent"]), 0.28), 180.0, 8200.0)
    output = np.zeros(round(1.90 * SAMPLE_RATE), dtype=np.float64)
    place(output, onset, 0.012, 0.28)
    place(output, first, 0.040, 0.88)
    place(output, second, 0.72, 0.62)
    time = np.arange(output.size, dtype=np.float64) / SAMPLE_RATE
    descent = 1.0 - 0.20 * np.clip((time - 0.18) / 1.72, 0.0, 1.0)
    output *= descent * edge_envelope(output.size, 0.012, 0.11)
    return normalize(output, 0.72)


def build_hurt(
    sources: dict[str, np.ndarray],
    variant: str,
) -> np.ndarray:
    main = band_limit(
        fit(
            trim_active(sources[variant + "_main"]),
            0.36,
        ),
        150.0,
        6800.0,
    )
    body = band_limit(fit(trim_active(sources["hurt_body"]), 0.24), 140.0, 2600.0)
    output = np.zeros(round(0.45 * SAMPLE_RATE), dtype=np.float64)
    place(output, main, 0.008, 0.78)
    place(output, body, 0.014, 0.24)
    output *= edge_envelope(output.size, 0.006, 0.055)
    return normalize(output, 0.64)


def build_call(
    sources: dict[str, np.ndarray],
    variant: str,
    duration: float,
) -> np.ndarray:
    """Shape a distinct growl or roar from the local non-upstream source bank."""
    is_roar = variant.startswith("roar")
    main = band_limit(
        fit(trim_active(sources[variant + "_main"]), duration * 0.86),
        75.0 if is_roar else 95.0,
        7_600.0 if is_roar else 5_400.0,
    )
    body = band_limit(
        fit(trim_active(sources["hurt_body"]), duration * 0.62),
        70.0,
        2_200.0,
    )
    output = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    place(output, main, 0.012, 0.92)
    place(output, body, duration * 0.16, 0.18 if is_roar else 0.28)
    time = np.arange(output.size, dtype=np.float64) / SAMPLE_RATE
    pulse_rate = 2.1 if is_roar else 3.4
    output *= (0.84 + 0.16 * np.sin(2.0 * np.pi * pulse_rate * time + 0.35))
    output *= edge_envelope(output.size, 0.014, 0.13 if is_roar else 0.10)
    return normalize(output, 0.70 if is_roar else 0.62)


def write_wav(path: Path, signal: np.ndarray) -> None:
    pcm = np.asarray(np.clip(signal, -1.0, 1.0) * 32767.0, dtype="<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())


def encode_ogg(ffmpeg: str, wav_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
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
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to build Hydra OGG files")
    for source_name in SOURCE_FILES.values():
        source_path = args.source_root / source_name
        if not source_path.is_file():
            raise SystemExit("missing Hydra source: %s" % source_path)
    with tempfile.TemporaryDirectory(prefix="hydra_sound_build_") as temp_dir:
        temp_root = Path(temp_dir)
        sources = {
            key: decode_ogg(ffmpeg, args.source_root / filename)
            for key, filename in SOURCE_FILES.items()
        }
        builders = {
            "warn": build_warn,
            "death": build_death,
        }
        for filename, (duration, kind) in OUTPUT_SPECS.items():
            if kind.startswith("hurt"):
                signal = build_hurt(sources, kind)
            elif kind.startswith("growl") or kind.startswith("roar"):
                signal = build_call(sources, kind, duration)
            else:
                signal = builders[kind](sources)
            if signal.size != round(duration * SAMPLE_RATE):
                raise AssertionError("%s has an unexpected sample count" % filename)
            wav_path = temp_root / (Path(filename).stem + ".wav")
            write_wav(wav_path, signal)
            encode_ogg(ffmpeg, wav_path, args.output_root / filename)
            print(args.output_root / filename)


if __name__ == "__main__":
    main()
