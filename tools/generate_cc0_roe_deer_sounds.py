#!/usr/bin/env python3
"""Generate six deer sounds from a pinned CC0 roe-deer field recording."""

from __future__ import annotations

import argparse
import hashlib
import math
import shutil
import tempfile
from pathlib import Path

import numpy as np

try:
    from tools import generate_original_naga_sounds as audio
except ModuleNotFoundError:  # Direct execution places tools/ on sys.path.
    import generate_original_naga_sounds as audio


SAMPLE_RATE = audio.SAMPLE_RATE
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_AUDIO = (
    ROOT
    / "tools"
    / "audio_sources"
    / "deer"
    / "roe_deer_calls_forest_of_saou_724578_hq.mp3"
)
SOURCE_SHA256 = "ae5294dc9aa810abb03f1e9b6680488a18ea3b06226b7fc17ba75db4d8ec5b1b"
SPECS = {
    "idle1.ogg": (20.6, 1.8, 1.30, "idle", 0),
    "idle2.ogg": (29.0, 1.8, 1.30, "idle", 1),
    "idle3.ogg": (61.6, 1.8, 1.18, "idle", 2),
    "hurt1.ogg": (37.5, 1.8, 0.72, "hurt", 0),
    "hurt2.ogg": (29.0, 1.8, 0.70, "hurt", 1),
    "death.ogg": (20.4, 2.0, 1.42, "death", 0),
}
PLAYBACK_RATES = {
    "idle": (0.96, 1.02, 0.92),
    "hurt": (1.08, 1.00),
    "death": (0.84,),
}


def verify_source(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"CC0 roe-deer source is missing: {path}")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != SOURCE_SHA256:
        raise ValueError(
            "CC0 roe-deer source hash mismatch: "
            f"expected {SOURCE_SHA256}, got {actual}"
        )


def decode_source(path: Path) -> np.ndarray:
    verify_source(path)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required to decode the CC0 field recording")
    return audio.decode_ogg(ffmpeg, path)


def extract_segment(
    source: np.ndarray,
    start_seconds: float,
    duration_seconds: float,
) -> np.ndarray:
    start = int(round(start_seconds * SAMPLE_RATE))
    size = int(round(duration_seconds * SAMPLE_RATE))
    end = min(source.size, start + size)
    if start < 0 or end <= start:
        raise ValueError("deer source segment is outside the recording")
    result = np.zeros(size, dtype=np.float64)
    available = np.asarray(source[start:end], dtype=np.float64)
    result[: available.size] = available
    return result


def _stft(signal: np.ndarray) -> tuple[np.ndarray, np.ndarray, int]:
    frame_size = 1024
    hop_size = 256
    frame_count = max(1, int(math.ceil((signal.size - frame_size) / hop_size)) + 1)
    padded_size = (frame_count - 1) * hop_size + frame_size
    padded = np.pad(signal, (0, max(0, padded_size - signal.size)))
    window = np.hanning(frame_size)
    frames = np.stack(
        [
            padded[index * hop_size : index * hop_size + frame_size] * window
            for index in range(frame_count)
        ]
    )
    return np.fft.rfft(frames, axis=1), window, hop_size


def _istft(
    spectrum: np.ndarray,
    window: np.ndarray,
    hop_size: int,
    output_size: int,
) -> np.ndarray:
    frame_size = window.size
    padded_size = (spectrum.shape[0] - 1) * hop_size + frame_size
    output = np.zeros(padded_size)
    normalizer = np.zeros(padded_size)
    frames = np.fft.irfft(spectrum, n=frame_size, axis=1)
    for index, frame in enumerate(frames):
        start = index * hop_size
        output[start : start + frame_size] += frame * window
        normalizer[start : start + frame_size] += window**2
    valid = normalizer > 1e-8
    output[valid] /= normalizer[valid]
    return output[:output_size]


