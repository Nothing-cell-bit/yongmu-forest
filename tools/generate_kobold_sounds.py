"""Generate a dog-inspired Kobold sound bank from pinned canine recordings.

The source clips are canine barks, not Twilight Forest assets. Outputs are
constructed from trimmed bark phrases with bounded speed, reversal, filtering
and role-specific envelopes; no upstream Kobold recording is read.
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
    "barking_of_a_dog.ogg": "e4438897b68360e54c9e9319a8aea14a78527f022c2b78086f4b2348c03b2fa1",
    "barking_of_a_dog_2.ogg": "d4e62e278cc0d7c9e502b7cb0041cdffb2b2dde31f1dba1016bb9f3866c03c27",
}
OUTPUT_SPECS = {
    "ambient1.ogg": (0.92, "ambient", 0),
    "ambient2.ogg": (1.04, "ambient", 1),
    "ambient3.ogg": (1.00, "ambient", 2),
    "ambient4.ogg": (0.52, "ambient", 3),
    "ambient5.ogg": (0.59, "ambient", 4),
    "ambient6.ogg": (0.53, "ambient", 5),
    "death1.ogg": (0.92, "death", 0),
    "death2.ogg": (1.18, "death", 1),
    "death3.ogg": (1.16, "death", 2),
    "hurt1.ogg": (0.48, "hurt", 0),
    "hurt2.ogg": (0.52, "hurt", 1),
    "hurt3.ogg": (0.44, "hurt", 2),
    "shorfle.ogg": (0.58, "shorfle", 0),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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


def trim_active(signal: np.ndarray) -> np.ndarray:
    window = max(1, round(0.008 * SAMPLE_RATE))
    envelope = np.convolve(np.abs(signal), np.ones(window) / window, mode="same")
    threshold = max(float(envelope.max()) * 0.045, 1e-5)
    active = np.flatnonzero(envelope >= threshold)
    if not active.size:
        return signal.copy()
    padding = round(0.010 * SAMPLE_RATE)
    return signal[max(0, active[0] - padding) : min(signal.size, active[-1] + padding + 1)]


def split_active_segments(signal: np.ndarray) -> list[np.ndarray]:
    """Split a multi-bark recording at genuine quiet gaps."""
    window = max(1, round(0.008 * SAMPLE_RATE))
    envelope = np.convolve(np.abs(signal), np.ones(window) / window, mode="same")
    threshold = max(float(envelope.max()) * 0.045, 1e-5)
    active = np.flatnonzero(envelope >= threshold)
    if not active.size:
        return [signal.copy()]

    gap_limit = round(0.075 * SAMPLE_RATE)
    split_points = np.flatnonzero(np.diff(active) > gap_limit)
    starts = np.r_[0, split_points + 1]
    ends = np.r_[split_points + 1, active.size]
    padding = round(0.012 * SAMPLE_RATE)
    segments = []
    for start, end in zip(starts, ends):
        left = max(0, int(active[start]) - padding)
        right = min(signal.size, int(active[end - 1]) + padding + 1)
        segment = signal[left:right]
        if segment.size >= round(0.035 * SAMPLE_RATE):
            segments.append(segment)
    return segments or [trim_active(signal)]


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
    shaped = np.tanh(signal * 1.18)
    current_peak = float(np.max(np.abs(shaped)))
    return shaped if current_peak <= 1e-9 else shaped * (peak / current_peak)


def fit_with_padding(signal: np.ndarray, sample_count: int) -> np.ndarray:
    if signal.size >= sample_count:
        return signal[:sample_count].copy()
    result = np.zeros(sample_count, dtype=np.float64)
    result[: signal.size] = signal
    return result


def render_bark(
    source: np.ndarray,
    duration: float,
    rate: float,
    reverse: bool,
    low_hz: float = 90.0,
    high_hz: float = 8_500.0,
) -> np.ndarray:
    active = trim_active(source)
    if reverse:
        active = active[::-1]
    played = resample(active, round(active.size / rate))
    max_count = round(duration * SAMPLE_RATE)
    played = played[:max_count]
    target_count = played.size
    if not target_count:
        return np.zeros(1, dtype=np.float64)
    played = band_limit(played, low_hz, high_hz)
    played *= edge_envelope(target_count, min(0.004, duration * 0.08), min(0.032, duration * 0.16))
    return played


def place(target: np.ndarray, source: np.ndarray, start: float, gain: float) -> None:
    start_index = max(0, round(start * SAMPLE_RATE))
    end_index = min(target.size, start_index + source.size)
    if end_index > start_index:
        target[start_index:end_index] += source[: end_index - start_index] * gain


def build_ambient(source_bank: list[np.ndarray], duration: float, seed: int, variant: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    output = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    count = 2 + (variant % 2)
    centers = np.linspace(0.14, 0.76, count) * duration
    for index, center in enumerate(centers):
        bark_duration = rng.uniform(0.17, 0.29)
        bark = render_bark(
            source_bank[(index + variant) % len(source_bank)],
            bark_duration,
            rng.uniform(1.25, 1.85),
            bool((index + variant) % 3 == 0),
            100.0,
            rng.uniform(6_800.0, 9_200.0),
        )
        place(output, bark, center, rng.uniform(0.74, 0.92))
    return normalize(output, 0.58)


def build_hurt(source_bank: list[np.ndarray], duration: float, seed: int, variant: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    output = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    main = render_bark(
        source_bank[variant % len(source_bank)],
        rng.uniform(0.22, 0.31),
        rng.uniform(1.30, 1.72),
        variant == 2,
        120.0,
        rng.uniform(6_400.0, 8_400.0),
    )
    place(output, main, 0.006, 0.92)
    tail = render_bark(source_bank[(variant + 1) % len(source_bank)], 0.13, 1.9, True, 150.0, 6_800.0)
    place(output, tail, 0.16 + variant * 0.012, 0.16)
    return normalize(output, 0.62)


def build_death(source_bank: list[np.ndarray], duration: float, seed: int, variant: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    output = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    first = render_bark(source_bank[variant % len(source_bank)], 0.32, rng.uniform(1.10, 1.35), False, 80.0, 7_600.0)
    second = render_bark(source_bank[(variant + 1) % len(source_bank)], 0.46, rng.uniform(0.72, 0.98), variant == 1, 70.0, 6_400.0)
    tail = render_bark(source_bank[variant % len(source_bank)], 0.42, rng.uniform(0.62, 0.84), True, 60.0, 5_800.0)
    place(output, first, 0.025, 0.78)
    place(output, second, 0.28 + variant * 0.025, 0.58)
    place(output, tail, 0.58, 0.34)
    return normalize(output, 0.66)


def build_shorfle(source_bank: list[np.ndarray], duration: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    output = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    # Shorfle is a muted snuffle, not a rapid sequence of chopped barks.
    main = render_bark(
        source_bank[0],
        0.20,
        rng.uniform(2.0, 2.8),
        False,
        140.0,
        2_600.0,
    )
    place(output, main, 0.075, 0.78)
    tail = render_bark(
        source_bank[1 % len(source_bank)],
        0.13,
        rng.uniform(2.8, 3.8),
        False,
        160.0,
        2_300.0,
    )
    place(output, tail, 0.19, 0.18)
    return normalize(output, 0.52)


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
    parser.add_argument("--source-audio", action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to build Kobold OGG files")
    if len(args.source_audio) != len(SOURCE_SHA256):
        raise SystemExit("exactly two pinned canine source clips are required")

    source_bank = []
    for source_arg, expected_hash in zip(args.source_audio, SOURCE_SHA256.values()):
        source_path = Path(source_arg)
        if not source_path.is_file():
            raise SystemExit("missing pinned canine source: %s" % source_path)
        actual_hash = sha256(source_path)
        if actual_hash != expected_hash:
            raise SystemExit("canine source hash mismatch: %s" % source_path)
        source_bank.extend(split_active_segments(decode_ogg(ffmpeg, source_path)))

    builders = {"ambient": build_ambient, "hurt": build_hurt, "death": build_death, "shorfle": build_shorfle}
    with tempfile.TemporaryDirectory(prefix="kobold_dog_source_build_") as temp_dir:
        temp_root = Path(temp_dir)
        for index, (filename, (duration, role, variant)) in enumerate(OUTPUT_SPECS.items()):
            seed = 20_260_902 + index * 101 + variant
            if role == "shorfle":
                signal = builders[role](source_bank, duration, seed)
            else:
                signal = builders[role](source_bank, duration, seed, variant)
            if signal.size != round(duration * SAMPLE_RATE):
                raise AssertionError("%s has an unexpected sample count" % filename)
            wav_path = temp_root / (Path(filename).stem + ".wav")
            write_wav(wav_path, signal)
            output_path = args.output_root / filename
            encode_ogg(ffmpeg, wav_path, output_path)
            print(output_path)


if __name__ == "__main__":
    main()
