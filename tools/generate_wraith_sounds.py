"""Generate Wraith sounds from pinned CC0 ghost voice recordings."""

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
    "cc0_ghost_breath.mp3": "4155c6cdad6120400ebebedf746786cb0ebbccb62d51f88a1d9e44862d158842",
    "cc0_ghostly_humming.ogg": "270954cff9f076c81e0a16fac391cfcd1cedf6786fcb05cfa813a955ae539678",
    "cc0_atmospheric_ghostly_loops.mp3": "0bf2b0ec840e55c8d4fe93365279853c68d3dc1bd641d59601a310ec18ffbe2f",
    "cc0_ghost_moan_growl.mp3": "f481134439aadd6afedbf68d050817d27ccb62b8c52305f7e6b96bd9ce0582f9",
}
OUTPUT_SPECS = {
    "wraith1.ogg": (1.590567, "cc0_ghostly_humming.ogg", 1.00, 2.80, 1.10, 80.0, 5_000.0, 0.32),
    "wraith2.ogg": (1.451247, "cc0_ghostly_humming.ogg", 19.85, 22.20, 1.08, 120.0, 4_600.0, 0.34),
    "wraith3.ogg": (1.845986, "cc0_ghost_moan_growl.mp3", 14.48, 16.72, 1.12, 110.0, 6_700.0, 0.38),
    "wraith4.ogg": (1.845986, "cc0_atmospheric_ghostly_loops.mp3", 6.28, 8.62, 1.16, 150.0, 6_000.0, 0.31),
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
    shaped = np.tanh(signal * 1.05)
    current = float(np.max(np.abs(shaped)))
    return shaped if current <= 1e-9 else shaped * peak / current


def fit(signal: np.ndarray, duration: float, rate: float, low_hz: float, high_hz: float) -> np.ndarray:
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
    result = band_limit(result, low_hz, high_hz)
    result *= envelope(target_size, min(0.025, duration * 0.08), min(0.12, duration * 0.18))
    return result


def build(source: np.ndarray, duration: float, start: float, end: float, rate: float, low_hz: float, high_hz: float, peak: float) -> np.ndarray:
    left = round(start * SAMPLE_RATE)
    right = min(source.size, round(end * SAMPLE_RATE))
    if right <= left:
        raise ValueError("Wraith source window is empty")
    main = fit(source[left:right], duration, rate, low_hz, high_hz)
    return normalize(main, peak)


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
        raise SystemExit("ffmpeg is required to build Wraith OGG files")
    sources = {}
    for filename, expected_hash in SOURCE_SHA256.items():
        path = args.source_root / filename
        if not path.is_file():
            raise SystemExit("missing pinned Wraith source: %s" % path)
        if sha256(path) != expected_hash:
            raise SystemExit("Wraith source hash mismatch: %s" % filename)
        sources[filename] = decode(ffmpeg, path)

    with tempfile.TemporaryDirectory(prefix="wraith_cc0_build_") as temp_dir:
        temp_root = Path(temp_dir)
        for filename, (duration, source_name, start, end, rate, low_hz, high_hz, peak) in OUTPUT_SPECS.items():
            signal = build(sources[source_name], duration, start, end, rate, low_hz, high_hz, peak)
            if signal.size != round(duration * SAMPLE_RATE):
                raise AssertionError("%s has an unexpected sample count" % filename)
            wav_path = temp_root / (Path(filename).stem + ".wav")
            write_wav(wav_path, signal)
            output_path = args.output_root / filename
            encode_ogg(ffmpeg, wav_path, output_path)
            print(output_path)


if __name__ == "__main__":
    main()
