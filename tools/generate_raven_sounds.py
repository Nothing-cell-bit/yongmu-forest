"""Generate Raven sounds from pinned CC0 and public-domain corvid recordings."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np


SAMPLE_RATE = 44_100
SOURCE_SHA256 = {
    "cc0_crow_caw.wav": "bba22883209b435905471d057160f1badae59b89a62e9a8b3199d7e327b17339",
    "public_domain_hooded_crow.ogg": "16026c1a65e185bdee21c95f341c306d3687ebf2d4660e7ff2fcaa2538396098",
}
OUTPUT_SPECS = {
    "caw1.ogg": (0.50, "caw", 0),
    "caw2.ogg": (0.56, "caw", 1),
    "squawk1.ogg": (0.62, "squawk", 0),
    "squawk2.ogg": (0.70, "squawk", 1),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode(ffmpeg: str, path: Path) -> np.ndarray:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)


def band_limit(signal: np.ndarray, low_hz: float, high_hz: float) -> np.ndarray:
    spectrum = np.fft.rfft(signal)
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / SAMPLE_RATE)
    low_start = max(0.0, low_hz * 0.45)
    low_ramp = np.clip((frequencies - low_start) / max(low_hz - low_start, 1.0), 0.0, 1.0)
    high_ramp = np.clip((high_hz - frequencies) / max(high_hz * 0.16, 1.0), 0.0, 1.0)
    mask = (0.5 - 0.5 * np.cos(np.pi * low_ramp)) * (0.5 - 0.5 * np.cos(np.pi * high_ramp))
    mask[frequencies > high_hz] = 0.0
    return np.fft.irfft(spectrum * mask, n=signal.size)


def envelope(size: int, attack: float, release: float) -> np.ndarray:
    result = np.ones(size, dtype=np.float64)
    attack_size = min(size, max(1, round(attack * SAMPLE_RATE)))
    release_size = min(size, max(1, round(release * SAMPLE_RATE)))
    result[:attack_size] *= np.linspace(0.0, 1.0, attack_size)
    result[-release_size:] *= np.linspace(1.0, 0.0, release_size)
    return result


def normalize(signal: np.ndarray, peak: float) -> np.ndarray:
    shaped = np.tanh(signal * 1.08)
    current = float(np.max(np.abs(shaped)))
    return shaped if current <= 1e-9 else shaped * peak / current


def split_calls(signal: np.ndarray) -> list[np.ndarray]:
    window = round(0.008 * SAMPLE_RATE)
    activity = np.convolve(np.abs(signal), np.ones(window) / window, mode="same")
    active = np.flatnonzero(activity >= max(float(activity.max()) * 0.08, 1e-5))
    if not active.size:
        return [signal]
    gaps = np.flatnonzero(np.diff(active) > round(0.15 * SAMPLE_RATE))
    starts = np.r_[0, gaps + 1]
    ends = np.r_[gaps + 1, active.size]
    padding = round(0.016 * SAMPLE_RATE)
    result = []
    for start, end in zip(starts, ends):
        left = max(0, int(active[start]) - padding)
        right = min(signal.size, int(active[end - 1]) + padding + 1)
        if right - left >= round(0.05 * SAMPLE_RATE):
            result.append(signal[left:right])
    return result or [signal]


def fit(signal: np.ndarray, duration: float, rate: float) -> np.ndarray:
    stretched = np.interp(
        np.linspace(0.0, signal.size - 1.0, max(1, round(signal.size / rate))),
        np.arange(signal.size),
        signal,
    )
    target_size = round(duration * SAMPLE_RATE)
    if stretched.size >= target_size:
        result = stretched[:target_size]
    else:
        result = np.zeros(target_size, dtype=np.float64)
        result[: stretched.size] = stretched
    result = band_limit(result, 220.0, 9_500.0)
    result *= envelope(target_size, min(0.004, duration * 0.08), min(0.035, duration * 0.15))
    return result


def place(target: np.ndarray, source: np.ndarray, start: float, gain: float) -> None:
    left = max(0, round(start * SAMPLE_RATE))
    right = min(target.size, left + source.size)
    if right > left:
        target[left:right] += source[: right - left] * gain


def build_caw(crow_caw: np.ndarray, hooded_crow: np.ndarray, duration: float, variant: int) -> np.ndarray:
    target = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    if variant == 0:
        main = fit(crow_caw, duration * 0.98, 1.06)
    else:
        source = hooded_crow[int(1.82 * SAMPLE_RATE) : int(2.52 * SAMPLE_RATE)]
        main = band_limit(fit(source, duration * 0.98, 1.12), 260.0, 7_800.0)
    place(target, main, 0.012, (0.92, 0.82)[variant])
    return normalize(target, 0.43)


def build_squawk(hooded_crow: np.ndarray, duration: float, variant: int) -> np.ndarray:
    target = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    if variant == 0:
        source = hooded_crow[int(0.84 * SAMPLE_RATE) : int(1.55 * SAMPLE_RATE)]
        main = band_limit(fit(source, duration * 0.98, 1.05), 220.0, 8_800.0)
    else:
        source = hooded_crow[int(2.78 * SAMPLE_RATE) : int(3.56 * SAMPLE_RATE)]
        main = band_limit(fit(source, duration * 0.98, 1.12), 180.0, 6_900.0)
    place(target, main, 0.008, (0.88, 0.84)[variant])
    return normalize(target, 0.46)


def write_wav(path: Path, signal: np.ndarray) -> None:
    pcm = np.asarray(np.clip(signal, -1.0, 1.0) * 32767.0, dtype="<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())


def encode_ogg(ffmpeg: str, wav_path: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav_path), "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:a", "+bitexact", "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "libvorbis", "-q:a", "5", str(output_path)], check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to build Raven OGG files")
    sources = {}
    for filename, expected_hash in SOURCE_SHA256.items():
        path = args.source_root / filename
        if not path.is_file():
            raise SystemExit("missing pinned raven source: %s" % path)
        if sha256(path) != expected_hash:
            raise SystemExit("raven source hash mismatch: %s" % filename)
        sources[filename] = decode(ffmpeg, path)
    crow_caw = sources["cc0_crow_caw.wav"]
    hooded_crow = sources["public_domain_hooded_crow.ogg"]

    with tempfile.TemporaryDirectory(prefix="raven_public_domain_build_") as temp_dir:
        temp_root = Path(temp_dir)
        for filename, (duration, role, variant) in OUTPUT_SPECS.items():
            if role == "caw":
                signal = build_caw(crow_caw, hooded_crow, duration, variant)
            else:
                signal = build_squawk(hooded_crow, duration, variant)
            if signal.size != round(duration * SAMPLE_RATE):
                raise AssertionError("%s has an unexpected sample count" % filename)
            wav_path = temp_root / (Path(filename).stem + ".wav")
            write_wav(wav_path, signal)
            output_path = args.output_root / filename
            encode_ogg(ffmpeg, wav_path, output_path)
            print(output_path)


if __name__ == "__main__":
    main()
