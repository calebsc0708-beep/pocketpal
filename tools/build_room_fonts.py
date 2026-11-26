#!/usr/bin/env python3
"""
Frame fonts for the PokePal room widget. Run AFTER tools/build_pals.py and tools/build_sprites.py (it wipes Generated/).

Home Screen widgets can't animate, so this uses the same trick as the Dynamic Island:
a running timer drawn in a font whose digits 0-9 are pictures. The seconds digit changes
once a second, so the picture does too (10 pictures, 10-second loop).

For each pal it builds:
  PokePal-<pal>-idle   10 frames of the pal's idle animation, front view (square, just the pal)
  PokePal-<pal>-back   the same from behind (for activities where it faces away from you)
  PokePal-<pal>-hop    10 pictures of the pal standing at 10 spots on the room floor,
                       covering room x 20..180, y 0..160 (a 160x160 square of the room)

Then it adds the fonts to Support/Widget-Info.plist and lets the widget use your location.
"""
import io
import json
import math
import plistlib
from pathlib import Path

from PIL import Image
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables.sbixGlyph import Glyph as SbixGlyph
from fontTools.ttLib.tables.sbixStrike import Strike

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "PalGen" / "PalFrames.xcassets"          # made by tools/build_pals.py
FRAMES = json.loads((ROOT / "PalGen" / "pal_frames.json").read_text())
OUT = ROOT / "Generated" / "Fonts"
PLIST = ROOT / "Support" / "Widget-Info.plist"

# ---- must match Widget/RoomWidget.swift ----
HOP_ORIGIN = (20, 0)       # top-left of the hop glyph square, in room px
HOP_SIDE = 160             # the square covers 160x160 room px
PAL_ROOM_SIZE = 34         # a 68 px canvas is drawn 34 room px tall (half size); bigger canvases scale up
def spot(k):               # 10 spots in a loop around the rug (feet position, room px)
    a = 2 * math.pi * k / 10
    return (102 + 40 * math.cos(a), 128 + 12 * math.sin(a))

UPM = 1000
DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
EMPTY = {".notdef": None, "space": " ", "colon": ":", "hyphen": "-", "period": "."}
SEPARATORS = ["space", "colon", "hyphen", "period"]
# Same as build_sprites.py: every digit followed by another character becomes a zero-width
# blank, so a running timer like "1:23:45" draws as one picture (the last digit).
FEATURES = """
languagesystem DFLT dflt;
languagesystem latn dflt;
@DIGIT = [zero one two three four five six seven eight nine];
@ANY = [zero one two three four five six seven eight nine space colon hyphen period];
lookup HideAllButLast {
    sub @DIGIT' @ANY by zw;
} HideAllButLast;
feature ccmp { lookup HideAllButLast; } ccmp;
feature calt { lookup HideAllButLast; } calt;
"""


def frame_image(name):
    return Image.open(ASSETS / f"{name}.imageset" / f"{name}.png").convert("RGBA")


def frame_at(species, clip, t_ms):
    seq = FRAMES[species][clip]["frames"]
    total = sum(f["ms"] for f in seq)
    t = t_ms % total
    for f in seq:
        if t < f["ms"]:
            return f["image"]
        t -= f["ms"]
    return seq[0]["image"]


