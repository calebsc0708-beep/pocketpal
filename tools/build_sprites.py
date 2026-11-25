#!/usr/bin/env python3
"""
Pocket Pal sprite pipeline. Run from the project root:  python3 tools/build_sprites.py

Reads everything in Sprites/ and writes ready-to-use files to Generated/:

  Inputs it understands
    name.png                    still sprite
    name_1.png, name_2.png ...  animation frames
    name.gif                    animated GIF (split into frames automatically)
    name.sheet.png              sprite sheet: frames side by side (or stacked)
    sprites.json                optional per-sprite settings (see README)

  What it does to every sprite
    - removes a solid background (white, black, any flat color) if there's no transparency
    - trims empty space, using ONE shared box for all frames so animations don't jitter
    - makes it square (centered, sitting on the bottom edge)
    - pixel art stays at its native size; big images become 192x192

  What it builds
    Generated/Sprites/          cleaned sprites + sprites.json (bundled into the app)
    Generated/Fonts/            "frame fonts" that make sprites animate / move in the Dynamic Island
    Generated/preview.png       a sheet showing every sprite and frame
    Support/Widget-Info.plist   registers the fonts with the widget
"""
import io
import json
import math
import plistlib
import shutil
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps, ImageSequence
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables.sbixGlyph import Glyph as SbixGlyph
from fontTools.ttLib.tables.sbixStrike import Strike

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "Sprites"
GEN = ROOT / "Generated"
OUT_SPRITES = GEN / "Sprites"
OUT_FONTS = GEN / "Fonts"
SUPPORT = ROOT / "Support"

PIXEL_ART_MAX = 128     # sprites this small (after trimming) are treated as pixel art
BIG_SIZE = 192          # size for non-pixel-art sprites
WORK_MAX = 512          # big inputs are shrunk to this before processing (speed)

# ----------------------------------------------------------------------------- helpers

def safe(name: str) -> str:
    """Must match Sprites.fontID(_:) in Shared/PetAttributes.swift."""
    s = "".join(c for c in name if c.isascii() and c.isalnum())
    return s or "sprite"


def warn(msg):
    print(f"    ! {msg}")


def load_settings():
    path = SRC / "sprites.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        warn(f"sprites.json couldn't be read ({e}); ignoring it")
        return {}

# ----------------------------------------------------------------------------- collecting inputs

def pick_evenly(frames, count):
    if len(frames) <= count:
        return frames
    return [frames[round(i * (len(frames) - 1) / (count - 1))] if count > 1 else frames[0]
            for i in range(count)]


def best_frame_count(n):
    """Largest of 10/5/2 that's <= n, so loops are seamless with the 10-second timer."""
    for c in (10, 5, 2):
        if n >= c:
            return c
    return 1


def gather():
    """Returns {name: [PIL frames]} for every sprite in Sprites/."""
    sprites, numbered = {}, {}
    for p in sorted(SRC.iterdir()):
        if p.name.startswith(".") or not p.is_file():
            continue
        ext = p.suffix.lower()
        try:
            if ext == ".gif":
                frames = [f.convert("RGBA") for f in ImageSequence.Iterator(Image.open(p))]
                count = best_frame_count(len(frames))
                if count != len(frames):
                    print(f"  {p.name}: {len(frames)} GIF frames -> using {count} (loops cleanly)")
                sprites[p.stem] = pick_evenly(frames, count)
            elif ext == ".png" and p.stem.lower().endswith(".sheet"):
                name = p.stem[: -len(".sheet")]
                sheet = Image.open(p).convert("RGBA")
                w, h = sheet.size
                if w >= h:
                    n = max(1, round(w / h)); fw = w / n
                    frames = [sheet.crop((round(i * fw), 0, round((i + 1) * fw), h)) for i in range(n)]
                else:
                    n = max(1, round(h / w)); fh = h / n
                    frames = [sheet.crop((0, round(i * fh), w, round((i + 1) * fh))) for i in range(n)]
                print(f"  {p.name}: sprite sheet split into {n} frames")
                if n not in (1, 2, 5, 10):
                    warn(f"{n} frames doesn't divide 10; the loop will hiccup. 2, 5 or 10 loop perfectly.")
                sprites[name] = frames
            elif ext == ".png":
                base, sep, num = p.stem.rpartition("_")
                if sep and base and num.isdigit():
                    numbered.setdefault(base, []).append((int(num), Image.open(p).convert("RGBA")))
                else:
                    sprites[p.stem] = [Image.open(p).convert("RGBA")]
        except Exception as e:
            warn(f"skipped {p.name}: {e}")
    for base, items in numbered.items():
        frames = [im for _, im in sorted(items, key=lambda t: t[0])]
        if base in sprites:
            warn(f"'{base}' exists twice (numbered frames and another file); using the numbered frames")
        if len(frames) not in (1, 2, 5, 10):
            warn(f"{base}: {len(frames)} frames doesn't divide 10; the loop will hiccup. 2, 5 or 10 loop perfectly.")
        sprites[base] = frames
    return sprites

