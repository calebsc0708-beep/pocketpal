#!/usr/bin/env python3
"""
Turns animated sprites into "frame fonts" for the Dynamic Island.

Sprites named like  pikachu_1.png, pikachu_2.png, ...  are grouped into one
animated sprite. For each group this script builds a color bitmap font (sbix)
where the digits 0-9 are drawn as the animation frames: digit d shows frame
d % frame_count. The Live Activity shows a running timer in that font and only
the last digit (the seconds) is visible, so the sprite flips frames every second.

It also writes Support/Widget-Info.plist, which registers the fonts (UIAppFonts).

Usage (from the project root):  python3 tools/make_fonts.py
"""
import io
import plistlib
import sys
from pathlib import Path

from PIL import Image
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable
from fontTools.ttLib.tables.sbixGlyph import Glyph as SbixGlyph
from fontTools.ttLib.tables.sbixStrike import Strike

ROOT = Path(__file__).resolve().parent.parent
SPRITES = ROOT / "Sprites"
FONTS = ROOT / "Fonts"
SUPPORT = ROOT / "Support"

UPM = 1000
STRIKES = [32, 48, 64, 96, 128, 192]  # bitmap sizes in pixels; iOS picks the closest
DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
EMPTY = {".notdef": None, "space": " ", "colon": ":", "hyphen": "-", "period": "."}


def safe(name: str) -> str:
    """Must match Sprites.fontName(for:) in Shared/PetAttributes.swift."""
    s = "".join(c for c in name if c.isascii() and c.isalnum())
    return s or "sprite"


def group_sprites():
    groups = {}
    for p in sorted(SPRITES.glob("*.png")):
        stem = p.stem
        base, sep, num = stem.rpartition("_")
        if sep and num.isdigit() and base:
            groups.setdefault(base, []).append((int(num), p))
    return {k: [p for _, p in sorted(v)] for k, v in groups.items() if len(v) >= 2}


def square(img: Image.Image) -> Image.Image:
    img = img.convert("RGBA")
    bbox_side = max(img.size)
    canvas = Image.new("RGBA", (bbox_side, bbox_side), (0, 0, 0, 0))
    canvas.paste(img, ((bbox_side - img.width) // 2, (bbox_side - img.height) // 2))
    return canvas


def png_bytes(img: Image.Image, size: int) -> bytes:
    pixel_art = img.width <= 128
    resample = Image.NEAREST if (pixel_art or size >= img.width) else Image.LANCZOS
    out = io.BytesIO()
    img.resize((size, size), resample).save(out, "PNG", optimize=True)
    return out.getvalue()


def build_font(name: str, frame_paths, out_path: Path):
    frames = [square(Image.open(p)) for p in frame_paths]
    # Make every frame the same size as the first so they line up
    side = frames[0].width
    frames = [f if f.width == side else f.resize((side, side), Image.NEAREST) for f in frames]

    glyph_order = list(EMPTY.keys()) + DIGITS
    family = f"PocketPal {safe(name)}"
    ps_name = f"PocketPal-{safe(name)}"

    fb = FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(glyph_order)
    cmap = {ord(ch): g for g, ch in EMPTY.items() if ch}
    cmap.update({ord(str(i)): g for i, g in enumerate(DIGITS)})
    fb.setupCharacterMap(cmap)

    empty = TTGlyphPen(None).glyph()
    fb.setupGlyf({g: empty for g in glyph_order})
    # Every glyph is a perfect square: advance = em = line height
    fb.setupHorizontalMetrics({g: (UPM, 0) for g in glyph_order})
    fb.setupHorizontalHeader(ascent=UPM, descent=0, lineGap=0)
    fb.setupNameTable({"familyName": family, "styleName": "Regular",
                       "fullName": family, "psName": ps_name, "uniqueFontIdentifier": ps_name})
    fb.setupOS2(sTypoAscender=UPM, sTypoDescender=0, sTypoLineGap=0,
                usWinAscent=UPM, usWinDescent=0, sxHeight=UPM // 2, sCapHeight=UPM,
                fsType=0)
    fb.setupPost(isFixedPitch=1)

    sbix = newTable("sbix")
    sbix.version = 1
    sbix.flags = 1
    for ppem in STRIKES:
        strike = Strike(ppem=ppem, resolution=72)
        for i, gname in enumerate(DIGITS):
            frame = frames[i % len(frames)]
            strike.glyphs[gname] = SbixGlyph(
                glyphName=gname, graphicType="png ",
                imageData=png_bytes(frame, ppem), originOffsetX=0, originOffsetY=0)
        sbix.strikes[ppem] = strike
    fb.font["sbix"] = sbix

    fb.save(str(out_path))
    return ps_name


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
        "UIAppFonts": [f"Fonts/{f}" for f in font_files],
    }
    SUPPORT.mkdir(exist_ok=True)
    with open(SUPPORT / "Widget-Info.plist", "wb") as fh:
        plistlib.dump(plist, fh)


def main():
    FONTS.mkdir(exist_ok=True)
    for old in FONTS.glob("*.ttf"):
        old.unlink()
    font_files = []
    for name, paths in group_sprites().items():
        fname = f"{safe(name)}.ttf"
        ps = build_font(name, paths, FONTS / fname)
        font_files.append(fname)
        print(f"  {name}: {len(paths)} frames -> Fonts/{fname} ({ps})")
        if 10 % len(paths):
            print(f"    note: {len(paths)} frames doesn't divide 10 evenly; "
                  f"the loop will hiccup once every 10 seconds. 2, 5 or 10 frames loop perfectly.")
    write_widget_plist(font_files)
    print(f"Built {len(font_files)} animated sprite font(s).")


if __name__ == "__main__":
    sys.exit(main())
