"""Render the 16:9 Jev explainer with a real Tetris app capture."""

from __future__ import annotations

import argparse
import math
import random
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


ROOT = Path(__file__).resolve().parents[1]
VIDEO_DIR = ROOT / "video"
CAPTURE_DIR = VIDEO_DIR / "real_tetris"
DEFAULT_OUTPUT = VIDEO_DIR / "jev_explainer_landscape.mp4"
DEFAULT_POSTER = VIDEO_DIR / "jev_explainer_landscape_poster.png"

WIDTH = 1920
HEIGHT = 1080
FPS = 30
DURATION = 55.0

BG = (7, 12, 27)
BG_2 = (10, 25, 40)
CARD = (16, 28, 52)
CARD_2 = (20, 36, 65)
BORDER = (39, 62, 93)
TEXT = (239, 247, 255)
MUTED = (145, 168, 199)
DIM = (82, 109, 143)
MINT = (105, 245, 207)
PURPLE = (171, 122, 255)
BLUE = (93, 181, 255)
ORANGE = (255, 181, 86)
PINK = (255, 112, 156)
RED = (255, 105, 124)
WHITE = (255, 255, 255)

FONT_SANS = "/System/Library/Fonts/Supplemental/Arial.ttf"
FONT_BOLD = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
FONT_MONO = "/System/Library/Fonts/SFNSMono.ttf"


def rgba(color: tuple[int, int, int], alpha: int = 255) -> tuple[int, int, int, int]:
    return (*color, alpha)


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def ease_out(value: float) -> float:
    value = clamp(value)
    return 1 - (1 - value) ** 3


def ease_in_out(value: float) -> float:
    value = clamp(value)
    return value * value * (3 - 2 * value)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = clamp(amount)
    return tuple(round(x + (y - x) * amount) for x, y in zip(a, b))


@lru_cache(maxsize=None)
def load_font(size: int, bold: bool = False, mono: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_MONO if mono else FONT_BOLD if bold else FONT_SANS
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        fallback = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf" if mono else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
        return ImageFont.truetype(fallback, size)


def text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    value: str,
    size: int,
    fill: tuple[int, int, int, int] | tuple[int, int, int] = TEXT,
    *,
    anchor: str = "la",
    bold: bool = False,
    mono: bool = False,
    spacing: int = 5,
) -> None:
    draw.multiline_text(
        (int(xy[0]), int(xy[1])),
        value,
        font=load_font(size, bold=bold, mono=mono),
        fill=fill,
        anchor=anchor,
        spacing=spacing,
    )


def panel(
    draw: ImageDraw.ImageDraw,
    box: tuple[float, float, float, float],
    *,
    fill: tuple[int, int, int, int] | tuple[int, int, int] = CARD,
    outline: tuple[int, int, int, int] | tuple[int, int, int] = BORDER,
    radius: int = 24,
    width: int = 2,
) -> None:
    draw.rounded_rectangle(tuple(int(round(value)) for value in box), radius=radius, fill=fill, outline=outline, width=width)


