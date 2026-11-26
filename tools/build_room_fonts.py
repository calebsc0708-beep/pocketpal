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


# ---- walking between activities (must match Pal/PalActivity.swift) ----
# id: (back, flip, perch, floor, size)
ACTS = {
    "window": (True, False, (86, 79), (86, 112), 30),
    "music": (False, True, (109, 117), (109, 117), 33),
    "fish": (True, False, (205, 99), (158, 124), 30),
    "rug0": (False, False, (96, 132), (96, 132), 34),
    "rug1": (False, True, (122, 128), (122, 128), 34),
    "rug2": (False, False, (78, 126), (78, 126), 34),
}
# the activity cycle is window -> rug -> music -> fish -> window, so these are all the moves there are
WALKS = [("window", "rug0"), ("window", "rug1"), ("window", "rug2"), ("rug0", "music"), ("rug1", "music"),
         ("rug2", "music"), ("music", "fish"), ("fish", "window")]
WALK_SPEED = 11          # room px per second on the floor
FLOOR_SIZE = 33          # canvas size (room px) while walking on the floor


def walk_path(a, b):
    """Positions (x, y, size, moving_dx, moving_dy) for each second of the walk, start to arrival."""
    _, _, pa, fa, sa = ACTS[a]
    _, _, pb, fb, sb = ACTS[b]
    pts = []   # waypoints: (x, y, size, kind)
    pts.append((*pa, sa, "start"))
    if pa != fa: pts.append((*fa, FLOOR_SIZE, "jump"))       # hop down from the perch
    pts.append((*fb, FLOOR_SIZE, "walk"))
    if pb != fb: pts.append((*pb, sb, "jump"))               # hop up onto the next perch
    else: pts[-1] = (*pb, sb, "walk")
    out = [(pa[0], pa[1], sa, 0.0, 0.0)]                     # one beat where it was, so it starts from there
    for (x0, y0, s0, _), (x1, y1, s1, kind) in zip(pts, pts[1:]):
        dist = math.hypot(x1 - x0, y1 - y0)
        n = 2 if kind == "jump" else max(1, math.ceil(dist / WALK_SPEED))
        for k in range(1, n + 1):
            f = k / n
            lift = math.sin(f * math.pi) * (10 if kind == "jump" else 0)
            out.append((x0 + (x1 - x0) * f, y0 + (y1 - y0) * f - lift, s0 + (s1 - s0) * f, x1 - x0, y1 - y0))
    return out


def pal_glyph(img, x, y, size, m, flip):
    """The pal's 68 px canvas drawn `size` room px tall with its feet at (x, y), in an em of 256 room px.
    Returns (png bytes, offset) — the picture is just the pal, placed with the sbix origin offset."""
    if flip: img = img.transpose(Image.FLIP_LEFT_RIGHT)
    side = max(1, round(size * img.width / 68 * m))
    pic = img.resize((side, side), Image.NEAREST)
    bb = pic.getbbox() or (0, 0, 1, 1)
    left = round(x * m - side / 2); top = round(y * m - side)
    pic = pic.crop(bb)
    ox = left + bb[0]; bottom = top + bb[3]
    return png(pic), (ox, 256 * m - bottom)


def walk_font(species, a, b):
    """60 seconds after the 5-minute mark: the walk from activity a to b, then b's idle loop.
    After the first minute the font shows b's idle loop (same frame as the idle font: seconds mod 10)."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables.sbixStrike import Strike
    from fontTools.ttLib.tables.sbixGlyph import Glyph as SbixGlyph
    path = walk_path(a, b)
    assert len(path) < 50, (a, b, len(path))
    loops = {c: sum(f["ms"] for f in FRAMES[species][c]["frames"]) for c in ("front", "back")}
    def pose(clip, k):   # idle frame k of 10, like the idle fonts
        return frame_image(frame_at(species, clip, k * loops[clip] / 10))
    bback, bflip, bperch, _, bsize = ACTS[b]
    glyphs = {}          # name -> {m: (png, offset)}
    for s, (x, y, size, dx, dy) in enumerate(path):
        back = dy < 0 and abs(dy) >= abs(dx) * 0.25          # walking away from you: show the back
        clip = "back" if back else "front"
        art_faces_right = back                               # front art faces left, back art faces right
        if s == 0:                                           # still doing the old activity: same pose as before
            aback, aflip = ACTS[a][0], ACTS[a][1]
            clip, flip = ("back" if aback else "front"), aflip
        else:
            flip = (dx > 0) != art_faces_right if abs(dx) > 0.5 else False
        glyphs[f"w{s:02d}"] = {m: pal_glyph(pose(clip, s % 10), x, y, size, m, flip) for m in (2, 4)}
    for k in range(10):
        glyphs[f"i{k}"] = {m: pal_glyph(pose("back" if bback else "front", k), bperch[0], bperch[1], bsize, m, bflip)
                           for m in (2, 4)}
    W = len(path)
    names = list(glyphs)
    glyph_order = list(EMPTY.keys()) + DIGITS + ["zw"] + names
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
    name = f"PokePal-{species}-walk-{a}-{b}"
    fb.setupNameTable({"familyName": name.replace("-", " "), "styleName": "Regular", "fullName": name.replace("-", " "),
                       "psName": name, "uniqueFontIdentifier": name})
    fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, sTypoLineGap=0, usWinAscent=UPM, usWinDescent=0,
                sxHeight=UPM // 2, sCapHeight=UPM, fsType=0)
    fb.setupPost()
    sbix = newTable("sbix"); sbix.version = 1; sbix.flags = 1
    for m in (2, 4):
        strike = Strike(ppem=256 * m, resolution=72)
        for g in names:
            data, (ox, oy) = glyphs[g][m]
            strike.glyphs[g] = SbixGlyph(glyphName=g, graphicType="png ", imageData=data, originOffsetX=ox, originOffsetY=oy)
        sbix.strikes[256 * m] = strike
    fb.font["sbix"] = sbix
    # The timer counts from the 5-minute mark: "0:SS" in the first minute, "M:SS" after.
    D = DIGITS
    rules = []
    for t in range(60):                                      # first minute: walk, then idle at b
        g = f"w{t:02d}" if t < W else f"i{t % 10}"
        rules.append(f"    sub {D[0]} colon {D[t // 10]} {D[t % 10]} by {g};")
    for mnt in range(1, 10):                                 # after that: idle at b (seconds mod 10)
        for t in range(60):
            rules.append(f"    sub {D[mnt]} colon {D[t // 10]} {D[t % 10]} by i{t % 10};")
    fea = f"""
languagesystem DFLT dflt;
languagesystem latn dflt;
@ANY = [{" ".join(DIGITS + SEPARATORS)}];
lookup KeepLastFour {{
    sub @ANY' @ANY @ANY @ANY @ANY by zw;
}} KeepLastFour;
lookup Pick {{
{chr(10).join(rules)}
}} Pick;
feature ccmp {{ lookup KeepLastFour; lookup Pick; }} ccmp;
feature calt {{ lookup KeepLastFour; lookup Pick; }} calt;
"""
    addOpenTypeFeaturesFromString(fb.font, fea)
    fb.save(str(OUT / f"{name}.ttf"))
    return f"{name}.ttf", W


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    files = []
    for species in FRAMES:
        files.append(idle_font(species, "front"))
        files.append(idle_font(species, "back"))
        files.append(hop_font(species))
        secs = []
        for a, b in WALKS:
            f, w = walk_font(species, a, b); files.append(f); secs.append(w)
        print(f"  {species}: idle, back, hop + {len(WALKS)} walks ({min(secs)}-{max(secs)} s)")
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