# ----------------------------------------------------------------------------- cleanup

def has_transparency(im):
    return im.getchannel("A").getextrema()[0] < 250


def remove_solid_background(im, tol=48):
    """Flood-fills a flat background from the edges. Leaves enclosed areas (eye whites etc.) alone."""
    w, h = im.size
    px = im.load()
    corners = [px[0, 0], px[w - 1, 0], px[0, h - 1], px[w - 1, h - 1]]
    bg = corners[0][:3]
    close = lambda c: abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) <= tol
    if sum(close(c[:3]) for c in corners) < 3:
        return im  # corners disagree: no flat background to remove
    out = im.copy(); op = out.load()
    seen = bytearray(w * h); q = deque()
    for x in range(w):
        q.append((x, 0)); q.append((x, h - 1))
    for y in range(h):
        q.append((0, y)); q.append((w - 1, y))
    while q:
        x, y = q.popleft()
        i = y * w + x
        if seen[i]:
            continue
        seen[i] = 1
        if not close(px[x, y][:3]):
            continue
        op[x, y] = (0, 0, 0, 0)
        if x > 0: q.append((x - 1, y))
        if x < w - 1: q.append((x + 1, y))
        if y > 0: q.append((x, y - 1))
        if y < h - 1: q.append((x, y + 1))
    return out