def pill(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    label: str,
    *,
    fill: tuple[int, int, int, int] | tuple[int, int, int] = CARD_2,
    outline: tuple[int, int, int, int] | tuple[int, int, int] = BORDER,
    color: tuple[int, int, int, int] | tuple[int, int, int] = MUTED,
    size: int = 19,
    padding_x: int = 18,
    padding_y: int = 10,
) -> tuple[int, int, int, int]:
    current_font = load_font(size, bold=True)
    x, y = int(xy[0]), int(xy[1])
    bbox = draw.textbbox((0, 0), label, font=current_font)
    width = bbox[2] + padding_x * 2
    height = bbox[3] + padding_y * 2
    box = (x, y, x + width, y + height)
    draw.rounded_rectangle(box, radius=height // 2, fill=fill, outline=outline, width=2)
    draw.text((x + width // 2, y + height // 2), label, font=current_font, fill=color, anchor="mm")
    return box


def line(draw: ImageDraw.ImageDraw, xy: tuple[float, float, float, float], fill, width: int = 2) -> None:
    draw.line(tuple(int(round(value)) for value in xy), fill=fill, width=width)


def arrow(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], color, width: int = 4) -> None:
    x1, y1 = start
    x2, y2 = end
    line(draw, (x1, y1, x2, y2), color, width)
    angle = math.atan2(y2 - y1, x2 - x1)
    size = 15
    left = (x2 - math.cos(angle - 0.55) * size, y2 - math.sin(angle - 0.55) * size)
    right = (x2 - math.cos(angle + 0.55) * size, y2 - math.sin(angle + 0.55) * size)
    draw.polygon([(x2, y2), left, right], fill=color)


def glow_circle(image: Image.Image, center: tuple[float, float], radius: float, color: tuple[int, int, int]) -> None:
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    x, y = center
    for multiplier, alpha in ((2.4, 13), (1.8, 22), (1.35, 35)):
        current = radius * multiplier
        draw.ellipse((x - current, y - current, x + current, y + current), fill=rgba(color, alpha))
    image.alpha_composite(overlay)


def scene_opacity(local: float) -> float:
    return min(1.0, 0.35 + local * 4.0, 0.35 + (1.0 - local) * 5.0)


def make_background() -> Image.Image:
    image = Image.new("RGBA", (WIDTH, HEIGHT), rgba(BG))
    draw = ImageDraw.Draw(image)
    for y in range(0, HEIGHT, 12):
        color = mix(BG, BG_2, y / HEIGHT)
        draw.rectangle((0, y, WIDTH, y + 12), fill=rgba(color))
    for x in range(-HEIGHT, WIDTH + HEIGHT, 118):
        line(draw, (x, 0, x + HEIGHT, HEIGHT), rgba((26, 48, 77), 18), 2)
    return image


BASE_BACKGROUND = make_background()
RANDOM = random.Random(42)
PARTICLES = [
    (RANDOM.randrange(WIDTH), RANDOM.randrange(90, 1010), RANDOM.choice((2, 2, 3)), RANDOM.random(), RANDOM.choice((MINT, PURPLE, BLUE, ORANGE)))
    for _ in range(76)
]
CAPTURE_PATHS = sorted(CAPTURE_DIR.glob("real_[0-9][0-9].png"))


@lru_cache(maxsize=None)
def capture_image(path: str) -> Image.Image:
    return Image.open(path).convert("RGBA")


def new_frame(t: float) -> Image.Image:
    image = BASE_BACKGROUND.copy()
    draw = ImageDraw.Draw(image)
    for index, (x, y, radius, phase, color) in enumerate(PARTICLES):
        xx = (x + t * (5 + index % 5)) % WIDTH
        yy = y + math.sin(t * 0.8 + phase * 12) * 8
        alpha = int(24 + 20 * (0.5 + 0.5 * math.sin(t * 0.9 + phase * 20)))
        draw.ellipse((xx - radius, yy - radius, xx + radius, yy + radius), fill=rgba(color, alpha))
    return image


def draw_header(draw: ImageDraw.ImageDraw, label: str) -> None:
    text(draw, (82, 38), "TYPESAFE", 19, fill=rgba(MINT), bold=True, mono=True)
    text(draw, (82, 69), "JEV / SYSTEM ONE", 14, fill=rgba(DIM), bold=True, mono=True)
    text(draw, (1838, 46), label.upper(), 15, fill=rgba(MUTED), anchor="ra", bold=True, mono=True)
    line(draw, (82, 105, 1838, 105), rgba(BORDER, 160), 2)


def draw_footer(draw: ImageDraw.ImageDraw, t: float, duration: float) -> None:
    y = 1018
    line(draw, (82, y, 1838, y), rgba(BORDER, 150), 3)
    line(draw, (82, y, 82 + 1756 * clamp(t / duration), y), rgba(MINT, 230), 5)
    text(draw, (82, 1047), "STATE  →  JUDGMENT  →  CODE", 14, fill=rgba(DIM), bold=True, mono=True)
    text(draw, (1838, 1047), "typesafe.ai", 15, fill=rgba(MUTED), anchor="ra", bold=True, mono=True)


def scene_title(
    draw: ImageDraw.ImageDraw,
    eyebrow: str,
    headline: str,
    subhead: str,
    *,
    y: int = 145,
    headline_size: int = 64,
) -> None:
    text(draw, (82, y), eyebrow.upper(), 17, fill=rgba(MINT), bold=True, mono=True)
    text(draw, (82, y + 49), headline, headline_size, fill=rgba(TEXT), bold=True, spacing=0)
    bbox = draw.multiline_textbbox((0, 0), headline, font=load_font(headline_size, bold=True), spacing=0)
    text(draw, (82, y + 49 + bbox[3] - bbox[1] + 17), subhead, 24, fill=rgba(MUTED))


def draw_jev_orb(image: Image.Image, center: tuple[int, int], pulse: float) -> None:
    x, y = center
    radius = 76 * (1 + math.sin(pulse * math.pi * 4) * 0.05)
    glow_circle(image, (x, y), radius, MINT)
    draw = ImageDraw.Draw(image)
    draw.ellipse((x - 64, y - 64, x + 64, y + 64), fill=rgba((15, 48, 58)), outline=rgba(MINT, 245), width=3)
    draw.ellipse((x - 46, y - 46, x + 46, y + 46), outline=rgba(MINT, 120), width=2)
    text(draw, (x, y - 7), "JEV", 28, fill=rgba(TEXT), anchor="mm", bold=True, mono=True)
    text(draw, (x, y + 29), "judgment", 14, fill=rgba(MINT), anchor="mm", bold=True, mono=True)


def intro_scene(layer: Image.Image, p: float) -> None:
    draw = ImageDraw.Draw(layer)
    reveal = ease_out(p)
    text(draw, (90, 200), "A NEW PRIMITIVE FOR AI SOFTWARE", 20, fill=rgba(MINT), bold=True, mono=True)
    text(draw, (90, 345 - 20 * (1 - reveal)), "Most AI", 92, fill=rgba(TEXT), bold=True)
    text(draw, (90, 455 - 20 * (1 - reveal)), "writes.", 92, fill=rgba(MUTED), bold=True)
    text(draw, (90, 580 - 20 * (1 - reveal)), "Jev decides.", 92, fill=rgba(MINT), bold=True)
    line(draw, (90, 685, 635, 685), rgba(MINT, 230), 4)
    pill(draw, (90, 745), "NO FREE-FORM PARSE", fill=rgba(CARD_2, 220), outline=rgba(BORDER, 210), color=rgba(TEXT))
    pill(draw, (320, 745), "TYPED ANSWERS", fill=rgba(CARD_2, 220), outline=rgba(BORDER, 210), color=rgba(TEXT))
    pill(draw, (525, 745), "BUILT FOR CODE", fill=rgba(CARD_2, 220), outline=rgba(BORDER, 210), color=rgba(TEXT))

    text(draw, (1130, 210), "THE SHIFT", 18, fill=rgba(MUTED), bold=True, mono=True)
    state_box = (1090, 340, 1370, 660)
    code_box = (1550, 340, 1830, 660)
    panel(draw, state_box, fill=rgba(CARD, 240), outline=rgba(BLUE, 180))
    panel(draw, code_box, fill=rgba(CARD, 240), outline=rgba(PURPLE, 180))
    text(draw, (1120, 378), "STATE", 16, fill=rgba(BLUE), bold=True, mono=True)
    text(draw, (1120, 430), "board + context", 27, fill=rgba(TEXT), bold=True)
    text(draw, (1120, 510), 'piece: "T"\nquestion: "best move?"', 20, fill=rgba(MUTED), mono=True, spacing=12)
    text(draw, (1580, 378), "CODE", 16, fill=rgba(PURPLE), bold=True, mono=True)
    text(draw, (1580, 430), "if choice ==", 25, fill=rgba(TEXT), bold=True, mono=True)
    text(draw, (1580, 480), '"placement_07":', 22, fill=rgba(PURPLE), mono=True)
    text(draw, (1580, 535), "place()", 27, fill=rgba(MINT), bold=True, mono=True)
    arrow(draw, (1390, 500), (1518, 500), rgba(MINT, 220), 4)
    draw_jev_orb(layer, (1455, 500), p)
    text(draw, (1090, 745), "A fast decision layer for software that needs to act.", 24, fill=rgba(MUTED))


def state_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], p: float) -> None:
    panel(draw, box, fill=rgba(CARD, 240), outline=rgba(BLUE, 190))
    x1, y1, _, _ = box
    text(draw, (x1 + 30, y1 + 29), "STATE", 17, fill=rgba(BLUE), bold=True, mono=True)
    text(draw, (x1 + 30, y1 + 73), "unstructured context", 26, fill=rgba(TEXT), bold=True)
    lines = [('"piece"', ': "T"'), ('"board"', ': 10 × 20'), ('"next"', ': ["J", "I"]'), ('"question"', ': "best move?"')]
    for index, (key, value) in enumerate(lines):
        y = y1 + 145 + index * 49
        text(draw, (x1 + 30, y), key, 19, fill=rgba(BLUE), mono=True)
        text(draw, (x1 + 150, y), value, 19, fill=rgba(TEXT), mono=True)
    line(draw, (x1 + 30, y1 + 330, x1 + 410, y1 + 330), rgba(BORDER), 2)
    text(draw, (x1 + 30, y1 + 360), "your app owns the schema", 17, fill=rgba(DIM), mono=True)


