"""PokePal-clock: the room's little LCD clock as a real (vector) font.

The widget shows it with a counting-up timer, Text(start, style: .timer), which iOS keeps up to date
by itself — so the widget doesn't need a new picture every minute just for the clock.
The timer starts at midnight (afternoon) or noon the day before (morning), so it always reads
"HH:MM:SS" with HH between 12 and 23. The font then:
  - maps hours 13-23 to 1-11 (12-hour time), 12 stays 12
  - hides the ":SS" seconds

Layout matches the clock drawn in the app (PalRoomAmbience): 3x5 digits with a 4 px pitch,
a 2 px colon, and nothing for the space / "AM" / "PM" that the time style adds.
1 room pixel = 100 font units; the em is 8 room pixels tall, digits sit on rows 1-5.
"""
import plistlib
from pathlib import Path
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "Generated" / "Fonts"
PLIST = ROOT / "Support" / "Widget-Info.plist"
NAME = "PokePal-clock"
U = 100          # units per room pixel
EM = 8 * U       # em = 8 room px
TOP_ROW = 1      # digits start one pixel below the top of the em

DIGITS = [
    ["111", "101", "101", "101", "111"], ["010", "110", "010", "010", "111"],
    ["111", "001", "111", "100", "111"], ["111", "001", "111", "001", "111"],
    ["101", "101", "111", "001", "001"], ["111", "100", "111", "001", "111"],
    ["111", "100", "111", "101", "111"], ["111", "001", "010", "010", "010"],
    ["111", "101", "111", "101", "111"], ["111", "101", "111", "001", "111"],
]
COLON = ["0", "1", "0", "1", "0"]   # dots on rows 2 and 4 (y 48 and 50 in the room)


def pixels_glyph(rows):
    pen = TTGlyphPen(None)
    for r, row in enumerate(rows):
        for c, bit in enumerate(row):
            if bit != "1":
                continue
            x0 = c * U
            y1 = EM - (TOP_ROW + r) * U            # font y goes up from the baseline (bottom of the em)
            y0 = y1 - U
            pen.moveTo((x0, y0)); pen.lineTo((x0, y1)); pen.lineTo((x0 + U, y1)); pen.lineTo((x0 + U, y0)); pen.closePath()
    return pen.glyph()


def empty_glyph():
    return TTGlyphPen(None).glyph()


def features():
    """The hour pair (followed by :MM:) becomes 12-hour time; the seconds (after :MM) disappear."""
    D = "[" + " ".join(f"d{i}" for i in range(10)) + "]"
    lines = ["lookup KILL { sub " + D + " by empty; sub colon by empty; } KILL;"]
    for i in range(10):
        lines.append(f"lookup TO{i} {{ sub {D} by d{i}; }} TO{i};")
    rules = []
    for h in range(13, 24):               # 13..23 -> 1..11
        a, b = divmod(h, 10); h12 = h - 12
        if h12 < 10:
            rules.append(f"    sub d{a}' lookup KILL d{b}' lookup TO{h12} colon {D} {D} colon;")
        else:
            rules.append(f"    sub d{a}' lookup TO{h12 // 10} d{b}' lookup TO{h12 % 10} colon {D} {D} colon;")
    rules.append(f"    sub colon {D} {D} colon' lookup KILL {D}' lookup KILL {D}' lookup KILL;")   # :SS
    return "\n".join(lines) + "\nfeature calt {\n" + "\n".join(rules) + "\n} calt;\nfeature liga {\n" + "\n".join(rules) + "\n} liga;\n"


def main():
    names = [".notdef", "space", "empty"] + [f"d{i}" for i in range(10)] + ["colon"]
    glyphs = {".notdef": empty_glyph(), "space": empty_glyph(), "empty": empty_glyph(), "colon": pixels_glyph(COLON)}
    metrics = {".notdef": (0, 0), "space": (0, 0), "empty": (0, 0), "colon": (2 * U, 0)}
    cmap = {ord(":"): "colon", 0x2236: "colon"}
    for i in range(10):
        glyphs[f"d{i}"] = pixels_glyph(DIGITS[i]); metrics[f"d{i}"] = (4 * U, 0); cmap[ord("0") + i] = f"d{i}"
    # everything the time style can add around the digits draws nothing and takes no room
    for ch in "    APMapm.":
        cmap[ord(ch)] = "space"

    fb = FontBuilder(EM, isTTF=True)
    fb.setupGlyphOrder(names)
    fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(metrics)
    fb.setupHorizontalHeader(ascent=EM, descent=0, lineGap=0)
    fb.setupNameTable({"familyName": NAME, "styleName": "Regular", "psName": NAME, "fullName": NAME})
    fb.setupOS2(version=4, sTypoAscender=EM, sTypoDescender=0, sTypoLineGap=0, usWinAscent=EM, usWinDescent=0, fsSelection=0x80)  # use typo metrics
    fb.setupPost()
    addOpenTypeFeaturesFromString(fb.font, features())
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{NAME}.ttf"
    fb.save(str(path))

    if PLIST.exists():
        plist = plistlib.loads(PLIST.read_bytes())
        fonts = plist.get("UIAppFonts", [])
        entry = f"Fonts/{path.name}"
        if entry not in fonts:
            fonts.append(entry)
        plist["UIAppFonts"] = fonts
        PLIST.write_bytes(plistlib.dumps(plist))
    print(f"{path.name}: {path.stat().st_size} bytes")


if __name__ == "__main__":
    main()
