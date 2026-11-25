#!/usr/bin/env python3
"""
Once-a-second effect fonts for the room widget. Run after tools/build_room_fonts.py.

Like the pal, each font has 10 pictures (digits 0-9) shown one per second by a running timer:
  PokePal-fx-<time>-<weather>   everything that moves in that room look: clouds, rain/snow, stars,
                                lightning, dust, candle, steam, music notes + record, plant, fish + bubbles
                                (a 256x256 square over the room, top-left corner at the room's top-left)
  PokePal-lights-<palette>      the string lights twinkling (default, or a holiday's colors)
  PokePal-balloons-<holiday>    New Year's / Valentine's balloons bobbing (square at room x160, y48, 56 wide)
The clock is not included: the widget draws it once a minute.
"""
import io
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "fx"))
sys.path.insert(0, str(ROOT / "tools"))
import ambience                                   # noqa: E402  (Python copy of PalRoomAmbience)
from build_room_fonts import build_font, OUT, PLIST   # noqa: E402

import plistlib                                   # noqa: E402

ASSETS = ROOT / "Pal" / "PalSprites.xcassets"
ROOMS = ROOT / "tools" / "fx" / "rooms"
TIMES = ["sunrise", "day", "sunset", "night"]
WEATHERS = ["clear", "cloudy", "rain", "storm", "snow"]

# must match Pal/RoomDecorations.swift
PALETTES = {
    "default": [(255, 200, 120), (255, 170, 140), (255, 226, 150)],
    "halloween": [(255, 150, 40), (170, 90, 230), (120, 230, 90)],
    "autumn": [(255, 190, 90), (240, 130, 60), (255, 220, 130)],
    "christmas": [(255, 70, 70), (80, 220, 110), (255, 210, 90)],
    "newyear": [(255, 215, 100), (220, 220, 255), (255, 240, 180)],
    "valentine": [(255, 110, 150), (255, 180, 200), (240, 60, 90)],
}
BALLOON_ORIGIN, BALLOON_SIDE = (160, 48), 56
# the wide room (rectangle widget) is 344 px wide: its extra bulbs past x 256 get their own strip font
WIDE_W, STRIP_ORIGIN, STRIP_SIDE = 344, (256, 0), 88
WIDE_BULBS = [(x, 14 + 3 + int(5 * abs(math.sin((x - 44) / 42 * math.pi))) + 1) for x in range(264, WIDE_W, 10)]


def png(img):
    b = io.BytesIO(); img.save(b, "PNG", optimize=True); return b.getvalue()


def asset(name):
    return Image.open(ASSETS / f"{name}.imageset" / f"{name}.png").convert("RGBA")


def upscale_square(overlay, side, origin, scales):
    """overlay: RGBA in room px. Crop a side x side square at origin, scale by each factor (nearest)."""
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(overlay.crop((origin[0], origin[1], origin[0] + side, origin[1] + side)))
    return {side * m: sq.resize((side * m, side * m), Image.NEAREST) for m in scales}


FRONT = np.asarray(Image.open(Path(__file__).parent / "fx" / "front_mask.png").convert("L")) > 0


def room_fx(time, weather):
    base = asset(f"room_{time}_{weather}")
    info = json.loads((ROOMS / f"room_{time}_{weather}.json").read_text())
    saved = ambience.lights_on
    ambience.lights_on = lambda a, b: False                   # lights have their own font
    frames = []
    for d in range(10):
        f = ambience.draw2(base, float(d), time, weather, info, clock=None)
        a, b = np.asarray(f).astype(np.int16), np.asarray(base).astype(np.int16)
        changed = np.abs(a[..., :3] - b[..., :3]).max(axis=2) > 0
        solid = np.abs(a[..., :3] - b[..., :3]).max(axis=2) > 45      # a drawn pixel, not just light
        changed &= ~(FRONT & solid)                         # the desk chair / floor plant are in front of those
        ov = np.zeros_like(np.asarray(f)); ov[changed] = np.asarray(f)[changed]
        ov[changed, 3] = 255
        frames.append(Image.fromarray(ov))
    ambience.lights_on = saved
    strikes = {}
    for img in frames:
        for ppem, im in upscale_square(img, 256, (0, 0), (2, 4)).items():
            strikes.setdefault(ppem, []).append(png(im))
    name = f"PokePal-fx-{time}-{weather}"
    return build_font(name, strikes, OUT / f"{name}.ttf")


