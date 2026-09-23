"""Generate the hostile wolf sound bank from pinned Minecraft wolf sounds.

The source clips are Mojang Minecraft Java 1.20.1 wolf sounds. Outputs are
constructed from trimmed wolf calls with bounded speed, reversal, filtering
and role-specific envelopes; no Twilight Forest Mist Wolf recording is read.
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
SOURCE_OBJECTS = {
    "minecraft/sounds/mob/wolf/bark1.ogg": "2452c64a55eaef86bf1b668bb4d5f3b641cd8f25",
    "minecraft/sounds/mob/wolf/bark2.ogg": "9f1708a6409d04370ec12d0add015b11abbd5371",
    "minecraft/sounds/mob/wolf/growl1.ogg": "0b29f5ce8c4c10fa4184e5d29244f3bc121468a0",
    "minecraft/sounds/mob/wolf/howl1.ogg": "84556bac99c01ad006552cf5d96494817e9b1700",
    "minecraft/sounds/mob/wolf/howl2.ogg": "cdb0293c5e2bdbda21798af4e61a4c171c8b1ec0",
    "minecraft/sounds/mob/wolf/hurt1.ogg": "71b5fc7aa050892f8c9a9ed2713cc1ad8874742a",
    "minecraft/sounds/mob/wolf/hurt2.ogg": "bc2f6a5a1b6646eac1681b7414b098089aedf3c6",
    "minecraft/sounds/mob/wolf/whine.ogg": "fcf4f90c452b7b511d50e3959ae05036d13a7cf8",
}
OUTPUT_SPECS = {
    "idle1.ogg": (3.842902, "idle", 0),
    "idle2.ogg": (3.349478, "idle", 1),
    "idle3.ogg": (3.808073, "idle", 2),
    "hurt1.ogg": (0.737007, "hurt", 0),
    "hurt2.ogg": (0.662834, "hurt", 1),
    "target.ogg": (3.878662, "target", 0),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode_ogg(ffmpeg: str, path: Path) -> np.ndarray:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"],
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


def split_active_segments(signal: np.ndarray) -> list[np.ndarray]:
    window = max(1, round(0.008 * SAMPLE_RATE))
    envelope = np.convolve(np.abs(signal), np.ones(window) / window, mode="same")
    threshold = max(float(envelope.max()) * 0.045, 1e-5)
    active = np.flatnonzero(envelope >= threshold)
    if not active.size:
        return [signal.copy()]
    gaps = np.flatnonzero(np.diff(active) > round(0.075 * SAMPLE_RATE))
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
    shaped = np.tanh(signal * 1.12)
    current_peak = float(np.max(np.abs(shaped)))
    return shaped if current_peak <= 1e-9 else shaped * (peak / current_peak)


def render_bark(source: np.ndarray, max_duration: float, rate: float, reverse: bool, low_hz: float, high_hz: float) -> np.ndarray:
    active = source[::-1] if reverse else source
    played = resample(active, round(active.size / rate))
    played = played[: round(max_duration * SAMPLE_RATE)]
    if not played.size:
        return np.zeros(1, dtype=np.float64)
    played = band_limit(played, low_hz, high_hz)
    played *= edge_envelope(played.size, min(0.004, max_duration * 0.08), min(0.032, max_duration * 0.16))
    return played


def place(target: np.ndarray, source: np.ndarray, start: float, gain: float) -> None:
    start_index = max(0, round(start * SAMPLE_RATE))
    end_index = min(target.size, start_index + source.size)
    if end_index > start_index:
        target[start_index:end_index] += source[: end_index - start_index] * gain


def build_idle(source_bank: list[np.ndarray], duration: float, seed: int, variant: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    output = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    # One idle file carries one complete vanilla wolf call. Do not concatenate
    # several barks: the long howl contour is the recognizable wolf identity.
    idle_sources = (3, 4, 3)
    rates = (0.94, 1.10, 0.97)
    source = source_bank[idle_sources[variant % len(idle_sources)]]
    bark = render_bark(source, duration, rates[variant % len(rates)], False, 95.0, 8_200.0)
    place(output, bark, 0.0, rng.uniform(0.82, 0.90))
    return normalize(output, 0.41)


def build_hurt(source_bank: list[np.ndarray], duration: float, seed: int, variant: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    output = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    hurt_sources = (5, 6, 7)
    bark = render_bark(source_bank[hurt_sources[variant % len(hurt_sources)]], 0.30, rng.uniform(1.35, 1.85), variant == 1, 110.0, rng.uniform(5_800.0, 7_800.0))
    place(output, bark, 0.004, 0.90)
    tail = render_bark(source_bank[hurt_sources[(variant + 1) % len(hurt_sources)]], 0.16, 2.05, False, 120.0, 5_600.0)
    place(output, tail, 0.17, 0.14)
    return normalize(output, 0.62)


def build_target(source_bank: list[np.ndarray], duration: float, seed: int, variant: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    output = np.zeros(round(duration * SAMPLE_RATE), dtype=np.float64)
    count = 6
    centers = np.linspace(0.07, 0.70, count) * duration
    target_sources = (0, 1, 2, 3)
    for index, center in enumerate(centers):
        bark = render_bark(source_bank[target_sources[index % len(target_sources)]], rng.uniform(0.18, 0.30), rng.uniform(1.5, 2.25), False, 115.0, rng.uniform(6_800.0, 9_000.0))
        place(output, bark, center, rng.uniform(0.66, 0.86))
    return normalize(output, 0.60)


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
    parser.add_argument("--minecraft-assets-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to build hostile wolf OGG files")
    source_bank = []
    for logical_path, expected_sha1 in SOURCE_OBJECTS.items():
        source_path = args.minecraft_assets_root / "objects" / expected_sha1[:2] / expected_sha1
        if not source_path.is_file():
            raise SystemExit("missing Minecraft source object: %s" % logical_path)
        actual_sha1 = hashlib.sha1(source_path.read_bytes()).hexdigest()
        if actual_sha1 != expected_sha1:
            raise SystemExit("Minecraft source SHA-1 mismatch: %s" % logical_path)
        source_bank.append(decode_ogg(ffmpeg, source_path))
    if len(source_bank) < 8:
        raise SystemExit("Minecraft wolf source bank is unexpectedly small")

    with tempfile.TemporaryDirectory(prefix="hostile_wolf_dog_build_") as temp_dir:
        temp_root = Path(temp_dir)
        for index, (filename, (duration, role, variant)) in enumerate(OUTPUT_SPECS.items()):
            seed = 20_260_903 + index * 101 + variant
            if role == "idle":
                signal = build_idle(source_bank, duration, seed, variant)
            elif role == "hurt":
                signal = build_hurt(source_bank, duration, seed, variant)
            else:
                signal = build_target(source_bank, duration, seed, variant)
            wav_path = temp_root / (Path(filename).stem + ".wav")
            write_wav(wav_path, signal)
            output_path = args.output_root / filename
            encode_ogg(ffmpeg, wav_path, output_path)
            print(output_path)


if __name__ == "__main__":
    main()
