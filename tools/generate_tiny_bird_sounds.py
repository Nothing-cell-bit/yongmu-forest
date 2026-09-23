"""Generate Tiny Bird sounds from pinned CC0 field recordings.

Short chirps and hurt calls are rebuilt from separated call segments. Songs use
longer continuous windows from a second recording. The Twilight Forest Tiny
Bird recordings are not read.
"""

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
    "separated_chirps.ogg": "59e49e5bfc8f3b0dee8f925f2731af5333c5e04ec251547c664e58d0afb9f2ac",
    "phylloscopus_thiru.ogg": "474f8e7f7b186edecc3e6079d73970f3646bee975896370070c15758579e6884",
}
OUTPUT_SPECS = {
    "chirp1.ogg": (0.854603, "chirp", 0),
    "chirp2.ogg": (0.869478, "chirp", 1),
    "chirp3.ogg": (0.433560, "chirp", 2),
    "hurt1.ogg": (0.382404, "hurt", 0),
    "hurt2.ogg": (0.433469, "hurt", 1),
    "song1.ogg": (2.454785, "song", 0),
    "song2.ogg": (5.756009, "song", 1),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_ogg(ffmpeg: str, path: Path) -> np.ndarray:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)


def split_active_segments(signal: np.ndarray) -> list[np.ndarray]:
    window = max(1, round(0.008 * SAMPLE_RATE))
    envelope = np.convolve(np.abs(signal), np.ones(window) / window, mode="same")
    threshold = max(float(envelope.max()) * 0.10, 1e-5)
    active = np.flatnonzero(envelope >= threshold)
    if not active.size:
        return [signal.copy()]
    gaps = np.flatnonzero(np.diff(active) > round(0.12 * SAMPLE_RATE))
    starts = np.r_[0, gaps + 1]
    ends = np.r_[gaps + 1, active.size]
    padding = round(0.012 * SAMPLE_RATE)
    result = []
    for start, end in zip(starts, ends):
        left = max(0, int(active[start]) - padding)
        right = min(signal.size, int(active[end - 1]) + padding + 1)
        segment = signal[left:right]
        if segment.size >= round(0.035 * SAMPLE_RATE):
            result.append(segment)
    return result or [signal]


def band_limit(signal: np.ndarray, low_hz: float, high_hz: float) -> np.ndarray:
    spectrum = np.fft.rfft(signal)
    frequencies = np.fft.rfftfreq(signal.size, 1.0 / SAMPLE_RATE)
    low_start = max(0.0, low_hz * 0.45)
    low_ramp = np.clip((frequencies - low_start) / max(low_hz - low_start, 1.0), 0.0, 1.0)
    high_ramp = np.clip((high_hz - frequencies) / max(high_hz * 0.16, 1.0), 0.0, 1.0)
    mask = (0.5 - 0.5 * np.cos(np.pi * low_ramp)) * (0.5 - 0.5 * np.cos(np.pi * high_ramp))
    mask[frequencies > high_hz] = 0.0
    return np.fft.irfft(spectrum * mask, n=signal.size)


def edge_envelope(sample_count: int, attack: float, release: float) -> np.ndarray:
    result = np.ones(sample_count, dtype=np.float64)
    attack_count = min(sample_count, max(1, round(attack * SAMPLE_RATE)))
    release_count = min(sample_count, max(1, round(release * SAMPLE_RATE)))
    result[:attack_count] *= np.linspace(0.0, 1.0, attack_count)
    result[-release_count:] *= np.linspace(1.0, 0.0, release_count)
    return result


def normalize(signal: np.ndarray, peak: float) -> np.ndarray:
    shaped = np.tanh(signal * 1.08)
    current_peak = float(np.max(np.abs(shaped)))
    return shaped if current_peak <= 1e-9 else shaped * (peak / current_peak)


def fit(signal: np.ndarray, sample_count: int) -> np.ndarray:
    if signal.size == sample_count:
        return signal.copy()
    return np.interp(np.linspace(0.0, signal.size - 1.0, sample_count), np.arange(signal.size), signal)