def output_panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int]) -> None:
    panel(draw, box, fill=rgba(CARD, 240), outline=rgba(MINT, 190))
    x1, y1, _, _ = box
    text(draw, (x1 + 30, y1 + 29), "OUTPUT", 17, fill=rgba(MINT), bold=True, mono=True)
    text(draw, (x1 + 30, y1 + 73), "typed judgment", 26, fill=rgba(TEXT), bold=True)
    text(draw, (x1 + 30, y1 + 150), "Choice", 17, fill=rgba(PURPLE), bold=True, mono=True)
    text(draw, (x1 + 30, y1 + 195), "placement_07", 25, fill=rgba(TEXT), mono=True)
    text(draw, (x1 + 30, y1 + 260), "0.92", 39, fill=rgba(MINT), bold=True, mono=True)
    text(draw, (x1 + 150, y1 + 275), "probability", 18, fill=rgba(MUTED), mono=True)
    line(draw, (x1 + 30, y1 + 330, x1 + 410, y1 + 330), rgba(BORDER), 2)
    text(draw, (x1 + 30, y1 + 362), "finite answers in", 17, fill=rgba(DIM), mono=True)
    text(draw, (x1 + 30, y1 + 395), "code out", 17, fill=rgba(DIM), mono=True)


def flow_scene(layer: Image.Image, p: float) -> None:
    draw = ImageDraw.Draw(layer)
    scene_title(draw, "The shape", "State in. Typed judgment out.", "The app defines the possible answers first; Jev chooses among them.")
    state_panel(draw, (90, 330, 570, 750), p)
    output_panel(draw, (1350, 330, 1830, 750))
    arrow(draw, (600, 540), (820, 540), rgba(BLUE, 220), 4)
    arrow(draw, (1095, 540), (1330, 540), rgba(MINT, 220), 4)
    draw_jev_orb(layer, (960, 540), p)
    for index in range(11):
        amount = clamp(p * 1.3 - index * 0.06)
        if amount <= 0:
            continue
        start_x = 635 + index * 10
        end_x = 1310 - index * 9
        x = start_x + (end_x - start_x) * ease_in_out(amount)
        y = 470 + index * 13
        draw.ellipse((x - 5, y - 5, x + 5, y + 5), fill=rgba((190, 255, 237), 190))
    text(draw, (90, 850), "Not a chat reply.", 31, fill=rgba(TEXT), bold=True)
    text(draw, (90, 900), "A typed decision your program can verify and use.", 24, fill=rgba(MUTED))
    pill(draw, (1360, 850), "CHOICE", fill=rgba(PURPLE, 38), outline=rgba(PURPLE, 150), color=rgba(PURPLE))
    pill(draw, (1535, 850), "SCORE", fill=rgba(ORANGE, 38), outline=rgba(ORANGE, 150), color=rgba(ORANGE))
    pill(draw, (1695, 850), "NOUL", fill=rgba(MINT, 32), outline=rgba(MINT, 145), color=rgba(MINT))


