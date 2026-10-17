"""App icon: one SVG (same mark as the UI favicon) plus a stdlib rasteriser for the PNG sizes a PWA manifest needs."""
from __future__ import annotations

import json
import math
import struct
import zlib
from functools import lru_cache

BG, FG = (11, 12, 14), (139, 140, 255)
SVG = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><rect width='32' height='32' fill='#0b0c0e'/>"
       "<path d='M9 24V8h8a5 5 0 010 10h-5' fill='none' stroke='#8b8cff' stroke-width='3' "
       "stroke-linecap='round' stroke-linejoin='round'/></svg>")
# the "P": polyline + half circle (centre 17,13 r5) in the 32x32 viewBox, stroke width 3
_SEGS = [((9, 24), (9, 8)), ((9, 8), (17, 8)), ((17, 18), (12, 18))]
_CX, _CY, _R, _HALF = 17.0, 13.0, 5.0, 1.5


def _dist(x: float, y: float) -> float:
    d = 1e9
    for (ax, ay), (bx, by) in _SEGS:
        dx, dy = bx - ax, by - ay
        t = max(0.0, min(1.0, ((x - ax) * dx + (y - ay) * dy) / (dx * dx + dy * dy)))
        d = min(d, math.hypot(x - ax - t * dx, y - ay - t * dy))
    if x >= _CX:
        d = min(d, abs(math.hypot(x - _CX, y - _CY) - _R))
    return d


@lru_cache(maxsize=8)
def png(size: int) -> bytes:
    rows = []
    for j in range(size):
        y = (j + 0.5) * 32 / size
        row = bytearray([0])
        for i in range(size):
            a = max(0.0, min(1.0, (_HALF - _dist((i + 0.5) * 32 / size, y)) * size / 32 + 0.5))
            row += bytes(int(b + (f - b) * a) for b, f in zip(BG, FG))
        rows.append(bytes(row))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b""))


def ico(size: int = 256) -> bytes:
    """Windows .ico holding one PNG image (Vista+)."""
    p = png(size)
    d = size if size < 256 else 0
    return struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", d, d, 0, 0, 1, 32, len(p), 22) + p


MANIFEST = json.dumps({
    "name": "PYTHIA Studio", "short_name": "PYTHIA", "description": "Accelerate Python hotspots with verified C++.",
    "start_url": "/", "scope": "/", "display": "standalone", "background_color": "#0b0c0e", "theme_color": "#0b0c0e",
    "icons": [{"src": "/icon.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
              {"src": "/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
              {"src": "/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}]})
HEAD_TAGS = ('<link rel="manifest" href="/manifest.webmanifest"><link rel="apple-touch-icon" href="/icon-192.png">'
             '<meta name="theme-color" content="#0b0c0e">')
