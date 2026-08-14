"""Minimal dependency-free PNG writer.

Blender's bundled Python has numpy but no Pillow, so we write PNG bytes
ourselves. Only what we need: 8-bit RGB / RGBA / grayscale, no interlace.
"""

import struct
import zlib

import numpy as np


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_png(path: str, image: np.ndarray, srgb: bool = False) -> None:
    """Write a uint8 array of shape (h, w), (h, w, 3) or (h, w, 4) as PNG.

    `srgb` only tags the file (sRGB chunk); it does not convert values.
    Colour maps should be written with srgb=True, data maps (normal,
    roughness, AO, ORM) with srgb=False so importers keep them linear.
    """
    arr = np.asarray(image)
    if arr.dtype != np.uint8:
        arr = np.clip(arr, 0.0, 1.0)
        arr = (arr * 255.0 + 0.5).astype(np.uint8)

    if arr.ndim == 2:
        colour_type, channels = 0, 1
    elif arr.ndim == 3 and arr.shape[2] == 3:
        colour_type, channels = 2, 3
    elif arr.ndim == 3 and arr.shape[2] == 4:
        colour_type, channels = 6, 4
    else:
        raise ValueError(f"unsupported image shape {arr.shape}")

    height, width = arr.shape[0], arr.shape[1]
    flat = arr.reshape(height, width * channels)

    # Filter type 0 (None) in front of every scanline.
    raw = np.empty((height, width * channels + 1), dtype=np.uint8)
    raw[:, 0] = 0
    raw[:, 1:] = flat

    out = [b"\x89PNG\r\n\x1a\n"]
    out.append(_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, colour_type, 0, 0, 0)))
    if srgb:
        out.append(_chunk(b"sRGB", b"\x00"))  # perceptual rendering intent
        out.append(_chunk(b"gAMA", struct.pack(">I", 45455)))
    out.append(_chunk(b"IDAT", zlib.compress(raw.tobytes(), 9)))
    out.append(_chunk(b"IEND", b""))

    with open(path, "wb") as handle:
        handle.write(b"".join(out))


def read_png_size(path: str):
    """Return (width, height) by reading only the IHDR chunk."""
    with open(path, "rb") as handle:
        header = handle.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"{path} is not a PNG")
    return struct.unpack(">II", header[16:24])
