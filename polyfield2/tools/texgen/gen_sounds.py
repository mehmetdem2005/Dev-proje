"""Synthesise the sound effects.

    blender -b --python gen_sounds.py

These are generated rather than downloaded, which is a deviation from the
"download real assets" rule and worth stating plainly. No CC0 game-audio
library turned out to be reachable from here without an API key: Wikimedia
Commons has almost no usable weapon audio, what it does have is CC-BY rather
than public domain, and its search returns people pronouncing the word
"gunshot" more often than gunshots.

Synthesis is a reasonable answer for this particular category anyway — layered
gunfire is normally built from a noise transient, a resonant body and a decay
tail rather than from a single field recording, which is exactly what this
does. Ambience and footsteps are filtered noise, which is also standard.

Output: 22.05 kHz mono 16-bit WAV, which Godot imports directly.
"""

import math
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np

OUT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "..", "game", "assets", "audio")
RATE = 22050


def write_wav(path, samples, rate=RATE):
    """16-bit mono PCM WAV."""
    data = np.clip(samples, -1.0, 1.0)
    pcm = (data * 32767.0).astype("<i2").tobytes()
    header = b"RIFF" + struct.pack("<I", 36 + len(pcm)) + b"WAVEfmt "
    header += struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(pcm))
    with open(path, "wb") as handle:
        handle.write(header + pcm)
    return len(pcm) / 2.0 / rate


def _noise(length, seed):
    return np.random.default_rng(seed).normal(0.0, 1.0, int(length * RATE))


def _envelope(length, attack, decay, power=2.0):
    n = int(length * RATE)
    t = np.linspace(0.0, length, n, endpoint=False)
    rise = np.clip(t / max(attack, 1e-5), 0.0, 1.0)
    fall = np.exp(-t / max(decay, 1e-5)) ** power
    return rise * fall


def _lowpass(signal, cutoff):
    """One-pole low-pass; enough to shape noise into a body."""
    alpha = math.exp(-2.0 * math.pi * cutoff / RATE)
    out = np.empty_like(signal)
    acc = 0.0
    for index in range(signal.size):
        acc = alpha * acc + (1.0 - alpha) * signal[index]
        out[index] = acc
    return out


def _highpass(signal, cutoff):
    return signal - _lowpass(signal, cutoff)


def _resonator(signal, frequency, decay):
    """Ring a decaying sine at `frequency`, excited by the signal's transient."""
    n = signal.size
    t = np.arange(n) / RATE
    ring = np.sin(2.0 * math.pi * frequency * t) * np.exp(-t / decay)
    # Excite with the first few milliseconds only — that is the crack.
    excite = signal[:int(0.004 * RATE)]
    return np.convolve(ring, excite, mode="full")[:n] / max(1.0, excite.size * 0.5)


def gunshot(seed, length=0.55, body_hz=190.0, brightness=4200.0, punch=1.0, tail=0.28):
    """Transient + resonant body + room tail."""
    n = int(length * RATE)
    noise = _noise(length, seed)

    crack = _highpass(noise, brightness) * _envelope(length, 0.0004, 0.012, 1.4)
    body = _lowpass(noise, body_hz * 4.0) * _envelope(length, 0.0008, 0.045, 1.1)
    ring = _resonator(crack, body_hz, 0.05)
    room = _lowpass(_noise(length, seed + 7), 1800.0) * _envelope(length, 0.010, tail, 1.6)

    mix = crack * 0.85 * punch + body * 0.60 + ring * 0.35 + room * 0.22
    mix /= max(np.abs(mix).max(), 1e-6)
    # Soft clip: gunfire is loud and a hard limit sounds like a click.
    return np.tanh(mix * 1.6) * 0.92


def footstep(seed):
    length = 0.16
    noise = _noise(length, seed)
    crunch = _highpass(noise, 900.0) * _envelope(length, 0.001, 0.030, 1.5)
    thud = _lowpass(noise, 240.0) * _envelope(length, 0.002, 0.045, 1.2)
    mix = crunch * 0.6 + thud * 0.5
    return mix / max(np.abs(mix).max(), 1e-6) * 0.5


def mech_click(seed, frequency=2600.0, length=0.09, decay=0.012):
    noise = _noise(length, seed)
    click = _highpass(noise, frequency) * _envelope(length, 0.0003, decay, 1.6)
    body = _lowpass(noise, 700.0) * _envelope(length, 0.0006, 0.018, 1.2)
    mix = click * 0.8 + body * 0.35
    return mix / max(np.abs(mix).max(), 1e-6) * 0.7


def ui_blip(length=0.10, frequency=760.0):
    t = np.linspace(0.0, length, int(length * RATE), endpoint=False)
    tone = np.sin(2.0 * math.pi * frequency * t) + 0.4 * np.sin(2.0 * math.pi * frequency * 2 * t)
    return tone * _envelope(length, 0.002, 0.030, 1.4) * 0.35


def wind_loop(seed, length=6.0):
    """Seamless highland wind: filtered noise with a slow gust envelope.

    Cross-faded with itself so the loop point is inaudible.
    """
    noise = _noise(length, seed)
    air = _lowpass(noise, 520.0)
    air = _highpass(air, 60.0)
    t = np.linspace(0.0, length, air.size, endpoint=False)
    gust = 0.55 + 0.45 * (0.6 * np.sin(t * 0.7) + 0.4 * np.sin(t * 0.23 + 1.1))
    air = air * gust
    air /= max(np.abs(air).max(), 1e-6)

    fade = int(0.75 * RATE)
    ramp = np.linspace(0.0, 1.0, fade)
    looped = air.copy()
    looped[:fade] = air[:fade] * ramp + air[-fade:] * (1.0 - ramp)
    return looped[:-fade] * 0.30


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    bank = {
        # Each weapon gets its own body frequency and brightness so they are
        # distinguishable by ear alone.
        "fire_rifle": gunshot(11, 0.60, body_hz=165.0, brightness=3800.0, punch=1.15, tail=0.34),
        "fire_smg": gunshot(23, 0.34, body_hz=240.0, brightness=5200.0, punch=0.8, tail=0.16),
        "fire_lmg": gunshot(37, 0.48, body_hz=140.0, brightness=3400.0, punch=1.1, tail=0.26),
        "fire_pistol": gunshot(53, 0.38, body_hz=300.0, brightness=5600.0, punch=0.85, tail=0.18),
        "fire_launcher": gunshot(71, 1.10, body_hz=85.0, brightness=1800.0, punch=1.3, tail=0.75),
        "reload_out": mech_click(97, 2100.0, 0.12, 0.020),
        "reload_in": mech_click(103, 1700.0, 0.14, 0.026),
        "bolt": mech_click(109, 3200.0, 0.10, 0.014),
        "hit_marker": ui_blip(0.07, 1180.0),
        "ui_click": ui_blip(0.09, 640.0),
        "wind": wind_loop(131),
    }
    for index in range(4):
        bank["step_%d" % index] = footstep(200 + index * 17)

    total = 0.0
    for name, samples in bank.items():
        seconds = write_wav(os.path.join(OUT_DIR, "%s.wav" % name), samples)
        total += seconds
        print("  %-16s %5.2fs  peak %.2f" % (name, seconds, float(np.abs(samples).max())))
    print("\n%d clips, %.1fs total -> %s" % (len(bank), total, OUT_DIR))


if __name__ == "__main__":
    main()
