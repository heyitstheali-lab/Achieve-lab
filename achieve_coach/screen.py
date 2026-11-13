"""Screen capture."""

from __future__ import annotations

import io

import mss
from PIL import Image


def monitor_count() -> int:
    with mss.mss() as sct:
        return len(sct.monitors) - 1  # monitors[0] is the combined virtual screen


def capture_png(monitor: int = 1, max_edge: int = 1920) -> bytes:
    """Screenshot one monitor (1 = primary) and return PNG bytes.

    Large screens are scaled down so the long edge is at most `max_edge`
    pixels, which keeps uploads small while text stays readable.
    """
    with mss.mss() as sct:
        monitors = sct.monitors
        if monitor < 1 or monitor >= len(monitors):
            monitor = 1
        shot = sct.grab(monitors[monitor])
        img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

    if max(img.size) > max_edge:
        img.thumbnail((max_edge, max_edge), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
