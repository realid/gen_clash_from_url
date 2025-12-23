#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Tuple


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def mix(c1: Tuple[int, int, int], c2: Tuple[int, int, int], t: float) -> Tuple[int, int, int]:
    return (lerp(c1[0], c2[0], t), lerp(c1[1], c2[1], t), lerp(c1[2], c2[2], t))


def write_png(path: Path, width: int, height: int, rgba: bytearray) -> None:
    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # no filter
        start = y * stride
        raw.extend(rgba[start:start + stride])
    compressor = zlib.compressobj()
    data = compressor.compress(bytes(raw)) + compressor.flush()

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + tag + payload + struct.pack(">I", zlib.crc32(tag + payload))

    png = bytearray()
    png.extend(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)))
    png.extend(chunk(b"IDAT", data))
    png.extend(chunk(b"IEND", b""))
    path.write_bytes(png)


def write_icns(path: Path, png_data: bytes) -> None:
    # Minimal ICNS with a single 1024x1024 PNG (ic10).
    chunk_type = b"ic10"
    chunk_size = 8 + len(png_data)
    total_size = 8 + chunk_size
    data = bytearray()
    data.extend(b"icns")
    data.extend(struct.pack(">I", total_size))
    data.extend(chunk_type)
    data.extend(struct.pack(">I", chunk_size))
    data.extend(png_data)
    path.write_bytes(data)

def fill_rect(rgba: bytearray, width: int, height: int, x0: int, y0: int,
              x1: int, y1: int, color: Tuple[int, int, int, int]) -> None:
    x0 = max(0, x0)
    y0 = max(0, y0)
    x1 = min(width, x1)
    y1 = min(height, y1)
    for y in range(y0, y1):
        row = (y * width + x0) * 4
        for _ in range(x0, x1):
            rgba[row:row + 4] = bytes(color)
            row += 4


def fill_circle(rgba: bytearray, width: int, height: int, cx: int, cy: int,
                r: int, color: Tuple[int, int, int, int]) -> None:
    r2 = r * r
    y0 = max(0, cy - r)
    y1 = min(height - 1, cy + r)
    for y in range(y0, y1 + 1):
        dy = y - cy
        dy2 = dy * dy
        if dy2 > r2:
            continue
        x_span = int((r2 - dy2) ** 0.5)
        x0 = max(0, cx - x_span)
        x1 = min(width - 1, cx + x_span)
        row = (y * width + x0) * 4
        for _ in range(x0, x1 + 1):
            rgba[row:row + 4] = bytes(color)
            row += 4


def fill_round_rect(rgba: bytearray, width: int, height: int, x0: int, y0: int,
                    x1: int, y1: int, r: int, color: Tuple[int, int, int, int]) -> None:
    fill_rect(rgba, width, height, x0 + r, y0, x1 - r, y1, color)
    fill_rect(rgba, width, height, x0, y0 + r, x1, y1 - r, color)
    fill_circle(rgba, width, height, x0 + r, y0 + r, r, color)
    fill_circle(rgba, width, height, x1 - r - 1, y0 + r, r, color)
    fill_circle(rgba, width, height, x0 + r, y1 - r - 1, r, color)
    fill_circle(rgba, width, height, x1 - r - 1, y1 - r - 1, r, color)


def draw_ring(rgba: bytearray, width: int, height: int, cx: int, cy: int,
              r_outer: int, r_inner: int, color: Tuple[int, int, int, int],
              bg: Tuple[int, int, int, int]) -> None:
    fill_circle(rgba, width, height, cx, cy, r_outer, color)
    fill_circle(rgba, width, height, cx, cy, r_inner, bg)


def main() -> None:
    width = height = 1024
    rgba = bytearray(width * height * 4)

    top = (6, 12, 24)
    bottom = (12, 20, 36)
    for y in range(height):
        t = y / (height - 1)
        r, g, b = mix(top, bottom, t)
        row = y * width * 4
        for x in range(width):
            rgba[row:row + 4] = bytes((r, g, b, 255))
            row += 4

    panel = (12, 18, 34, 255)
    px0, py0, px1, py1 = 92, 92, 932, 932
    fill_round_rect(rgba, width, height, px0, py0, px1, py1, 120, panel)

    glow = (0, 200, 255, 255)
    core = (18, 230, 198, 255)
    draw_ring(rgba, width, height, 512, 420, 180, 120, glow, panel)
    draw_ring(rgba, width, height, 512, 420, 130, 86, core, panel)

    link = (0, 210, 255, 255)
    fill_round_rect(rgba, width, height, 356, 382, 668, 458, 28, link)

    grid = (28, 42, 70, 255)
    fill_round_rect(rgba, width, height, 220, 610, 804, 654, 12, grid)
    fill_round_rect(rgba, width, height, 220, 678, 804, 722, 12, grid)
    fill_round_rect(rgba, width, height, 220, 746, 744, 790, 12, grid)

    out_dir = Path(__file__).resolve().parent.parent / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    icon_png = out_dir / "icon.png"
    write_png(icon_png, width, height, rgba)

    iconset_dir = out_dir / "icon.iconset"
    if iconset_dir.exists():
        for p in iconset_dir.glob("*.png"):
            p.unlink()
    else:
        iconset_dir.mkdir(parents=True, exist_ok=True)

    def scale_to(size: int) -> bytearray:
        out = bytearray(size * size * 4)
        for y in range(size):
            sy = min(height - 1, int(y * (height / size)))
            for x in range(size):
                sx = min(width - 1, int(x * (width / size)))
                si = (sy * width + sx) * 4
                di = (y * size + x) * 4
                out[di:di + 4] = rgba[si:si + 4]
        return out

    base_sizes = [16, 32, 128, 256, 512]
    for size in base_sizes:
        out = scale_to(size)
        write_png(iconset_dir / f"icon_{size}x{size}.png", size, size, out)
        out2x = scale_to(size * 2)
        write_png(iconset_dir / f"icon_{size}x{size}@2x.png", size * 2, size * 2, out2x)

    icns_path = out_dir / "icon.icns"
    write_icns(icns_path, icon_png.read_bytes())

    bg_w, bg_h = 1200, 800
    bg = bytearray(bg_w * bg_h * 4)
    bg_top = (238, 242, 250)
    bg_bottom = (220, 228, 242)
    for y in range(bg_h):
        t = y / (bg_h - 1)
        r, g, b = mix(bg_top, bg_bottom, t)
        row = y * bg_w * 4
        for x in range(bg_w):
            bg[row:row + 4] = bytes((r, g, b, 255))
            row += 4

    grid = (190, 200, 220, 255)
    for y in range(120, bg_h - 80, 80):
        fill_round_rect(bg, bg_w, bg_h, 160, y, bg_w - 160, y + 12, 6, grid)

    write_png(out_dir / "dmg-background.png", bg_w, bg_h, bg)


if __name__ == "__main__":
    main()
