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
from build_room_fonts import build_font, OUT, PLIST, UPM, DIGITS, EMPTY, SEPARATORS   # noqa: E402

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
    """PNG bytes. Pixel art rarely has more than 256 colours, so store it with a palette when it fits:
    exactly the same pixels, a fraction of the size."""
    import numpy as np
    img = img.convert("RGBA")
    a = np.asarray(img)
    packed = np.ascontiguousarray(a).view(np.uint32).reshape(-1)        # one number per pixel: fast to sort
    packed = np.where(a[..., 3].reshape(-1) == 0, 0, packed)           # all fully clear pixels are the same colour
    uniq, idx = np.unique(packed, return_inverse=True)
    cols = uniq.view(np.uint8).reshape(-1, 4)
    b = io.BytesIO()
    if len(cols) <= 256:
        p = Image.fromarray(idx.reshape(a.shape[:2]).astype(np.uint8), "P")
        p.putpalette(cols[:, :3].astype(np.uint8).flatten().tolist())
        p.save(b, "PNG", optimize=True, transparency=bytes(cols[:, 3].astype(np.uint8).tolist()))
    else:
        img.save(b, "PNG", optimize=True)
    return b.getvalue()


def asset(name):
    return Image.open(ASSETS / f"{name}.imageset" / f"{name}.png").convert("RGBA")


def upscale_square(overlay, side, origin, scales):
    """overlay: RGBA in room px. Crop a side x side square at origin, scale by each factor (nearest)."""
    sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    sq.alpha_composite(overlay.crop((origin[0], origin[1], origin[0] + side, origin[1] + side)))
    return {side * m: sq.resize((side * m, side * m), Image.NEAREST) for m in scales}


FRONT = np.asarray(Image.open(Path(__file__).parent / "fx" / "front_mask.png").convert("L")) > 0

FX_FRAMES = 60   # the room effects loop over a whole minute (every motion fits it exactly: ambience.LOOP)


def build_font60(ps_name, strikes, out_path, offsets=None):
    """Like build_font, but picks one of 60 pictures from the timer's last TWO digits (its seconds, 00-59).
    strikes: {ppem: [60 PNG byte strings]}; offsets: {ppem: (x, y)} where each picture sits (px from the
    glyph's bottom-left), so pictures can be just the part of the square that moves."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables.sbixStrike import Strike
    from fontTools.ttLib.tables.sbixGlyph import Glyph as SbixGlyph
    from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
    # identical pictures are stored once: second n shows glyph slot[n]
    first = next(iter(strikes.values()))
    uniq, slot = {}, []
    for n in range(60):
        key = tuple(strikes[p][n] for p in strikes)
        slot.append(uniq.setdefault(key, len(uniq)))
    frames = [f"f{k:02d}" for k in range(len(uniq))]
    rep = {k: slot.index(k) for k in range(len(uniq))}       # a second that shows glyph k
    glyph_order = list(EMPTY.keys()) + DIGITS + ["zw"] + frames
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    cmap = {ord(ch): g for g, ch in EMPTY.items() if ch}
    cmap.update({ord(str(i)): g for i, g in enumerate(DIGITS)})
    fb.setupCharacterMap(cmap)
    empty = TTGlyphPen(None).glyph()
    fb.setupGlyf({g: empty for g in glyph_order})
    zero_width = set(SEPARATORS) | {"zw"} | set(DIGITS)
    fb.setupHorizontalMetrics({g: (0 if g in zero_width else UPM, 0) for g in glyph_order})
    fb.setupHorizontalHeader(ascent=UPM, descent=0, lineGap=0)
    fb.setupNameTable({"familyName": ps_name.replace("-", " "), "styleName": "Regular",
                       "fullName": ps_name.replace("-", " "), "psName": ps_name, "uniqueFontIdentifier": ps_name})
    fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, sTypoLineGap=0, usWinAscent=UPM,
                usWinDescent=0, sxHeight=UPM // 2, sCapHeight=UPM, fsType=0)
    fb.setupPost()
    sbix = newTable("sbix"); sbix.version = 1; sbix.flags = 1
    for ppem, images in strikes.items():
        strike = Strike(ppem=ppem, resolution=72)
        for k, gname in enumerate(frames):
            ox, oy = (offsets or {}).get(ppem, (0, 0))
            strike.glyphs[gname] = SbixGlyph(glyphName=gname, graphicType="png ", imageData=images[rep[k]],
                                             originOffsetX=ox, originOffsetY=oy)
        sbix.strikes[ppem] = strike
    fb.font["sbix"] = sbix
    ligs = "\n".join(f"    sub {DIGITS[a]} {DIGITS[b]} by f{slot[a * 10 + b]:02d};" for a in range(6) for b in range(10))
    fea = f"""
