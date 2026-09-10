"""Generate shareable PNG stat cards for comedian profile pages."""

from __future__ import annotations

import hashlib
import io
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

CARD_W = 1200
CARD_H = 630

ASSETS_DIR = Path(__file__).resolve().parent / "assets" / "fonts"
CACHE_DIR = Path(__file__).resolve().parent / "card_cache"

BG = (9, 9, 11)
CARD = (20, 20, 22)
BORDER = (30, 30, 34)
TEXT = (250, 250, 250)
MUTED = (113, 113, 122)
RED = (220, 38, 38)
GREEN = (34, 197, 94)


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(ASSETS_DIR / name), size)


def _stats_hash(guest: dict[str, Any]) -> str:
    key = (
        f"{guest['guest_name']}|{guest['episode_count']}|{guest['avg_kill_score']}|"
        f"{guest['baseline_avg']}|{guest['total_laugh_count']}|"
        f"{[e['avg_kill_score'] for e in guest['episodes']]}"
    )
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def cache_path(guest_name: str, stats_hash: str) -> Path:
    safe_name = "".join(c if c.isalnum() else "_" for c in guest_name)
    return CACHE_DIR / f"{safe_name}_{stats_hash}.png"


def _draw_sparkline(draw: ImageDraw.ImageDraw, scores: list[float], baseline: float, box: tuple[int, int, int, int]) -> None:
    x0, y0, x1, y1 = box
    if not scores:
        return
    all_vals = scores + [baseline]
    lo, hi = min(all_vals), max(all_vals)
    span = (hi - lo) or 1

    def px(i: int) -> int:
        if len(scores) == 1:
            return (x0 + x1) // 2
        return x0 + int(i / (len(scores) - 1) * (x1 - x0))

    def py(v: float) -> int:
        return y1 - int((v - lo) / span * (y1 - y0))

    baseline_y = py(baseline)
    draw.line([(x0, baseline_y), (x1, baseline_y)], fill=BORDER, width=2)

    points = [(px(i), py(v)) for i, v in enumerate(scores)]
    if len(points) > 1:
        draw.line(points, fill=RED, width=4, joint="curve")
    for x, y in points:
        draw.ellipse([x - 5, y - 5, x + 5, y + 5], fill=RED, outline=BG, width=2)


def render_card(guest: dict[str, Any]) -> bytes:
    img = Image.new("RGB", (CARD_W, CARD_H), BG)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, CARD_W - 1, CARD_H - 1], outline=BORDER, width=2)
    draw.rectangle([0, 0, CARD_W - 1, 8], fill=RED)

    label_font = _font("GeistMono-Regular.ttf", 22)
    value_font = _font("GeistMono-Bold.ttf", 54)
    brand_font = _font("GeistMono-Regular.ttf", 22)

    pad = 64
    max_name_w = CARD_W - pad * 2
    name_size = 76
    name_font = _font("InstrumentSans-Bold.ttf", name_size)
    while name_size > 32:
        bbox = draw.textbbox((0, 0), guest["guest_name"], font=name_font)
        if bbox[2] - bbox[0] <= max_name_w:
            break
        name_size -= 4
        name_font = _font("InstrumentSans-Bold.ttf", name_size)
    draw.text((pad, 70 + (76 - name_size)), guest["guest_name"], font=name_font, fill=TEXT)
    draw.text((pad, 170), "KILL TONY", font=label_font, fill=MUTED)

    lift = None
    if guest["avg_kill_score"] is not None:
        lift = round(guest["avg_kill_score"] - guest["baseline_avg"], 1)

    stats = [
        ("APPEARANCES", str(guest["episode_count"])),
        ("AVG KILL SCORE", str(guest["avg_kill_score"]) if guest["avg_kill_score"] is not None else "—"),
        ("SCORE LIFT", f"{'+' if lift and lift > 0 else ''}{lift}" if lift is not None else "—"),
    ]

    col_w = (CARD_W - pad * 2) // len(stats)
    stat_y = 320
    for i, (label, value) in enumerate(stats):
        x = pad + i * col_w
        draw.text((x, stat_y), label, font=label_font, fill=MUTED)
        color = TEXT
        if label == "SCORE LIFT" and lift is not None:
            color = GREEN if lift > 0 else (RED if lift < 0 else MUTED)
        draw.text((x, stat_y + 36), value, font=value_font, fill=color)

    scores = [e["avg_kill_score"] for e in guest["episodes"] if e["avg_kill_score"] is not None]
    if scores:
        _draw_sparkline(draw, scores, guest["baseline_avg"], (pad, 470, CARD_W - pad, 540))

    brand_text = "killtonyarchive.com"
    bbox = draw.textbbox((0, 0), brand_text, font=brand_font)
    brand_w = bbox[2] - bbox[0]
    draw.text((CARD_W - pad - brand_w, CARD_H - 60), brand_text, font=brand_font, fill=MUTED)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def get_or_render_card(guest: dict[str, Any]) -> bytes:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stats_hash = _stats_hash(guest)
    path = cache_path(guest["guest_name"], stats_hash)
    if path.exists():
        return path.read_bytes()

    png_bytes = render_card(guest)
    path.write_bytes(png_bytes)

    safe_name = "".join(c if c.isalnum() else "_" for c in guest["guest_name"])
    for stale in CACHE_DIR.glob(f"{safe_name}_*.png"):
        if stale != path:
            stale.unlink(missing_ok=True)

    return png_bytes