def primitive_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], title: str, subtitle: str, color: tuple[int, int, int], kind: str) -> None:
    panel(draw, box, fill=rgba(CARD, 240), outline=rgba(color, 175))
    x1, y1, x2, y2 = box
    draw.ellipse((x1 + 30, y1 + 30, x1 + 78, y1 + 78), fill=rgba(color, 45), outline=rgba(color, 205), width=2)
    text(draw, (x1 + 54, y1 + 54), kind, 17, fill=rgba(color), anchor="mm", bold=True, mono=True)
    text(draw, (x1 + 30, y1 + 112), title, 30, fill=rgba(TEXT), bold=True)
    text(draw, (x1 + 30, y1 + 162), subtitle, 20, fill=rgba(MUTED))
    if kind == "C":
        for index, (label, amount, bar_color) in enumerate((("place_07", 0.92, MINT), ("place_03", 0.05, DIM), ("place_11", 0.03, DIM))):
            y = y1 + 245 + index * 48
            text(draw, (x1 + 30, y), label, 17, fill=rgba(TEXT if index == 0 else MUTED), mono=True)
            draw.rounded_rectangle((x1 + 180, y + 4, x2 - 30, y + 18), radius=7, fill=rgba((35, 53, 77)))
            draw.rounded_rectangle((x1 + 180, y + 4, x1 + 180 + (x2 - x1 - 210) * amount, y + 18), radius=7, fill=rgba(bar_color, 225))
    elif kind == "S":
        text(draw, (x1 + 30, y1 + 255), "risk / urgency", 17, fill=rgba(MUTED), mono=True)
        line(draw, (x1 + 30, y1 + 318, x2 - 30, y1 + 318), rgba(BORDER), 5)
        point = x1 + 30 + (x2 - x1 - 60) * 0.78
        draw.ellipse((point - 12, y1 + 306, point + 12, y1 + 330), fill=rgba(color), outline=rgba(TEXT), width=2)
        text(draw, (x1 + 30, y1 + 365), "7.8 / 10", 28, fill=rgba(color), bold=True, mono=True)
    else:
        text(draw, (x1 + 30, y1 + 255), "is this safe to run?", 17, fill=rgba(MUTED), mono=True)
        text(draw, (x1 + 30, y1 + 330), "TRUE", 34, fill=rgba(color), bold=True, mono=True)
        text(draw, (x1 + 30, y1 + 382), "0.97 probability", 17, fill=rgba(TEXT), mono=True)
        line(draw, (x1 + 30, y1 + 430, x2 - 30, y1 + 430), rgba(color, 160), 3)