def place(target: np.ndarray, source: np.ndarray, start: float, gain: float) -> None:
    start_index = max(0, round(start * SAMPLE_RATE))
    end_index = min(target.size, start_index + source.size)
    if end_index > start_index:
        target[start_index:end_index] += source[: end_index - start_index] * gain


def build_chirp(segments: list[np.ndarray], duration: float, variant: int) -> np.ndarray:
    target = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    count = 4 if variant != 2 else 2
    gap = (0.08, 0.10, 0.07)[variant]
    cursor = 0.025
    for index in range(count):
        segment = segments[(variant * 5 + index * 7) % len(segments)]
        call_duration = (0.13, 0.16, 0.12)[variant]
        call = fit(segment, round(call_duration * SAMPLE_RATE))
        call = band_limit(call, 900.0 + variant * 120.0, 11_000.0)
        call *= edge_envelope(call.size, 0.004, 0.028)
        place(target, call, cursor, (0.72, 0.66, 0.76)[variant])
        cursor += call_duration + gap
    return normalize(target, 0.43)


def build_hurt(segments: list[np.ndarray], duration: float, variant: int) -> np.ndarray:
    target = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    first = fit(segments[(variant + 11) % len(segments)], round(0.16 * SAMPLE_RATE))
    first = band_limit(first, 1_000.0 + variant * 150.0, 10_500.0)
    first *= edge_envelope(first.size, 0.002, 0.035)
    place(target, first, 0.006, 0.78)
    if variant == 1:
        second = fit(segments[(variant + 19) % len(segments)], round(0.10 * SAMPLE_RATE))
        second = band_limit(second, 1_200.0, 9_500.0)
        second *= edge_envelope(second.size, 0.002, 0.025)
        place(target, second, 0.19, 0.18)
    return normalize(target, 0.38)


def build_song(source: np.ndarray, duration: float, variant: int) -> np.ndarray:
    windows = ((20.33, 22.41), (23.44, 27.18))
    start, end = windows[variant]
    source_slice = source[round(start * SAMPLE_RATE) : round(end * SAMPLE_RATE)]
    target = fit(source_slice, round(duration * SAMPLE_RATE))
    target = band_limit(target, 700.0 if variant == 0 else 520.0, 11_500.0)
    target *= edge_envelope(target.size, 0.012, min(0.15, duration * 0.14))
    return normalize(target, 0.40)


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
        raise SystemExit("ffmpeg is required to build Tiny Bird OGG files")

    source_arrays = {}
    for filename, expected_hash in SOURCE_SHA256.items():
        path = args.source_root / filename
        if not path.is_file():
            raise SystemExit("missing pinned CC0 bird source: %s" % path)
        if sha256(path) != expected_hash:
            raise SystemExit("CC0 bird source hash mismatch: %s" % filename)
        source_arrays[filename] = decode_ogg(ffmpeg, path)
    chirp_segments = split_active_segments(source_arrays["separated_chirps.ogg"])
    song_source = source_arrays["phylloscopus_thiru.ogg"]

    with tempfile.TemporaryDirectory(prefix="tiny_bird_cc0_build_") as temp_dir:
        temp_root = Path(temp_dir)
        for filename, (duration, role, variant) in OUTPUT_SPECS.items():
            if role == "chirp":
                signal = build_chirp(chirp_segments, duration, variant)
            elif role == "hurt":
                signal = build_hurt(chirp_segments, duration, variant)
            else:
                signal = build_song(song_source, duration, variant)
            if signal.size != round(duration * SAMPLE_RATE):
                raise AssertionError("%s has an unexpected sample count" % filename)
            wav_path = temp_root / (Path(filename).stem + ".wav")
            write_wav(wav_path, signal)
            output_path = args.output_root / filename
            encode_ogg(ffmpeg, wav_path, output_path)
            print(output_path)


if __name__ == "__main__":
    main()