def lights(palette_name, strip=False):
    pal = PALETTES[palette_name]
    holiday = palette_name != "default"
    strikes = {}
    W = WIDE_W if strip else 256
    bulbs = WIDE_BULBS if strip else ambience.BULBS
    first = len(ambience.BULBS) if strip else 0          # keep each bulb's twinkle phase in step
    for d in range(10):
        ov = Image.new("RGBA", (W, 160), (0, 0, 0, 0)); px = ov.load()
        def put(x, y, c, a):
            if 0 <= x < W and 0 <= y < 160 and a > 0:
                r, g, b, al = px[x, y]
                na = a + al / 255 * (1 - a)
                px[x, y] = tuple(int((c[k] * a + (r, g, b)[k] * al / 255 * (1 - a)) / max(na, 1e-6)) for k in range(3)) + (int(na * 255),)
        for i, (x, y) in enumerate(bulbs, start=first):
            a = 0.5 + 0.5 * math.sin(2 * math.pi * 3 * d / 10 + i * 1.7)   # loops cleanly every 10 seconds
            c = pal[i % 3]
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 2), (-1, 1), (1, 1)]:
                put(x + dx, y + dy, c, 0.35 * a)
            if holiday:
                put(x, y, c, 1); put(x, y + 1, c, 1)                     # recolor the bulb itself
                put(x, y, (255, 255, 255), 0.35 * a)
            else:
                put(x, y, (255, 250, 230), 0.6 * a); put(x, y + 1, (255, 250, 230), 0.6 * a)
        sq = upscale_square(ov, STRIP_SIDE, STRIP_ORIGIN, (2, 4)) if strip else upscale_square(ov, 256, (0, 0), (2, 4))
        for ppem, im in sq.items():
            strikes.setdefault(ppem, []).append(png(im))
    name = f"PokePal-lights{'R' if strip else ''}-{palette_name}"
    return build_font(name, strikes, OUT / f"{name}.ttf")


def balloons(holiday, items):
    strikes = {}
    for d in range(10):
        ov = Image.new("RGBA", (256, 160), (0, 0, 0, 0))
        for b in items:
            dy = round(math.sin(2 * math.pi * d / 5 + b["phase"]) * 1.2)       # bob up and down
            dx = round(math.sin(2 * math.pi * d / 10 + b["phase"]) * 1.0)      # drift side to side
            ov.alpha_composite(asset(b["image"]), (b["x"] + dx, b["y"] + dy))
        for ppem, im in upscale_square(ov, BALLOON_SIDE, BALLOON_ORIGIN, (4, 8)).items():
            strikes.setdefault(ppem, []).append(png(im))
    name = f"PokePal-balloons-{holiday}"
    return build_font(name, strikes, OUT / f"{name}.ttf")


def main():
    files = []
    for t in TIMES:
        for w in WEATHERS:
            files.append(room_fx(t, w))
    for p in PALETTES:
        files.append(lights(p))
        files.append(lights(p, strip=True))
    for hol, items in json.loads((ROOT / "tools" / "fx" / "balloons.json").read_text()).items():
        files.append(balloons(hol, items))
    plist = plistlib.loads(PLIST.read_bytes())
    fonts = plist.get("UIAppFonts", [])
    fonts += [f"Fonts/{f}" for f in files if f"Fonts/{f}" not in fonts]
    plist["UIAppFonts"] = fonts
    PLIST.write_bytes(plistlib.dumps(plist))
    total = sum((OUT / f).stat().st_size for f in files)
    print(f"Done: {len(files)} effect font(s), {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