def primitives_scene(layer: Image.Image, p: float) -> None:
    draw = ImageDraw.Draw(layer)
    scene_title(draw, "The primitives", "Three shapes for software decisions.", "Pick the smallest question that matches the branch your code needs.", headline_size=58)
    cards = [("Choice", "select one", PURPLE, "C"), ("Score", "grade a scale", ORANGE, "S"), ("Noul", "estimate true", MINT, "N")]
    for index, (title, subtitle, color, kind) in enumerate(cards):
        local = ease_out(clamp((p - index * 0.16) * 3.5))
        x = 90 + index * 620
        y = 330 + int((1 - local) * 35)
        primitive_card(draw, (x, y, x + 540, y + 455), title, subtitle, color, kind)
    text(draw, (90, 865), "The output space is declared.", 28, fill=rgba(TEXT), bold=True)
    text(draw, (90, 910), "The judgment is still probabilistic.", 23, fill=rgba(MUTED))
    pill(draw, (1470, 860), "TYPE-SAFE SHAPE", fill=rgba(MINT, 30), outline=rgba(MINT, 145), color=rgba(MINT))


def paste_real_capture(image: Image.Image, p: float) -> None:
    draw = ImageDraw.Draw(image)
    box = (700, 260, 1835, 945)
    panel(draw, box, fill=rgba((8, 16, 31), 248), outline=rgba(MINT, 170), radius=22, width=3)
    x1, y1, x2, y2 = box
    draw.ellipse((x1 + 22, y1 + 17, x1 + 34, y1 + 29), fill=rgba(PINK, 210))
    draw.ellipse((x1 + 43, y1 + 17, x1 + 55, y1 + 29), fill=rgba(ORANGE, 210))
    draw.ellipse((x1 + 64, y1 + 17, x1 + 76, y1 + 29), fill=rgba(MINT, 210))
    text(draw, (x1 + 100, y1 + 17), "LOCAL APP / REAL TETRIS CAPTURE", 14, fill=rgba(MUTED), bold=True, mono=True)

    if not CAPTURE_PATHS:
        text(draw, ((x1 + x2) // 2, (y1 + y2) // 2), "real capture unavailable", 25, fill=rgba(RED), anchor="mm")
        return
    position = clamp(p) * (len(CAPTURE_PATHS) - 1)
    index = min(int(position), len(CAPTURE_PATHS) - 1)
    fraction = position - index
    first = capture_image(str(CAPTURE_PATHS[index]))
    second = capture_image(str(CAPTURE_PATHS[min(index + 1, len(CAPTURE_PATHS) - 1)]))
    available = (x2 - x1 - 28, y2 - y1 - 68)
    first_fit = ImageOps.contain(first, available, method=Image.Resampling.LANCZOS)
    second_fit = ImageOps.contain(second, available, method=Image.Resampling.LANCZOS)
    frame = Image.new("RGBA", available, (7, 12, 27, 255))
    frame.paste(first_fit, ((available[0] - first_fit.width) // 2, (available[1] - first_fit.height) // 2))
    if fraction > 0.01 and index + 1 < len(CAPTURE_PATHS):
        next_frame = Image.new("RGBA", available, (7, 12, 27, 0))
        next_frame.paste(second_fit, ((available[0] - second_fit.width) // 2, (available[1] - second_fit.height) // 2))
        next_frame.putalpha(int(255 * fraction))
        frame.alpha_composite(next_frame)
    image.alpha_composite(frame, (x1 + 14, y1 + 52))
    timeline_y = y2 + 25
    line(draw, (x1 + 40, timeline_y, x2 - 40, timeline_y), rgba(BORDER), 3)
    for dot_index in range(len(CAPTURE_PATHS)):
        dot_x = x1 + 40 + (x2 - x1 - 80) * dot_index / max(1, len(CAPTURE_PATHS) - 1)
        radius = 7 if dot_index == index else 4
        color = MINT if dot_index == index else DIM
        draw.ellipse((dot_x - radius, timeline_y - radius, dot_x + radius, timeline_y + radius), fill=rgba(color, 230))


def real_tetris_scene(layer: Image.Image, p: float) -> None:
    draw = ImageDraw.Draw(layer)
    scene_title(draw, "A concrete move", "Now watch the real game.", "Live board, queue, score, and verified placements.", y=125, headline_size=56)
    text(draw, (90, 335), "REAL APP", 18, fill=rgba(MINT), bold=True, mono=True)
    text(draw, (90, 390), "Jev Playing Tetris", 31, fill=rgba(TEXT), bold=True)
    text(draw, (90, 445), "The board changes one verified move at a time.", 21, fill=rgba(MUTED), spacing=5)
    steps = [("01", "read board state", BLUE), ("02", "choose a legal placement", PURPLE), ("03", "animate + lock", MINT)]
    for index, (number, label, color) in enumerate(steps):
        y = 545 + index * 94
        draw.ellipse((90, y, 136, y + 46), fill=rgba(color, 34), outline=rgba(color, 190), width=2)
        text(draw, (113, y + 23), number, 16, fill=rgba(color), anchor="mm", bold=True, mono=True)
        text(draw, (160, y + 7), label, 22, fill=rgba(TEXT), bold=True)
    pill(draw, (90, 860), "CAPTURED FROM THE RUNNING APP", fill=rgba(MINT, 30), outline=rgba(MINT, 145), color=rgba(MINT), size=17)
    paste_real_capture(layer, p)


def use_case_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str, description: str, color: tuple[int, int, int]) -> None:
    panel(draw, box, fill=rgba(CARD, 242), outline=rgba(color, 145), radius=22)
    x1, y1, x2, y2 = box
    draw.ellipse((x1 + 28, y1 + 28, x1 + 82, y1 + 82), fill=rgba(color, 40), outline=rgba(color, 190), width=2)
    text(draw, (x1 + 55, y1 + 55), label[0], 20, fill=rgba(color), anchor="mm", bold=True, mono=True)
    text(draw, (x1 + 112, y1 + 34), label, 17, fill=rgba(color), bold=True, mono=True)
    text(draw, (x1 + 112, y1 + 69), description, 24, fill=rgba(TEXT), bold=True)


def use_cases_scene(layer: Image.Image, p: float) -> None:
    draw = ImageDraw.Draw(layer)
    scene_title(draw, "The fit", "Where this clicks.", "Any loop that needs a judgment more often than it needs an explanation.")
    cards = [("ROUTE", "pick the next tool or subagent", PURPLE), ("RANK", "order tickets, candidates, or links", BLUE), ("VERIFY", "gate outputs and enforce guardrails", ORANGE), ("REACT", "make decisions inside real-time apps", MINT)]
    for index, (label, description, color) in enumerate(cards):
        x = 90 + (index % 2) * 910
        y = 335 + (index // 2) * 235
        local = ease_out(clamp((p - index * 0.12) * 4))
        shift = int((1 - local) * 80)
        use_case_card(draw, (x + shift, y, x + shift + 820, y + 165), label, description, color)
    text(draw, (90, 880), "Fast path when the answer space is known.", 26, fill=rgba(MUTED))


def built_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], name: str, tag: str, description: str, color: tuple[int, int, int]) -> None:
    panel(draw, box, fill=rgba(CARD, 242), outline=rgba(color, 155), radius=24)
    x1, y1, x2, y2 = box
    text(draw, (x1 + 30, y1 + 30), tag.upper(), 15, fill=rgba(color), bold=True, mono=True)
    text(draw, (x1 + 30, y1 + 92), name, 35, fill=rgba(TEXT), bold=True)
    text(draw, (x1 + 30, y1 + 154), description, 21, fill=rgba(MUTED))
    line(draw, (x1 + 30, y2 - 62, x2 - 30, y2 - 62), rgba(BORDER), 2)
    text(draw, (x1 + 30, y2 - 37), "STATE  →  ACTION", 15, fill=rgba(DIM), bold=True, mono=True)


def built_scene(layer: Image.Image, p: float) -> None:
    draw = ImageDraw.Draw(layer)
    scene_title(draw, "Already in motion", "The pattern is already showing up.", "Doom and Wikiracing are TypeSafe examples; Tetris makes the loop inspectable.", headline_size=56)
    built_card(draw, (90, 345, 650, 755), "DOOM", "TypeSafe example", "react to game state", RED)
    built_card(draw, (690, 345, 1250, 755), "WIKIRACING", "TypeSafe example", "choose among many links", BLUE)
    built_card(draw, (1290, 345, 1830, 755), "TETRIS", "this experiment", "choose a legal move, then verify it", MINT)
    text(draw, (90, 875), "Same primitive. Different world.", 29, fill=rgba(TEXT), bold=True)
    text(draw, (90, 920), "Give software a judgment it can actually use.", 22, fill=rgba(MUTED))


def ending_scene(layer: Image.Image, p: float) -> None:
    draw = ImageDraw.Draw(layer)
    text(draw, (WIDTH // 2, 165), "THE TAKEAWAY", 19, fill=rgba(MINT), anchor="ma", bold=True, mono=True)
    text(draw, (WIDTH // 2, 325), "Jev is not a chatbot.", 80, fill=rgba(TEXT), anchor="ma", bold=True)
    text(draw, (WIDTH // 2, 445), "It’s a decision layer.", 70, fill=rgba(MINT), anchor="ma", bold=True)
    boxes = [(420, "STATE", BLUE), (865, "JEV", MINT), (1310, "CODE", PURPLE)]
    y = 610
    for index, (x, label, color) in enumerate(boxes):
        draw.rounded_rectangle((x, y, x + 190, y + 82), radius=18, fill=rgba(color, 38), outline=rgba(color, 210), width=2)
        text(draw, (x + 95, y + 41), label, 21, fill=rgba(color), anchor="mm", bold=True, mono=True)
        if index < 2:
            arrow(draw, (x + 215, y + 41), (x + 420, y + 41), rgba(MUTED, 210), 4)
    pill(draw, (WIDTH // 2 - 133, 815), "BUILD THE FAST PATH", fill=rgba(MINT, 40), outline=rgba(MINT, 190), color=rgba(MINT), size=20)
    text(draw, (WIDTH // 2, 920), "typesafe.ai", 28, fill=rgba(TEXT), anchor="ma", bold=True, mono=True)
    text(draw, (WIDTH // 2, 965), "The future of AI software may need fewer words—and better judgments.", 21, fill=rgba(MUTED), anchor="ma")


SCENES = [
    (0.0, 4.7, "hook", intro_scene),
    (4.7, 12.5, "the shape", flow_scene),
    (12.5, 20.0, "primitives", primitives_scene),
    (20.0, 34.0, "real tetris", real_tetris_scene),
    (34.0, 43.0, "use cases", use_cases_scene),
    (43.0, 49.5, "examples", built_scene),
    (49.5, 55.0, "takeaway", ending_scene),
]


def render_frame(t: float) -> Image.Image:
    frame = new_frame(t)
    label = "JEV"
    for index, (start, end, scene_label, scene) in enumerate(SCENES):
        if start <= t < end or index == len(SCENES) - 1:
            local = clamp((t - start) / (end - start))
            layer = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            scene(layer, local)
            alpha = layer.getchannel("A").point(lambda value: int(value * scene_opacity(local)))
            layer.putalpha(alpha)
            frame.alpha_composite(layer)
            label = scene_label
            break
    chrome = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    chrome_draw = ImageDraw.Draw(chrome)
    draw_header(chrome_draw, label)
    draw_footer(chrome_draw, t, DURATION)
    frame.alpha_composite(chrome)
    return frame.convert("RGB")


def render_video(output: Path, poster: Path | None, fps: int, duration: float, audio: Path | None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    if audio is not None and not audio.exists():
        raise FileNotFoundError(f"Audio file not found: {audio}")
    video_output = output if audio is None else output.with_name(f".{output.stem}.silent{output.suffix}")
    command = [
        "ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{WIDTH}x{HEIGHT}", "-r", str(fps), "-i", "-", "-an", "-c:v", "libx264",
        "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(video_output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    total_frames = round(duration * fps)
    if poster is not None:
        poster.parent.mkdir(parents=True, exist_ok=True)
        render_frame(min(3.5, max(0.0, duration - 1.0 / fps))).save(poster, format="PNG", optimize=True)
    try:
        for frame_number in range(total_frames):
            frame = render_frame(frame_number / fps)
            assert process.stdin is not None
            process.stdin.write(frame.tobytes())
            if frame_number % fps == 0:
                print(f"rendered {frame_number / fps:05.1f}s / {duration:05.1f}s", flush=True)
        assert process.stdin is not None
        process.stdin.close()
        process.stdin = None
        return_code = process.wait()
    except BaseException:
        if process.stdin is not None:
            process.stdin.close()
        process.kill()
        process.wait()
        raise
    if return_code != 0:
        error = process.stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg failed with exit code {return_code}: {error}")
    if audio is None:
        return
    muxed_output = output.with_name(f".{output.stem}.muxed{output.suffix}")
    mux_command = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video_output), "-i", str(audio),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac",
        "-af", "loudnorm=I=-18:TP=-1.5:LRA=7", "-b:a", "160k", "-ar", "48000",
        "-shortest", "-movflags", "+faststart",
        str(muxed_output),
    ]
    try:
        subprocess.run(mux_command, check=True, capture_output=True)
        muxed_output.replace(output)
    except subprocess.CalledProcessError as error:
        details = error.stderr.decode("utf-8", errors="replace") if error.stderr else ""
        raise RuntimeError(f"ffmpeg audio mux failed: {details}") from error
    finally:
        if video_output.exists():
            video_output.unlink()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--poster", type=Path, default=DEFAULT_POSTER)
    parser.add_argument("--fps", type=int, default=FPS)
    parser.add_argument("--duration", type=float, default=DURATION)
    parser.add_argument("--audio", type=Path, default=None)
    parser.add_argument("--no-poster", action="store_true")
    args = parser.parse_args()
    if args.fps <= 0 or args.duration <= 0:
        raise SystemExit("fps and duration must be positive")
    render_video(args.output, None if args.no_poster else args.poster, args.fps, args.duration, args.audio)
    print(f"wrote {args.output}")
    if not args.no_poster:
        print(f"wrote {args.poster}")
    if args.audio is not None:
        print(f"audio {args.audio}")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(1)