def clean(frames):
    # all frames same size as the first
    w, h = frames[0].size
    frames = [f if f.size == (w, h) else f.resize((w, h), Image.NEAREST) for f in frames]
    # shrink huge inputs for speed
    if max(w, h) > WORK_MAX:
        k = WORK_MAX / max(w, h)
        frames = [f.resize((max(1, round(w * k)), max(1, round(h * k))), Image.LANCZOS) for f in frames]
    if not any(has_transparency(f) for f in frames):
        frames = [remove_solid_background(f) for f in frames]
    # one shared bounding box for every frame -> no jitter
    boxes = [f.getchannel("A").point(lambda a: 255 if a > 16 else 0).getbbox() for f in frames]
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    box = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))
    frames = [f.crop(box) for f in frames]
    cw, ch = frames[0].size
    side = max(cw, ch)
    squared = []
    for f in frames:
        c = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        c.paste(f, ((side - cw) // 2, side - ch))  # centered, sitting on the bottom
        squared.append(c)
    if side > PIXEL_ART_MAX:
        squared = [f.resize((BIG_SIZE, BIG_SIZE), Image.LANCZOS) for f in squared]
    return squared

# ----------------------------------------------------------------------------- frame sequences

MOTIONS = {
    "hop":    [(0, 0.0), (0, -0.12)] * 5,
    "wiggle": [(-0.09, 0), (0.09, 0)] * 5,
    "wander": [(0.10 * math.cos(2 * math.pi * k / 10), 0.07 * math.sin(2 * math.pi * k / 10)) for k in range(10)],
}
MOTION_SCALE = 0.78


def timing_sequence(n_frames, setting):
    """Which frame shows for each of the 10 seconds."""
    if isinstance(setting, list) and setting:
        seq = []
        for v in setting:
            if isinstance(v, int) and 1 <= v <= n_frames:
                seq.append(v - 1)
        if seq:
            if 10 % len(seq):
                warn(f"timing has {len(seq)} steps; 1, 2, 5 or 10 loop perfectly")
            return [seq[d % len(seq)] for d in range(10)]
    return [d % n_frames for d in range(10)]


def moved(frame, dx, dy, flip):
    side = frame.width
    inner = max(1, round(side * MOTION_SCALE))
    resample = Image.NEAREST if side <= PIXEL_ART_MAX else Image.LANCZOS
    small = frame.resize((inner, inner), resample)
    if flip:
        small = ImageOps.mirror(small)
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    x = round((side - inner) / 2 + dx * side)
    y = round((side - inner) / 2 + dy * side + (side - inner) * 0.35)
    canvas.paste(small, (x, y), small)
    return canvas


def motion_digits(frames, seq, motion, flip_setting):
    path = MOTIONS[motion]
    out = []
    for d in range(10):
        dx, dy = path[d]
        prev_dx = path[d - 1][0]
        flip = bool(flip_setting) and motion != "hop" and dx < prev_dx
        out.append(moved(frames[seq[d]], dx, dy, flip))
    return out

# ----------------------------------------------------------------------------- fonts

UPM = 1000
STRIKES = [32, 48, 64, 96, 128, 192]
DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
EMPTY = {".notdef": None, "space": " ", "colon": ":", "hyphen": "-", "period": "."}
SEPARATORS = ["space", "colon", "hyphen", "period"]
# Every digit followed by another character becomes a zero-width blank, so a running
# timer like "1:23:45" draws as ONE sprite: the last digit (the seconds).
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


def png_bytes(img, size):
    resample = Image.NEAREST if (img.width <= PIXEL_ART_MAX or size >= img.width) else Image.LANCZOS
    out = io.BytesIO()
    img.resize((size, size), resample).save(out, "PNG", optimize=True)
    return out.getvalue()


def build_font(font_id, digit_images, out_path):
    """digit_images: 10 images, one per digit 0-9."""
    ps_name = f"PocketPal-{font_id}"
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
    fb.setupNameTable({"familyName": f"PocketPal {font_id}", "styleName": "Regular",
                       "fullName": f"PocketPal {font_id}", "psName": ps_name,
                       "uniqueFontIdentifier": ps_name})
    fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, sTypoLineGap=0, usWinAscent=UPM,
                usWinDescent=0, sxHeight=UPM // 2, sCapHeight=UPM, fsType=0)
    fb.setupPost()
    sbix = newTable("sbix"); sbix.version = 1; sbix.flags = 1
    cache = {}
    for ppem in STRIKES:
        strike = Strike(ppem=ppem, resolution=72)
        for d, gname in enumerate(DIGITS):
            key = (id(digit_images[d]), ppem)
            if key not in cache:
                cache[key] = png_bytes(digit_images[d], ppem)
            strike.glyphs[gname] = SbixGlyph(glyphName=gname, graphicType="png ",
                                             imageData=cache[key], originOffsetX=0, originOffsetY=0)
        sbix.strikes[ppem] = strike
    fb.font["sbix"] = sbix
    addOpenTypeFeaturesFromString(fb.font, FEATURES)
    fb.save(str(out_path))
    return f"{font_id}.ttf"

# ----------------------------------------------------------------------------- preview sheet

def preview_sheet(processed, path):
    cell, pad, label_w = 96, 10, 150
    rows = sorted(processed.items(), key=lambda kv: kv[0].lower())
    max_frames = max((len(f) for _, f in rows), default=1)
    W = label_w + max_frames * (cell + pad) + pad
    H = max(1, len(rows)) * (cell + pad) + pad
    sheet = Image.new("RGBA", (W, H), (22, 22, 30, 255))
    d = ImageDraw.Draw(sheet)
    for r, (name, frames) in enumerate(rows):
        y = pad + r * (cell + pad)
        kind = f"{len(frames)} frames" if len(frames) > 1 else "still"
        d.text((pad, y + cell // 2 - 12), name, fill=(235, 235, 245, 255))
        d.text((pad, y + cell // 2 + 2), kind, fill=(150, 150, 170, 255))
        for i, f in enumerate(frames):
            x = label_w + i * (cell + pad)
            d.rounded_rectangle((x, y, x + cell, y + cell), radius=10, fill=(0, 0, 0, 255))
            resample = Image.NEAREST if f.width <= PIXEL_ART_MAX else Image.LANCZOS
            sheet.alpha_composite(f.resize((cell - 12, cell - 12), resample), (x + 6, y + 6))
    sheet.save(path)

# ----------------------------------------------------------------------------- main

def write_widget_plist(font_files):
    plist = {
        "CFBundleDevelopmentRegion": "en",
        "CFBundleDisplayName": "Pocket Pal Widget",
        "CFBundleExecutable": "$(EXECUTABLE_NAME)",
        "CFBundleIdentifier": "$(PRODUCT_BUNDLE_IDENTIFIER)",
        "CFBundleInfoDictionaryVersion": "6.0",
        "CFBundleName": "$(PRODUCT_NAME)",
        "CFBundlePackageType": "$(PRODUCT_BUNDLE_PACKAGE_TYPE)",
        "CFBundleShortVersionString": "$(MARKETING_VERSION)",
        "CFBundleVersion": "$(CURRENT_PROJECT_VERSION)",
        "NSExtension": {"NSExtensionPointIdentifier": "com.apple.widgetkit-extension"},
        "ALTAppGroups": ["group.com.yourname.pocketpal"],   # SideStore fills in the real (renamed) group
        "UIAppFonts": [f"Fonts/{f}" for f in font_files],
    }
    SUPPORT.mkdir(exist_ok=True)
    with open(SUPPORT / "Widget-Info.plist", "wb") as fh:
        plistlib.dump(plist, fh)


def main():
    if GEN.exists():
        shutil.rmtree(GEN)
    OUT_SPRITES.mkdir(parents=True); OUT_FONTS.mkdir(parents=True)
    SRC.mkdir(exist_ok=True)
    settings = load_settings()
    font_files, processed = [], {}

    for name, raw in gather().items():
        frames = clean(raw)
        if not frames:
            warn(f"{name}: image is empty after removing the background; skipped")
            continue
        processed[name] = frames
        s = settings.get(name, {}) if isinstance(settings.get(name), dict) else {}
        fid = safe(name)

        # cleaned sprite files for the app
        if len(frames) == 1:
            frames[0].save(OUT_SPRITES / f"{name}.png", optimize=True)
        else:
            for i, f in enumerate(frames, 1):
                f.save(OUT_SPRITES / f"{name}_{i}.png", optimize=True)

        seq = timing_sequence(len(frames), s.get("timing"))
        flip = s.get("flip", False)
        if len(frames) > 1:
            font_files.append(build_font(fid, [frames[seq[d]] for d in range(10)], OUT_FONTS / f"{fid}.ttf"))
            for m in MOTIONS:  # animation + movement
                font_files.append(build_font(f"{fid}-{m}", motion_digits(frames, seq, m, flip),
                                             OUT_FONTS / f"{fid}-{m}.ttf"))
                # first frame only, moving (for when "Animate" is off)
                font_files.append(build_font(f"{fid}-{m}-still", motion_digits(frames[:1], [0] * 10, m, flip),
                                             OUT_FONTS / f"{fid}-{m}-still.ttf"))
        else:
            for m in MOTIONS:
                font_files.append(build_font(f"{fid}-{m}", motion_digits(frames, [0] * 10, m, flip),
                                             OUT_FONTS / f"{fid}-{m}.ttf"))
        print(f"  {name}: {'still' if len(frames) == 1 else f'{len(frames)} frames'}, {frames[0].width}px")

    # settings the app reads (nickname / motion / icon defaults)
    app_settings = {k: {kk: v[kk] for kk in ("nickname", "motion", "icon") if kk in v}
                    for k, v in settings.items() if isinstance(v, dict)}
    (OUT_SPRITES / "sprites.json").write_text(json.dumps(app_settings, indent=2), encoding="utf-8")

    write_widget_plist(font_files)
    preview_sheet(processed, GEN / "preview.png")
    print(f"Done: {len(processed)} sprite(s), {len(font_files)} font(s). Preview: Generated/preview.png")


if __name__ == "__main__":
    sys.exit(main())