def reduce_field_noise(signal: np.ndarray, kind: str) -> np.ndarray:
    source = np.asarray(signal, dtype=np.float64)
    source -= float(source.mean())
    spectrum, window, hop_size = _stft(source)
    magnitude = np.abs(spectrum)
    noise_profile = np.percentile(magnitude, 22.0, axis=0)
    oversubtraction = 1.45 if kind == "idle" else 1.32
    gain = 1.0 - oversubtraction * noise_profile[None, :] / (magnitude + 1e-9)
    gain = np.clip(gain, 0.10, 1.0)

    # Smooth the gain in time to avoid watery musical-noise artifacts.
    for index in range(1, gain.shape[0]):
        gain[index] = 0.58 * gain[index - 1] + 0.42 * gain[index]

    frequencies = np.fft.rfftfreq(window.size, 1.0 / SAMPLE_RATE)
    high_pass = 1.0 - np.exp(-((frequencies / 125.0) ** 4))
    low_pass = 1.0 / (1.0 + (frequencies / 5_200.0) ** 10)
    cleaned = _istft(
        spectrum * gain * high_pass[None, :] * low_pass[None, :],
        window,
        hop_size,
        source.size,
    )

    # A slow activity gate lowers forest ambience between calls while keeping
    # the actual animal waveform intact.
    envelope_size = max(3, int(SAMPLE_RATE * 0.030))
    envelope_window = np.ones(envelope_size) / envelope_size
    envelope = np.sqrt(
        np.convolve(cleaned**2, envelope_window, mode="same") + 1e-12
    )
    noise_floor = float(np.percentile(envelope, 18.0))
    call_level = float(np.percentile(envelope, 88.0))
    activity = np.clip(
        (envelope - noise_floor) / max(call_level - noise_floor, 1e-9),
        0.0,
        1.0,
    )
    gate_floor = 0.18 if kind == "idle" else 0.12
    gate = gate_floor + (1.0 - gate_floor) * np.sqrt(activity)
    return cleaned * gate


def _activity_window(
    signal: np.ndarray,
    size: int,
    kind: str,
) -> np.ndarray:
    size = min(size, signal.size)
    envelope_size = max(3, int(SAMPLE_RATE * 0.025))
    envelope_window = np.ones(envelope_size) / envelope_size
    envelope = np.convolve(signal**2, envelope_window, mode="same")
    peak_index = int(np.argmax(envelope))
    pre_fraction = 0.30 if kind == "idle" else 0.18 if kind == "hurt" else 0.24
    start = peak_index - int(round(size * pre_fraction))
    start = max(0, min(start, signal.size - size))
    return np.asarray(signal[start : start + size], dtype=np.float64)


def build_deer_sound(
    raw_segment: np.ndarray,
    output_duration: float,
    kind: str,
    variant: int,
) -> np.ndarray:
    cleaned = reduce_field_noise(raw_segment, kind)
    playback_rate = PLAYBACK_RATES[kind][variant]
    output_size = int(round(output_duration * SAMPLE_RATE))
    needed_source_size = min(
        cleaned.size,
        int(math.ceil(output_size * playback_rate)) + 2,
    )
    active = _activity_window(cleaned, needed_source_size, kind)
    positions = np.arange(output_size) * playback_rate
    resampled = np.interp(
        positions,
        np.arange(active.size),
        active,
        left=0.0,
        right=0.0,
    )

    time = np.arange(output_size) / SAMPLE_RATE
    attack_seconds = 0.008 if kind == "idle" else 0.0035
    release_seconds = 0.14 if kind == "idle" else 0.085 if kind == "hurt" else 0.20
    envelope = audio.edge_envelope(
        time,
        output_duration,
        attack_seconds,
        release_seconds,
    )
    peak = 0.49 if kind == "idle" else 0.54 if kind == "hurt" else 0.52
    return audio.normalize(resampled * envelope, peak=peak)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument(
        "--source-audio",
        type=Path,
        default=DEFAULT_SOURCE_AUDIO,
        help="Pinned CC0 Roe Deer calls Forest of Saou HQ preview",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output_root.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit("ffmpeg is required to encode Vorbis OGG files")
    source = decode_source(args.source_audio)

    with tempfile.TemporaryDirectory(prefix="roe_deer_sound_build_") as temp_dir:
        temp_root = Path(temp_dir)
        for name, (start, source_duration, output_duration, kind, variant) in SPECS.items():
            raw_segment = extract_segment(source, start, source_duration)
            signal = build_deer_sound(
                raw_segment,
                output_duration,
                kind,
                variant,
            )
            wav_path = temp_root / (Path(name).stem + ".wav")
            audio.write_wav(wav_path, signal)
            audio.encode_ogg(ffmpeg, wav_path, args.output_root / name)
            print(args.output_root / name)


if __name__ == "__main__":
    main()