languagesystem DFLT dflt;
languagesystem latn dflt;
@ANY = [{" ".join(DIGITS + SEPARATORS)}];
lookup HideAllButLastTwo {{
    sub @ANY' @ANY @ANY by zw;
}} HideAllButLastTwo;
lookup Seconds {{
{ligs}
}} Seconds;
feature ccmp {{ lookup HideAllButLastTwo; lookup Seconds; }} ccmp;
feature calt {{ lookup HideAllButLastTwo; lookup Seconds; }} calt;
"""
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(str(out_path))
    return out_path.name


def room_fx(time, weather):
    base = asset(f"room_{time}_{weather}")
    info = json.loads((ROOMS / f"room_{time}_{weather}.json").read_text())
    saved = ambience.lights_on
    ambience.lights_on = lambda a, b: False                   # lights have their own font
    frames = []
    for d in range(FX_FRAMES):
        f = ambience.draw2(base, float(d), time, weather, info, clock=None)
        a, b = np.asarray(f).astype(np.int16), np.asarray(base).astype(np.int16)
        changed = np.abs(a[..., :3] - b[..., :3]).max(axis=2) > 0
        solid = np.abs(a[..., :3] - b[..., :3]).max(axis=2) > 45      # a drawn pixel, not just light
        changed &= ~(FRONT & solid)                         # the desk chair / floor plant are in front of those
        ov = np.zeros_like(np.asarray(f)); ov[changed] = np.asarray(f)[changed]
        ov[changed, 3] = 255
        frames.append(Image.fromarray(ov))
    ambience.lights_on = saved
    # only keep the part of the room that ever changes (window, desk, tank, plant...): smaller pictures
    # to store and, more importantly, to decode every second on the Home Screen
    union = np.zeros((160, 256), bool)
    for img in frames:
        union |= np.asarray(img)[..., 3] > 0
    ys, xs = np.nonzero(union)
    x0, y0, x1, y1 = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1) if len(xs) else (0, 0, 1, 1)
    strikes, offsets = {}, {}
    for img in frames:
        part = img.crop((x0, y0, x1, y1))
        for m in (2, 4):
            ppem = 256 * m
            strikes.setdefault(ppem, []).append(png(part.resize(((x1 - x0) * m, (y1 - y0) * m), Image.NEAREST)))
            offsets[ppem] = (x0 * m, (256 - y1) * m)          # picture's bottom-left, up from the square's bottom
    name = f"PokePal-fx-{time}-{weather}"
    return build_font60(name, strikes, OUT / f"{name}.ttf", offsets)


# ---- the pal asleep under the covers (widget): breathing lump + Zs floating up, once a second ----
COVERS_ORIGIN, COVERS_SIZE = (204, 82), (36, 20)     # must match PalSleepLayer in Pal/PalRoomView.swift
LUMP_X = 216
Z_COLOR = (255, 248, 225)


def sleep_frame(weather, wide, t):
    img = Image.new("RGBA", (256, 160), (0, 0, 0, 0))
    breath = 1 if t % 4 in (1, 2) else 0                       # 2 s in, 2 s out
    img.alpha_composite(asset(f"covers{'w' if wide else ''}{breath}_night_{weather}"), COVERS_ORIGIN)
    px = img.load()
    for i in range(3):                                         # three Zs, a third of the way apart
        p = (t / 10 + i / 3) % 1                               # each takes 10 s to float up; the 3 never line up, so it reads as drifting
        size = 2 + i % 2 + round(p * 2)
        x = LUMP_X + 6 + round(p * 10 + math.sin(p * 6 + i) * 1.5)
        y = 84 - round(p * 22)
        a = min(1, p / 0.15) * min(1, (1 - p) / 0.3)
        if a <= 0.05:
            continue
        for k in range(size + 1):
            for (zx, zy) in ((x + k, y), (x + k, y + size), (x + size - k, y + k)):
                if 0 <= zx < 256 and 0 <= zy < 160:
                    b = px[zx, zy]
                    # blend over whatever is there (the quilt / clear) so faint Zs look faint
                    na = a + b[3] / 255 * (1 - a)
                    c = tuple(round((Z_COLOR[j] * a + b[j] * b[3] / 255 * (1 - a)) / max(na, 1e-6)) for j in range(3))
                    px[zx, zy] = c + (round(na * 255),)
    return img


def sleep_font(weather, wide):
    frames = [sleep_frame(weather, wide, t) for t in range(FX_FRAMES)]
    union = np.zeros((160, 256), bool)
    for f in frames:
        union |= np.asarray(f)[..., 3] > 0
    ys, xs = np.nonzero(union)
    x0, y0, x1, y1 = int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1
    strikes, offsets = {}, {}
    for f in frames:
        part = f.crop((x0, y0, x1, y1))
        for m in (2, 4):
            strikes.setdefault(256 * m, []).append(png(part.resize(((x1 - x0) * m, (y1 - y0) * m), Image.NEAREST)))
            offsets[256 * m] = (x0 * m, (256 - y1) * m)
    name = f"PokePal-sleep{'w' if wide else ''}-{weather}"
    return build_font60(name, strikes, OUT / f"{name}.ttf", offsets)


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
    for w in WEATHERS:                       # asleep (night only), normal and wide room
        files.append(sleep_font(w, False))
        files.append(sleep_font(w, True))
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
