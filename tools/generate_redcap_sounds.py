"""Generate Redcap audio without reading Twilight Forest sound assets.

Redcap ambient clips 1-5 use separate pinned CC0 laughter recordings. Ambient
clips 6-7 are synthesized deterministically from seeded noise. Hurt and death
clips use pinned Minecraft Java 1.20.1 witch and pillager vocal sources. All
file-backed outputs receive bounded time/grain processing, filtering and
envelope shaping, so no OGG is copied unchanged.
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
MINECRAFT_SOURCE_OBJECTS = {
    "minecraft/sounds/entity/witch/hurt1.ogg": "d4f9f7adb9789781a3a0ca1a94262a474cbee1db",
    "minecraft/sounds/entity/witch/hurt2.ogg": "608ce4dc409ef39df6b0409647b89f2f1a2d9ded",
    "minecraft/sounds/entity/witch/hurt3.ogg": "591bb8451ac56723d2b689d9bc95c8020bb4809b",
    "minecraft/sounds/entity/witch/death1.ogg": "627c939e2aa48a5e3f516848e66a76acb992c2a8",
    "minecraft/sounds/entity/witch/death2.ogg": "b5e67bcc0f5af24fa6d01f377215143ee7a1cf67",
    "minecraft/sounds/entity/witch/death3.ogg": "4c02a13757318403e7837260c1b30069dcb7be69",
    "minecraft/sounds/mob/pillager/hurt1.ogg": "3f2e8691d05ab35ba956159e76ad89b267bb9a9f",
    "minecraft/sounds/mob/pillager/hurt2.ogg": "977e87e9f30b5b4b35d7a8fc7355a1d891f7c2c8",
    "minecraft/sounds/mob/pillager/hurt3.ogg": "dcfac8650527f90c0ea202504497436b716ae37a",
    "minecraft/sounds/mob/pillager/death1.ogg": "12365c224970df985cce386bbcaeb357b4b85496",
    "minecraft/sounds/mob/pillager/death2.ogg": "b440f29191234eb91f36354bbf43d62dcba0973e",
}
LAUGH_SOURCE_SHA256 = {
    "sinister_laugh.ogg": "8de8e205e6ce8542609d709718a46a94388d859bef337ee0af3abdf02eb87454",
    "evil_cackle_laugh_2.ogg": "215caebb11ca96d22eea36a68e16ffcfa7479c835e3927a21fe90a7880c8bc9c",
    "evil_laugh_2.ogg": "41e69ed7eb6e0b82746429b1abbb74c16f2ff2b9aa02a3a700c3ada4563b559e",
    "witch_cackle.ogg": "6698c4f70facd5e9b4285ff34897099f70c95a826c6775ba4fba7ef5afbc4caf",
    "evil_laughter_0.ogg": "9dcf890d2ed763e71013fcca6dd885bde98cf7caac6e901bffbc531f459e0e9e",
}
OUTPUT_SPECS = {
    "redcap1.ogg": (1.277098, "ambient", 0),
    "redcap2.ogg": (1.265488, "ambient", 1),
    "redcap3.ogg": (1.288707, "ambient", 2),
    "redcap4.ogg": (1.625397, "ambient", 3),
    "redcap5.ogg": (1.416417, "ambient", 4),
    "redcap6.ogg": (1.300317, "ambient", 5),
    "redcap7.ogg": (1.750000, "easter_egg", 0),
    "hurt1.ogg": (0.743039, "hurt", 0),
    "hurt2.ogg": (1.010068, "hurt", 1),
    "hurt3.ogg": (0.917188, "hurt", 2),
    "hurt4.ogg": (0.801088, "hurt", 3),
    "die1.ogg": (1.776327, "death", 0),
    "die2.ogg": (1.799546, "death", 1),
    "die3.ogg": (1.253878, "death", 2),
}


def decode_ogg(ffmpeg: str, path: Path) -> np.ndarray:
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "f32le", "pipe:1"],
        check=True,
        stdout=subprocess.PIPE,
    )
    return np.frombuffer(result.stdout, dtype="<f4").astype(np.float64)


def trim_active(signal: np.ndarray) -> np.ndarray:
    window = max(1, round(0.008 * SAMPLE_RATE))
    envelope = np.convolve(np.abs(signal), np.ones(window) / window, mode="same")
    threshold = max(float(envelope.max()) * 0.045, 1e-5)
    active = np.flatnonzero(envelope >= threshold)
    if not active.size:
        return signal.copy()
    padding = round(0.012 * SAMPLE_RATE)
    return signal[max(0, active[0] - padding) : min(signal.size, active[-1] + padding + 1)]


def rearrange_grains(signal: np.ndarray, grain_count: int, reverse_index: int) -> np.ndarray:
    edges = np.linspace(0, signal.size, grain_count + 1, dtype=int)
    grains = [signal[edges[i] : edges[i + 1]] for i in range(grain_count) if edges[i + 1] > edges[i]]
    order = list(range(len(grains)))
    order = order[::2] + order[1::2]
    result = []
    for index in order:
        grain = grains[index]
        if index == reverse_index % len(grains):
            grain = grain[::-1]
        result.append(grain)
    return np.concatenate(result) if result else signal.copy()


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


def spectral_band(noise: np.ndarray, center_hz: float, width_hz: float) -> np.ndarray:
    spectrum = np.fft.rfft(noise)
    frequencies = np.fft.rfftfreq(noise.size, 1.0 / SAMPLE_RATE)
    curve = np.exp(-0.5 * ((frequencies - center_hz) / width_hz) ** 2)
    curve *= 1.0 - np.exp(-frequencies / 70.0)
    return np.fft.irfft(spectrum * curve, n=noise.size)


def unit_rms(signal: np.ndarray) -> np.ndarray:
    current = float(np.sqrt(np.mean(signal**2)))
    return signal if current <= 1e-9 else signal / current


def gaussian_burst(time: np.ndarray, center: float, width: float) -> np.ndarray:
    return np.exp(-0.5 * ((time - center) / width) ** 2)


def jittered_glottal(time: np.ndarray, rng: np.random.Generator, variant: int) -> np.ndarray:
    pulses = np.zeros(time.size, dtype=np.float64)
    cursor = 0.012
    while cursor < float(time[-1]):
        progress = cursor / max(float(time[-1]), 1e-9)
        frequency = 205.0 + variant * 12.0 - 45.0 * progress
        width = rng.uniform(0.0014, 0.0032)
        pulses += rng.uniform(0.45, 1.0) * gaussian_burst(time, cursor, width)
        cursor += rng.uniform(0.78, 1.22) / frequency
    return unit_rms(spectral_band(pulses, 720.0 + variant * 55.0, 720.0))


def build_procedural_laugh(duration: float, seed: int, variant: int) -> np.ndarray:
    """Synthesize an irregular goblin laugh without reading any audio file."""
    sample_count = round(duration * SAMPLE_RATE)
    time = np.arange(sample_count, dtype=np.float64) / SAMPLE_RATE
    rng = np.random.default_rng(seed)
    syllable_count = 3 + (variant % 3)
    gate = np.zeros(sample_count, dtype=np.float64)
    for index in range(syllable_count):
        center = duration * (0.16 + index * 0.18) + rng.uniform(-0.035, 0.035)
        width = rng.uniform(0.052, 0.082)
        gate += gaussian_burst(time, center, width)
    gate = np.clip(gate, 0.0, 1.0)

    low = unit_rms(spectral_band(rng.standard_normal(sample_count), 290.0 + variant * 13.0, 260.0))
    chest = unit_rms(spectral_band(rng.standard_normal(sample_count), 760.0 + variant * 45.0, 430.0))
    mouth = unit_rms(spectral_band(rng.standard_normal(sample_count), 1_720.0 + variant * 95.0, 820.0))
    breath = unit_rms(spectral_band(rng.standard_normal(sample_count), 3_800.0 + variant * 160.0, 1_650.0))
    glottal = jittered_glottal(time, rng, variant)

    syllable_shape = 0.72 + 0.28 * np.sin(
        2.0 * np.pi * (3.5 + variant * 0.25) * time + rng.uniform(0, 2 * np.pi)
    )
    signal = gate * syllable_shape * (
        0.26 * low + 0.24 * chest + 0.20 * mouth + 0.08 * breath + 0.22 * glottal
    )
    signal *= edge_envelope(sample_count, 0.018, min(0.11, duration * 0.16))
    return normalize(signal, 0.48)


def render_source(source: np.ndarray, duration: float, rate: float, grain_count: int, reverse_index: int, low_hz: float, high_hz: float) -> np.ndarray:
    active = rearrange_grains(trim_active(source), grain_count, reverse_index)
    played = resample(active, round(active.size / rate))
    target_count = round(duration * SAMPLE_RATE)
    if played.size >= target_count:
        played = played[:target_count]
    else:
        padded = np.zeros(target_count, dtype=np.float64)
        padded[: played.size] = played
        played = padded
    played = band_limit(played, low_hz, high_hz)
    played *= edge_envelope(target_count, min(0.006, duration * 0.08), min(0.055, duration * 0.18))
    return played


def render_laugh_source(source: np.ndarray, duration: float, rate: float, low_hz: float, high_hz: float) -> np.ndarray:
    """Keep the complete laugh contour while applying only a small time warp."""
    active = trim_active(source)
    warped = resample(active, round(active.size * rate))
    target_count = round(duration * SAMPLE_RATE)
    played = resample(warped, target_count)
    played = band_limit(played, low_hz, high_hz)
    played *= edge_envelope(target_count, min(0.006, duration * 0.08), min(0.055, duration * 0.18))
    return played


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


def resample(signal: np.ndarray, sample_count: int) -> np.ndarray:
    sample_count = max(1, int(sample_count))
    if signal.size == sample_count:
        return signal.copy()
    return np.interp(np.linspace(0.0, signal.size - 1.0, sample_count), np.arange(signal.size), signal)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--laugh-source", type=Path, action="append", required=True)
    parser.add_argument("--minecraft-assets-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to build Redcap OGG files")

    minecraft_sources = {}
    for logical_path, expected_sha1 in MINECRAFT_SOURCE_OBJECTS.items():
        source_path = args.minecraft_assets_root / "objects" / expected_sha1[:2] / expected_sha1
        if not source_path.is_file():
            raise SystemExit("missing Minecraft replacement source: %s" % logical_path)
        actual_sha1 = hashlib.sha1(source_path.read_bytes()).hexdigest()
        if actual_sha1 != expected_sha1:
            raise SystemExit("Minecraft replacement SHA-1 mismatch: %s" % logical_path)
        minecraft_sources[logical_path] = decode_ogg(ffmpeg, source_path)

    if len(args.laugh_source) != len(LAUGH_SOURCE_SHA256):
        raise SystemExit("exactly five pinned CC0 laugh sources are required")
    laugh_sources = {}
    for laugh_path, (expected_name, expected_hash) in zip(args.laugh_source, LAUGH_SOURCE_SHA256.items()):
        if laugh_path.name != expected_name:
            raise SystemExit("unexpected CC0 laugh source order: %s" % laugh_path)
        if not laugh_path.is_file():
            raise SystemExit("missing pinned CC0 laugh source: %s" % laugh_path)
        if hashlib.sha256(laugh_path.read_bytes()).hexdigest() != expected_hash:
            raise SystemExit("CC0 laugh source hash mismatch: %s" % laugh_path)
        laugh_sources[expected_name] = decode_ogg(ffmpeg, laugh_path)

    with tempfile.TemporaryDirectory(prefix="redcap_laughter_build_") as temp_dir:
        temp_root = Path(temp_dir)
        for index, (filename, (duration, role, variant)) in enumerate(OUTPUT_SPECS.items()):
            seed = 20_260_905 + index * 101 + variant
            if role == "ambient":
                if variant == 5:
                    signal = build_procedural_laugh(duration, seed, variant)
                else:
                    laugh_source = laugh_sources[list(LAUGH_SOURCE_SHA256)[variant]]
                    signal = render_laugh_source(
                        laugh_source,
                        duration,
                        (1.00, 0.98, 1.02, 0.96, 1.04)[variant],
                        120.0,
                        (6_800.0, 7_400.0, 7_900.0, 6_500.0, 7_700.0)[variant],
                    )
                signal = normalize(signal, 0.48)
            elif role == "easter_egg":
                signal = build_procedural_laugh(duration, seed, 7)
                signal = normalize(signal, 0.42)
            elif role == "hurt":
                hurt_paths = (
                    "minecraft/sounds/entity/witch/hurt1.ogg",
                    "minecraft/sounds/entity/witch/hurt2.ogg",
                    "minecraft/sounds/mob/pillager/hurt1.ogg",
                    "minecraft/sounds/mob/pillager/hurt2.ogg",
                )
                source = minecraft_sources[hurt_paths[variant]]
                signal = render_source(source, duration, (1.00, 1.04, 1.08, 1.12)[variant], 3, variant, 130.0, 6_500.0)
                signal = normalize(signal, 0.54)
            else:
                death_paths = (
                    ("minecraft/sounds/entity/witch/death1.ogg", "minecraft/sounds/mob/pillager/death1.ogg"),
                    ("minecraft/sounds/mob/pillager/death1.ogg", "minecraft/sounds/entity/witch/death2.ogg"),
                    ("minecraft/sounds/entity/witch/death3.ogg", "minecraft/sounds/mob/pillager/death2.ogg"),
                )
                source = minecraft_sources[death_paths[variant][0]]
                tail = minecraft_sources[death_paths[variant][1]]
                signal = render_source(source, duration, (0.98, 1.02, 1.06)[variant], 3, variant + 1, 90.0, 6_000.0)
                signal += 0.20 * render_source(tail, duration, (1.15, 1.20, 1.25)[variant], 2, variant, 80.0, 5_500.0)
                signal = normalize(signal, 0.58)
            wav_path = temp_root / (Path(filename).stem + ".wav")
            write_wav(wav_path, signal)
            output_path = args.output_root / filename
            encode_ogg(ffmpeg, wav_path, output_path)
            print(output_path)


if __name__ == "__main__":
    main()