def build_font(ps_name, strikes, out_path):
    """strikes: {ppem: [10 PNG byte strings, one per digit]}"""
    glyph_order = list(EMPTY.keys()) + DIGITS + ["zw"]
    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    cmap = {ord(ch): g for g, ch in EMPTY.items() if ch}
    cmap.update({ord(str(i)): g for i, g in enumerate(DIGITS)})
    fb.setupCharacterMap(cmap)
    empty = TTGlyphPen(None).glyph()
    fb.setupGlyf({g: empty for g in glyph_order})
    zero_width = set(SEPARATORS) | {"zw"}
    fb.setupHorizontalMetrics({g: (0 if g in zero_width else UPM, 0) for g in glyph_order})
    fb.setupHorizontalHeader(ascent=UPM, descent=0, lineGap=0)
    fb.setupNameTable({"familyName": ps_name.replace("-", " "), "styleName": "Regular",
                       "fullName": ps_name.replace("-", " "), "psName": ps_name,
                       "uniqueFontIdentifier": ps_name})
    fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, sTypoLineGap=0, usWinAscent=UPM,
                usWinDescent=0, sxHeight=UPM // 2, sCapHeight=UPM, fsType=0)
    fb.setupPost()
    sbix = newTable("sbix"); sbix.version = 1; sbix.flags = 1
    for ppem, images in strikes.items():
        strike = Strike(ppem=ppem, resolution=72)
        for d, gname in enumerate(DIGITS):
            strike.glyphs[gname] = SbixGlyph(glyphName=gname, graphicType="png ", imageData=images[d],
                                             originOffsetX=0, originOffsetY=0)
        sbix.strikes[ppem] = strike
    fb.font["sbix"] = sbix
    addOpenTypeFeaturesFromString(fb.font, FEATURES)
    fb.save(str(out_path))
    return out_path.name


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


def idle_font(species, clip="front"):
    loop = sum(f["ms"] for f in FRAMES[species][clip]["frames"])
    frames = [frame_image(frame_at(species, clip, d * loop / 10)) for d in range(10)]
    side = frames[0].width                        # 68
    strikes = {side * m: [png(f.resize((side * m, side * m), Image.NEAREST)) for f in frames] for m in (1, 2, 3, 4)}
    name = f"PokePal-{species}-{'idle' if clip == 'front' else 'back'}"
    return build_font(name, strikes, OUT / f"{name}.ttf")


def hop_pictures(species, px_per_room):
    """10 pictures: pal at spot k, facing the way it hops next, idle frame advancing."""
    loop = sum(f["ms"] for f in FRAMES[species]["front"]["frames"])
    pics = []
    for k in range(10):
        (x, y), (nx, ny) = spot(k), spot((k + 1) % 10)
        dx, dy = nx - x, ny - y
        back = dy < 0 and abs(dy) >= abs(dx) * 0.25           # hopping away from you: show the back
        clip = "back" if back else "front"
        img = frame_image(frame_at(species, clip, k * loop / 10))
        facing = "right" if back else "left"                   # which way the art faces
        moving_right = dx > 0
        if (facing == "left" and moving_right) or (facing == "right" and not moving_right):
            img = img.transpose(Image.FLIP_LEFT_RIGHT)
        side = round(PAL_ROOM_SIZE * img.width / 68 * px_per_room)
        img = img.resize((side, side), Image.NEAREST)
        canvas = Image.new("RGBA", (HOP_SIDE * px_per_room, HOP_SIDE * px_per_room), (0, 0, 0, 0))
        left = round((x - HOP_ORIGIN[0]) * px_per_room - side / 2)
        top = round((y - HOP_ORIGIN[1]) * px_per_room - side)
        canvas.alpha_composite(img, (left, top))
        pics.append(canvas)
    return pics


def hop_font(species):
    # 2, 4 and 8 image px per room px: the pal lands on 1x, 2x and 4x its own pixels, so it stays crisp
    strikes = {HOP_SIDE * m: [png(p) for p in hop_pictures(species, m)] for m in (2, 4, 8)}
    return build_font(f"PokePal-{species}-hop", strikes, OUT / f"PokePal-{species}-hop.ttf")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for species in FRAMES:
        files.append(idle_font(species, "front"))
        files.append(idle_font(species, "back"))
        files.append(hop_font(species))
        print(f"  {species}: idle, back + hop fonts")
    plist = plistlib.loads(PLIST.read_bytes()) if PLIST.exists() else {}
    fonts = plist.get("UIAppFonts", [])
    fonts += [f"Fonts/{f}" for f in files if f"Fonts/{f}" not in fonts]
    plist["UIAppFonts"] = fonts
    plist["NSWidgetWantsLocation"] = True                       # so the widget can match your weather
    PLIST.parent.mkdir(exist_ok=True)
    PLIST.write_bytes(plistlib.dumps(plist))
    print(f"Done: {len(files)} room font(s)")


if __name__ == "__main__":
    main()
