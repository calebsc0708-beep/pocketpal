from PIL import Image, ImageDraw, ImageFilter
import numpy as np, math, random

import sys
TIME, WEATHER = sys.argv[1], sys.argv[2]   # sunrise|day|sunset|night , clear|cloudy|rain|storm|snow
NIGHT = TIME == "night"
SCENE = sys.argv[3] if len(sys.argv) > 3 else ""
import os
WIDE = os.environ.get("WIDE") == "1"
W, H = (344 if WIDE else 256), 160
random.seed(3)
img = Image.new("RGB", (W, H))
d = ImageDraw.Draw(img)
emis = Image.new("L", (W, H), 0)          # emissive pixels ignore lighting
de = ImageDraw.Draw(emis)

# Anything solid drawn on top of a glowing pixel (sky, lamp) stops it glowing: the curtains, pillows
# and window frame in front of the glass get lit like everything else.
def P(pts, c, e=False):
    d.polygon(pts, fill=c)
    de.polygon(pts, fill=255 if e else 0)
def R(x0, y0, x1, y1, c, e=False):
    d.rectangle([x0, y0, x1, y1], fill=c)
    de.rectangle([x0, y0, x1, y1], fill=255 if e else 0)
def px(x, y, c, e=False):
    if 0 <= x < W and 0 <= y < H:
        img.putpixel((x, y), c)
        emis.putpixel((x, y), 255 if e else 0)
def E(box, c, e=False):
    d.ellipse(box, fill=c)
    de.ellipse(box, fill=255 if e else 0)

LAMP_ON = TIME in ("night", "sunset") or WEATHER == "storm" or (TIME == "sunrise" and WEATHER != "clear")
# ---------- palette ----------
CEIL = (70, 52, 70); BEAM = (96, 64, 48); BEAM_D = (70, 46, 36)
WALL = (150, 112, 120); WALL_D = (132, 96, 106); WALLL = (122, 88, 100)
PANEL = (120, 78, 58); PANEL_D = (98, 62, 46); PANEL_L = (140, 94, 70)
FLOOR = (128, 84, 60); FLOOR_D = (106, 68, 48); FLOOR_L = (146, 98, 70)
WOOD = (140, 92, 60); WOOD_D = (104, 66, 42); WOOD_L = (172, 118, 78)
SKY = (36, 48, 92); SKY_L = (52, 68, 118); TREE = (24, 34, 56); MOON = (255, 244, 200)
CREAM = (240, 226, 200); CREAM_D = (214, 196, 170)
BLANK = (196, 92, 84); BLANK_D = (160, 68, 64); BLANK_L = (222, 122, 104)
QUILT2 = (236, 180, 110)
SAGE = (126, 160, 120); SAGE_D = (96, 128, 94)
GREEN = (84, 156, 92); GREEN_D = (56, 116, 70); GREEN_DD = (38, 84, 54)
POT = (196, 108, 76); POT_D = (156, 80, 58)
BOOKS = [(206, 96, 96), (96, 150, 170), (230, 186, 96), (140, 110, 170), (110, 150, 110), (220, 140, 110)]
LAMP = (255, 214, 140); BULB = [(255, 200, 120), (255, 170, 140), (255, 226, 150)]
DARK = (40, 30, 40)
PAL = (140, 220, 170); PAL_D = (100, 180, 136)
RUG = (88, 120, 140); RUG_L = (120, 152, 166); RUG_D = (70, 98, 118)

FL = 104           # back-wall / floor line
LW = 44            # left wall depth (x where back wall begins)
CT = 14            # back wall top

def lw_top(x): return CT * x / LW
def lw_bot(x): return FL + (FL - 40) * (LW - x) / (150 - LW)
def lw(x, t): return lw_top(x) + (lw_bot(x) - lw_top(x)) * t

# ---------- perspective helpers ----------
# Coordinates are given as drawn on the back wall; dd = how far (metres) the point sits out from that wall.
VPX, VPY = 150, 40
def K(dd): return 10.0 / (10.0 - dd)
def wp(x, y, dd):
    k = K(dd); return (VPX + (x - VPX) * k, VPY + (y - VPY) * k)
def _q(pts): return [(round(x), round(y)) for x, y in pts]
def Pd(pts, dd, c, e=False): P(_q([wp(x, y, dd) for x, y in pts]), c, e)
def Rd(x0, y0, x1, y1, dd, c, e=False): Pd([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], dd, c, e)
def Ld(pts, dd, c): d.line(_q([wp(x, y, dd) for x, y in pts]), fill=c)
def Ed(box, dd, c, e=False):
    a = wp(box[0], box[1], dd); b = wp(box[2], box[3], dd); E([round(a[0]), round(a[1]), round(b[0]), round(b[1])], c, e)
def block(x0, y0, x1, y1, d0, d1, front, top=None, side=None, bottom=None, e=False):
    """A box sitting out from the back wall between depths d0..d1; only the faces you can see get drawn."""
    if top and y0 > VPY: P(_q([wp(x0, y0, d0), wp(x1, y0, d0), wp(x1, y0, d1), wp(x0, y0, d1)]), top, e)
    if bottom and y1 < VPY: P(_q([wp(x0, y1, d0), wp(x1, y1, d0), wp(x1, y1, d1), wp(x0, y1, d1)]), bottom, e)
    if side and x0 > VPX: P(_q([wp(x0, y0, d0), wp(x0, y0, d1), wp(x0, y1, d1), wp(x0, y1, d0)]), side, e)
    if side and x1 < VPX: P(_q([wp(x1, y0, d0), wp(x1, y0, d1), wp(x1, y1, d1), wp(x1, y1, d0)]), side, e)
    Rd(x0, y0, x1, y1, d1, front, e)
# world-space version (X right, Y up, Z away; camera at height 1.6, back wall at Z = 10)
def pj(X, Y, Z): return (VPX + 400 * X / Z, VPY + 400 * (1.6 - Y) / Z)
def to_world(x, y, dd=0.0):
    Z = 10.0 - dd; return ((x - VPX) * Z / 400, 1.6 - (y - VPY) * Z / 400, Z)

ITEMS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "items")
def item(name, div):
    """An item sprite shrunk by a whole factor (1 sprite pixel = 1 room pixel), hard-edged like the room."""
    im = Image.open(os.path.join(ITEMS, f"{name}.png")).convert("RGBA")
    w, h = max(1, round(im.width / div)), max(1, round(im.height / div))
    im = im.resize((w, h), Image.BOX)
    im.putalpha(im.getchannel("A").point(lambda v: 255 if v >= 128 else 0))
    return im
def place(name, div, cx, bottom):
    """Stand an item on a surface: centred on x, its bottom on y."""
    it = item(name, div)
    x, y = round(cx - it.width / 2), round(bottom - it.height)
    img.paste(it, (x, y), it)
    de.bitmap((x, y), it.getchannel("A"), fill=0)          # lit like the room, never glowing
HOLIDAY = os.environ.get("HOLIDAY")         # draw that holiday's decorations into the room
import holiday as _holiday
def holiday_layer(layer):
    globals()["_glass_now"] = np.asarray(emis) > 0
    _holiday.draw(layer, globals())

# ---------- room shell ----------
R(0, 0, W, H, FLOOR)
P([(0, 0), (W, 0), (W, CT), (LW, CT)], CEIL)
# ceiling beams (perspective toward back)
def _front(x, y): return (VPX + (x - VPX) * (VPY - 0) / (VPY - y), 0)   # where a back-wall point's depth line meets the top edge
for bx in ([90, 170, 240, 312] if WIDE else [90, 170, 240]):
    l, r, dr = bx - 3, bx + 3, CT + 3          # beam bottom, 3px below the ceiling at the back
    P(_q([(l, CT), (r, CT), _front(r, CT), _front(l, CT)]), BEAM_D)              # sides (just the edge strip)
    P(_q([(l, dr), (r, dr), _front(r, dr), _front(l, dr)]), BEAM)                # underside
    inner = l if bx > VPX else r                                                  # the side facing the middle shows
    P(_q([(inner, CT), (inner, dr), _front(inner, dr), _front(inner, CT)]), BEAM_D)
R(LW, CT, W, FL, WALL)
for x in range(LW + 6, W, 10): R(x, CT, x, 80, WALL_D)
R(LW, 80, W, FL, PANEL); R(LW, 80, W, 81, PANEL_L)
for x in range(LW + 10, W, 18): R(x, 84, x + 13, FL - 4, PANEL_D)
R(LW, FL - 2, W, FL, PANEL_D)
# left wall
P([(0, 0), (LW, CT), (LW, FL), (0, round(lw_bot(0)))], WALLL)
P([(0, int(lw(0, .72))), (LW, int(lw(LW, .72))), (LW, FL), (0, round(lw_bot(0)))], PANEL_D)
d.line([(0, int(lw(0, .72))), (LW, int(lw(LW, .72)))], fill=PANEL)
d.line([(LW, CT), (LW, FL)], fill=WALL_D)
# floor planks converging
P([(0, round(lw_bot(0))), (LW, FL), (W, FL), (W, H), (0, H)], FLOOR)
for y in [108, 113, 119, 126, 134, 143, 153]:
    xl = 0 if y >= lw_bot(0) else LW - (y - FL) * (150 - LW) / (FL - 40)
    d.line([(round(xl), y), (W, y)], fill=FLOOR_D)
vp = (150, 40)
for x in range(-200, W + 400, 26):
    d.line([(x, H), (vp[0] + (x - vp[0]) * (FL - vp[1]) / (H - vp[1]), FL)], fill=FLOOR_D)

_snap_shell = img.copy()
# ---------- window + seat ----------
wx0, wx1, wy0, wy1 = 62, 108, 26, 74
R(wx0 - 3, wy0, wx1 + 3, wy1 + 3, WOOD_D)
E([wx0 - 3, wy0 - 14, wx1 + 3, wy0 + 12], WOOD_D)
# --- sky layer (time + weather) ---
SKIES = {"sunrise": ((96, 112, 176), (252, 178, 142)), "day": ((92, 162, 232), (176, 214, 246)),
         "sunset": ((72, 60, 132), (252, 136, 84)), "night": ((20, 28, 70), (48, 62, 112))}
GRAY = {"sunrise": (150, 140, 150), "day": (160, 168, 178), "sunset": (130, 110, 120), "night": (40, 44, 62)}
mixw = {"clear": 0, "cloudy": .55, "rain": .75, "storm": .9, "snow": .7}[WEATHER]
def mix(a, b, t): return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
top, bot = SKIES[TIME]
if WEATHER == "storm": g = mix(GRAY[TIME], (20, 22, 34), .45)
elif WEATHER == "snow": g = mix(GRAY[TIME], (220, 224, 236), .3 if not NIGHT else 0)
else: g = GRAY[TIME]
top, bot = mix(top, g, mixw), mix(bot, g, mixw)
sky = Image.new("RGB", (W, H)); sk = ImageDraw.Draw(sky)
for y in range(wy0 - 12, wy1 + 1):
    t = (y - (wy0 - 12)) / (wy1 - wy0 + 12)
    sk.line([(0, y), (W, y)], fill=mix(top, bot, t))
rs = random.Random(11)
if WEATHER in ("clear", "cloudy"):
    if NIGHT:
        if WEATHER == "clear":
            for _ in range(14): sky.putpixel((rs.randint(wx0 + 2, wx1 - 2), rs.randint(wy0 - 8, 52)), (225, 225, 255))
        sk.ellipse([92, 22, 100, 30], fill=MOON); sk.ellipse([95, 21, 102, 28], fill=mix(top, bot, .3))
    else:
        sun = {"sunrise": (72, 58, (255, 220, 150)), "day": (94, 22, (255, 250, 220)), "sunset": (98, 58, (255, 170, 90))}[TIME]
        sx, sy, sc = sun
        sk.ellipse([sx - 7, sy - 7, sx + 7, sy + 7], fill=mix(sc, bot, .5))
        sk.ellipse([sx - 5, sy - 5, sx + 5, sy + 5], fill=sc)
# clouds
CL = {"sunrise": (250, 200, 196), "day": (250, 252, 255), "sunset": (240, 150, 140), "night": (70, 76, 104)}[TIME]
ncl = {"clear": 2, "cloudy": 7, "rain": 9, "storm": 10, "snow": 8}[WEATHER]
ccol = CL if WEATHER in ("clear", "cloudy") else mix(CL, g, .6)
if WEATHER == "storm": ccol = mix(ccol, (30, 32, 46), .5)
import json as _json
EXPORT = {"cloud": list(ccol), "cloudShadow": list(mix(ccol, (0, 0, 0), .12)), "clouds": ncl}
# trees / ground
TREES = {"sunrise": (52, 62, 92), "day": (62, 118, 84), "sunset": (54, 44, 70), "night": TREE}
tc = TREES[TIME]
if WEATHER in ("rain", "storm"): tc = mix(tc, (30, 36, 50), .4)
for x in range(0, W):
    th = int(60 + 5 * math.sin(x / 3) + 3 * math.sin(x / 1.3))
    sk.line([(x, th), (x, wy1)], fill=tc)
    if WEATHER == "snow":
        for k in range(2): sky.putpixel((x, th + k), (236, 240, 250) if not NIGHT else (150, 160, 190))
if WEATHER == "snow":
    sk.rectangle([0, 70, W, wy1], fill=(236, 240, 250) if not NIGHT else (140, 150, 184))
    for _ in range(45):
        sky.putpixel((rs.randint(wx0, wx1), rs.randint(wy0 - 10, wy1)), (255, 255, 255))
if WEATHER in ("rain", "storm"):
    rc = mix(bot, (255, 255, 255), .35)
    for _ in range(55 if WEATHER == "storm" else 40):
        x = rs.randint(wx0, wx1); y = rs.randint(wy0 - 10, wy1 - 3)
        sk.line([(x, y), (x - (1 if WEATHER == "storm" else 0), y + 3)], fill=rc)
if WEATHER == "storm":
    bolt = [(80, 18), (76, 32), (81, 32), (75, 50)]
    sk.line(bolt, fill=(255, 255, 220), width=1)
wmask = Image.new("L", (W, H), 0); wm = ImageDraw.Draw(wmask)
wm.rectangle([wx0, wy0, wx1, wy1], fill=255); wm.ellipse([wx0, wy0 - 11, wx1, wy0 + 9], fill=255)
img.paste(sky, (0, 0), wmask); emis.paste(255, (0, 0), wmask)
# window sill snow pile
if WEATHER == "snow":
    R(wx0, wy1 - 2, wx1, wy1, (246, 248, 255) if not NIGHT else (170, 180, 210), True)
R((wx0 + wx1) // 2, wy0 - 11, (wx0 + wx1) // 2 + 1, wy1, WOOD)
R(wx0, 48, wx1, 49, WOOD)
_snap_precurtain = img.copy()
# curtains
for cx, side in [(wx0 - 8, 1), (wx1 + 2, -1)]:
    P([(cx, wy0 - 14), (cx + 8, wy0 - 14), (cx + 7 + side * 2, wy1 + 4), (cx - 1, wy1 + 6)], SAGE)
    for k in range(2, 8, 3): d.line([(cx + k, wy0 - 13), (cx + k + side, wy1 + 4)], fill=SAGE_D)
_snap_postcurtain = img.copy()
block(wx0 - 12, wy0 - 16, wx1 + 12, wy0 - 15, 0, 0.15, WOOD_D, bottom=(84, 52, 36))
for ex in (wx0 - 13, wx1 + 12): block(ex, wy0 - 17, ex + 1, wy0 - 14, 0.1, 0.16, WOOD, side=WOOD_D)
# window seat
SEAT_D = 0.7
block(wx0 - 8, 80, wx1 + 8, FL, 0, SEAT_D, WOOD, side=WOOD_D)
block(wx0 - 8, 76, wx1 + 8, 80, 0, SEAT_D + 0.03, CREAM, top=(250, 238, 214), side=CREAM_D)
Ld([(wx0 - 8, 80), (wx1 + 8, 80)], SEAT_D, WOOD_D)
for x0 in [wx0 - 5, wx0 + 21]: Rd(x0, 85, x0 + 20, FL - 3, SEAT_D, WOOD_D); Rd(x0 + 1, 86, x0 + 19, FL - 4, SEAT_D, WOOD)
# pillows + folded blanket + book + mug on seat
E([wx0 - 6, 66, wx0 + 10, 79], QUILT2); E([wx0 - 4, 68, wx0 + 6, 77], (246, 200, 130))
E([wx1 - 10, 67, wx1 + 6, 79], SAGE); E([wx1 - 8, 69, wx1 + 2, 77], (146, 180, 140))
block(wx0 + 18, 73, wx0 + 34, 76, 0.15, 0.4, BLANK, top=BLANK_L, side=BLANK_D); Ld([(wx0 + 18, 74.5), (wx0 + 34, 74.5)], 0.4, BLANK_D)   # folded blanket
block(wx0 + 36, 73, wx0 + 41, 76, 0.0, 0.1, CREAM_D, top=(196, 176, 150)); px(wx0 + 42, 74, CREAM_D); px(wx0 + 42, 75, CREAM_D)   # mug (the steam rises from x 100)                                  # mug
px(wx0 + 38, 71, (200, 200, 210)); px(wx0 + 39, 70, (200, 200, 210))

# ---------- desk wall: corkboard, shelf ----------
R(122, 24, 150, 44, WOOD_D); R(123, 25, 149, 43, (196, 156, 110))
for (x, y, c) in [(125, 27, CREAM), (134, 29, CREAM), (142, 26, CREAM), (128, 35, (250, 210, 200)), (139, 36, CREAM)]:
    R(x, y, x + 6, y + 6, c); R(x + 1, y + 1, x + 5, y + 4, random.choice(BOOKS)); px(x + 3, y, (220, 60, 60))
block(118, 50, 170, 52, 0, 0.28, WOOD_D, top=WOOD)
R(120, 53, 121, 55, WOOD_D); R(167, 53, 168, 55, WOOD_D)
bx = 120
for i in range(8):
    h = random.randint(6, 10); c = BOOKS[i % len(BOOKS)]
    R(bx, 50 - h, bx + 1 + (i % 2), 49, c); bx += 3 + (i % 2)
R(150, 44, 156, 49, POT)
for (x, y) in [(150, 43), (152, 41), (154, 42), (156, 43), (153, 39), (151, 40), (155, 40)]: px(x, y, GREEN)
for y in range(53, 66): px(162 + (y // 3) % 2, y, GREEN if y % 2 else GREEN_D)
R(161, 46, 166, 49, CREAM_D)  # little jar of candy lights
# desk
DESK_D = 0.75
R(118, 82, 121, FL, WOOD_D); R(169, 82, 172, FL, WOOD_D)                           # back legs (against the wall)
block(140, 82, 168, 92, 0.05, DESK_D - 0.05, WOOD, side=WOOD_D, bottom=WOOD_D)      # drawer unit
Rd(141, 83, 167, 91, DESK_D - 0.05, WOOD_D); Rd(142, 84, 166, 90, DESK_D - 0.05, WOOD); Rd(152, 87, 155, 87, DESK_D - 0.05, WOOD_L)
block(116, 78, 174, 82, 0, DESK_D, WOOD, top=WOOD_L)                                 # desk top
Ld([(116, 82), (174, 82)], DESK_D, WOOD_D)
for lx in (118, 169): block(lx, 82, lx + 3, FL, DESK_D - 0.08, DESK_D, WOOD_D, side=(84, 52, 34))   # front legs
# record player
R(120, 72, 138, 77, DARK); E([123, 70, 135, 74], (24, 20, 28)); px(129, 72, (230, 120, 140))
R(136, 66, 136, 72, (190, 190, 200))
# open sketchbook
P([(140, 77), (152, 75), (152, 77), (140, 78)], CREAM)
# candle
R(155, 72, 157, 77, CREAM); (px(156, 71, (255, 200, 90), True), px(156, 70, (255, 240, 180), True)) if NIGHT else px(156, 71, DARK)
# lamp
R(162, 76, 170, 77, WOOD_D); R(165, 67, 166, 76, WOOD_D)
P([(159, 67), (172, 67), (169, 59), (162, 59)], LAMP if LAMP_ON else (236, 214, 176), LAMP_ON)
# chair (back toward viewer)
holiday_layer("desk")
_before_chair = img.copy()
C0, C1 = 0.95, 1.4        # chair from 0.95 m to 1.4 m out from the wall
for lx in (133, 151): block(lx, 87, lx + 2, FL, C0, C0 + 0.05, WOOD_D)                 # back legs (far)
block(132, 86, 154, 88, C0, C1, WOOD, top=WOOD_L, side=WOOD_D)                         # seat
for lx in (133, 151): block(lx, 66, lx + 2, FL, C1 - 0.05, C1, WOOD_D, side=(84, 52, 34))   # front legs + back posts
block(132, 66, 154, 69, C1 - 0.06, C1, WOOD, top=WOOD_L)                               # top rail
block(134, 74, 152, 76, C1 - 0.05, C1, WOOD_D)                                         # middle rail
# the chair's outline, so holiday decorations on the desk can be tucked behind it
CHAIR_MASK = Image.fromarray(((np.asarray(img).astype(int) - np.asarray(_before_chair).astype(int)) != 0).any(axis=2).astype(np.uint8) * 255)

# ---------- right side: (wide room) picture, floor lamp, nightstand; then the bed ----------
BR = 262 if WIDE else W + 24          # bed's right edge, at the wall
BED_L, BED_D = 182, 2.2               # bed's left edge at the wall, and how far it comes out
MUSTARD = (214, 164, 84); MUSTARD_D = (178, 128, 60); MUSTARD_L = (236, 192, 110); MUSTARD_DD = (150, 104, 48)
if WIDE:
    # framed picture with a little depth
    block(286, 24, 324, 52, 0, 0.05, WOOD_D, bottom=(84, 52, 36), top=(84, 52, 36), side=(84, 52, 36))
    Rd(288, 26, 322, 50, 0.05, (238, 214, 180)); Rd(290, 28, 320, 48, 0.05, (150, 190, 220)); Rd(290, 40, 320, 48, 0.05, (110, 150, 110))
    Pd([(290, 40), (300, 32), (308, 40)], 0.05, (96, 130, 96)); Pd([(302, 40), (312, 30), (320, 40)], 0.05, (84, 118, 88))
    Ed([313, 29, 318, 34], 0.05, (255, 236, 170))
    # nightstand: top, side and front all follow the room's lines
    NS_D = 0.5
    block(268, 82, 292, FL, 0, NS_D, WOOD, top=WOOD_L, side=WOOD_D)
    Rd(270, 86, 290, 92, NS_D, WOOD_D); Rd(271, 87, 289, 91, NS_D, WOOD); Rd(279, 89, 281, 89, NS_D, WOOD_L)
    Rd(270, 94, 290, 101, NS_D, WOOD_D); Rd(271, 95, 289, 100, NS_D, WOOD)
    NX, NY = (round(v) for v in wp(279, 82, 0.2))
    block(277, 76, 279, 82, 0.18, 0.22, WOOD_D)                                    # lamp stem
    Pd([(272, 76), (284, 76), (281, 69), (275, 69)], 0.2, LAMP if LAMP_ON else (236, 214, 176), LAMP_ON)
    block(284, 80, 290, 82, 0.1, 0.35, BOOKS[1], top=(130, 180, 196)); block(285, 78, 289, 80, 0.15, 0.3, BOOKS[0], top=(226, 130, 130))

# bed: headboard against the wall, frame + mattress + quilt coming out to BED_D
block(BED_L - 2, 60, BR + 2, 96, 0, 0.08, WOOD, top=WOOD_L, side=WOOD_D)
Rd(BED_L, 63, BR, 85, 0.08, WOOD_D)
for x in range(BED_L + 4, BR - 4, 12): Rd(x, 63, x + 8, 85, 0.08, WOOD)
Ld([(BED_L - 2, 60), (BR + 2, 60)], 0.08, WOOD_L)
if WIDE:
    block(BR - 1, 56, BR + 3, 96, 0.06, 0.14, WOOD_L, side=WOOD)                    # headboard post
block(BED_L, 94, BR, FL, 0.08, BED_D, WOOD, top=WOOD, side=WOOD_D)                  # frame
block(BED_L + 1, 88, BR - 1, 94, 0.1, BED_D - 0.02, CREAM, top=CREAM, side=CREAM_D)  # mattress
# pillows, resting on the mattress near the headboard
for (a, b, c, e_, col, hi) in ([(188, 78, 212, 92, CREAM, (252, 242, 222)), (210, 77, 238, 93, CREAM_D, CREAM), (236, 78, 258, 92, CREAM, (252, 242, 222))]):
    Ed([a, b, c, e_], 0.3, col); Ed([a + 2, b + 2, c - 4, e_ - 4], 0.3, hi)
# quilt: lies on the front part of the bed and hangs over the front and the left side
Q0 = 0.85
block(BED_L - 1, 87, BR + 1, 99, Q0, BED_D + 0.03, BLANK_D, top=BLANK, side=(146, 60, 58))
block(BED_L - 1, 86, BR + 1, 87, Q0, Q0 + 0.22, BLANK_L, top=BLANK_L, side=BLANK)    # turned-down edge
for x in range(BED_L + 14, BR, 16):                                                  # folds run toward the back
    d.line(_q([wp(x, 87, Q0 + 0.25), wp(x, 87, BED_D + 0.03), wp(x, 99, BED_D + 0.03)]), fill=(178, 80, 74))
for i, x in enumerate(range(BED_L + 4, BR - 2, 8)):                                  # little squares on the quilt top
    for j, dd in enumerate((1.25, 1.65, 2.05)):
        if (i + j) % 2 == 0:
            px_, py_ = wp(x, 87, dd); R(round(px_), round(py_), round(px_) + 1, round(py_), QUILT2)
for i, x in enumerate(range(BED_L + 8, BR - 2, 8)):                                  # and on the hanging front
    for y in (91, 96):
        if (i + y // 5) % 2 == 0:
            px_, py_ = wp(x, y, BED_D + 0.03); R(round(px_), round(py_), round(px_) + 1, round(py_) + 1, QUILT2)

# ---------- wall shelf above the bed: fish tank + digital clock ----------
R(186, 54, 236, 55, WOOD); R(186, 56, 236, 56, WOOD_D)
R(190, 57, 191, 59, WOOD_D); R(231, 57, 232, 59, WOOD_D)
# tank
R(190, 41, 212, 53, (52, 44, 56))                 # frame
R(191, 43, 211, 52, (112, 186, 206))              # water
R(191, 43, 211, 43, (150, 210, 226))              # water surface shine
R(191, 51, 211, 52, (222, 200, 150))              # sand
E([203, 49, 208, 53], (130, 120, 130)); px(205, 50, (160, 150, 160))   # rock
for y in range(45, 51): px(194 + (y % 2), y, GREEN)                    # weed
for y in range(47, 51): px(198 - (y % 2), y, GREEN_D)
R(190, 40, 212, 41, (70, 60, 74))                 # lid
# clock body (digits are drawn live by the app)
R(214, 45, 234, 53, (44, 38, 48)); R(215, 46, 233, 52, (22, 26, 24))
px(216, 53, (30, 26, 34)); px(232, 53, (30, 26, 34))

# ---------- left wall bookshelf (built out from the wall) ----------
def wall_quad(x0, x1, t0, t1, c):
    P(_q([(x0, lw(x0, t0)), (x1, lw(x1, t0)), (x1, lw(x1, t1)), (x0, lw(x0, t1))]), c)
XL = (LW - VPX) * 10 / 400               # the left wall is the plane X = XL
def wz(x): return 400 * XL / (x - VPX)   # depth of a left-wall point drawn at screen x
def wy(t): return 2.25 * (1 - t)         # height for a left-wall t (0 = ceiling, 1 = floor)
def lq(pts, c):                          # pts in world coords
    P(_q([pj(*p) for p in pts]), c)
SH_E = 0.26                              # shelf sticks out this far from the wall
SX0, SX1 = 0, 24                       # shelf spans these screen x's along the left wall
za, zb = wz(SX0), wz(SX1); ya, yb = wy(.22), 0.0          # top of the shelf, and it stands on the floor
lq([(XL, ya, za), (XL, ya, zb), (XL, yb, zb), (XL, yb, za)], (62, 40, 30))          # back panel
lq([(XL, ya, zb), (XL + SH_E, ya, zb), (XL + SH_E, yb, zb), (XL, yb, zb)], WOOD_D)   # far end panel (behind the books)
for k in range(4):
    t0 = .24 + k * .155; t1 = t0 + .13
    y1 = wy(t1); x = SX0 + 2
    while x < SX1 - 3:                                                                    # books stand on each board
        w = random.choice([2, 2, 3]); h = random.uniform(.08, .125) * 2.25
        z0, z1 = wz(x), wz(min(x + w, SX1 - 2)); c = random.choice(BOOKS)
        xe = XL + SH_E - 0.05
        lq([(XL + 0.04, y1 + h, z0), (xe, y1 + h, z0), (xe, y1, z0), (XL + 0.04, y1, z0)], tuple(int(v * .8) for v in c))  # near side of book
        lq([(xe, y1 + h, z0), (xe, y1 + h, z1), (xe, y1, z1), (xe, y1, z0)], c)                                            # spine
        x += w + 1
    yb_ = wy(t1 + .02)
    lq([(XL, y1, za), (XL + SH_E, y1, za), (XL + SH_E, y1, zb), (XL, y1, zb)], WOOD) if y1 < 1.6 else None              # board top (only seen below eye level)
    lq([(XL, yb_, za), (XL + SH_E, yb_, za), (XL + SH_E, yb_, zb), (XL, yb_, zb)], WOOD_D) if yb_ > 1.6 else None       # board underside (above eye level)
    lq([(XL + SH_E, y1, za), (XL + SH_E, y1, zb), (XL + SH_E, yb_, zb), (XL + SH_E, yb_, za)], WOOD_L)                 # board front edge
lq([(XL, ya, za), (XL + SH_E, ya, za), (XL + SH_E, ya, zb), (XL, ya, zb)], WOOD_D)                                     # top underside
yc = wy(.875)                                                                                                            # closed cupboard at the bottom
lq([(XL + SH_E, yc, za), (XL + SH_E, yc, zb), (XL + SH_E, 0, zb), (XL + SH_E, 0, za)], WOOD_D)
zm = (za + zb) / 2
for (z0_, z1_) in ((za + 0.1, zm - 0.04), (zm + 0.04, zb - 0.1)):                                                       # two doors
    lq([(XL + SH_E, yc - 0.06, z0_), (XL + SH_E, yc - 0.06, z1_), (XL + SH_E, 0.06, z1_), (XL + SH_E, 0.06, z0_)], WOOD)
    k_ = pj(XL + SH_E, yc / 2, z1_ - 0.08 if z0_ < zm else z0_ + 0.08); R(round(k_[0]), round(k_[1]), round(k_[0]), round(k_[1]) + 1, WOOD_L)
lq([(XL, ya, za), (XL + SH_E, ya, za), (XL + SH_E, yb, za), (XL, yb, za)], WOOD)                                       # near end panel
lq([(XL + SH_E, ya, za), (XL + SH_E, ya, za + 0.08), (XL + SH_E, yb, za + 0.08), (XL + SH_E, yb, za)], WOOD_L)           # its front edge
lq([(XL + SH_E, ya, zb - 0.08), (XL + SH_E, ya, zb), (XL + SH_E, yb, zb), (XL + SH_E, yb, zb - 0.08)], WOOD_L)           # far end's front edge
# framed art on left wall
wall_quad(14, 30, .08, .19, WOOD_D); wall_quad(15, 29, .095, .18, (230, 170, 130))
wall_quad(15, 29, .145, .18, (110, 90, 130))

# ---------- string lights (along top of back wall) ----------
bulbs = []
for x in range(LW, W, 2):
    y = CT + 3 + int(5 * abs(math.sin((x - LW) / 42 * math.pi)))
    px(x, y, (60, 44, 50))
    if (x - LW) % 10 == 0:
        c = BULB[((x - LW) // 10) % 3]
        on = TIME in ("night", "sunset") or WEATHER in ("storm", "rain") and TIME != "day"
        c = c if on else (110, 96, 96)
        px(x, y + 1, c, on); px(x, y + 2, c, on); bulbs.append((x, y + 2))
# lights also along left wall top edge
for x in range(0, LW, 2):
    y = int(lw_top(x)) + 3 + int(3 * abs(math.sin(x / 22 * math.pi)))
    px(x, y, (60, 44, 50))
    if x % 10 == 4:
        c = BULB[(x // 10) % 3]; on = TIME in ("night", "sunset") or WEATHER in ("storm", "rain") and TIME != "day"
        c = c if on else (110, 96, 96)
        px(x, y + 1, c, on); px(x, y + 2, c, on); bulbs.append((x, y + 2))

holiday_layer("wall")
# ---------- wide room corner: floor lamp, small rug, armchair ----------
def shade(c, k): return tuple(max(0, min(255, int(v * k))) for v in c)
def wbox(cx, cz, a, dx, dz, w, dep, y0, y1, base, kt=1.14, kf=1.0, ks=0.74, edge=True):
    """Box in the chair's own frame (turned by a), drawn with only its visible faces, flat colours + soft edges."""
    ca, sa = math.cos(a), math.sin(a)
    def c(sx, sz, y):
        lx = dx + sx * w / 2; lz = dz + sz * dep / 2
        return (cx + lx * ca - lz * sa, y, cz + lx * sa + lz * ca)
    faces = [("top", [c(-1, -1, y1), c(1, -1, y1), c(1, 1, y1), c(-1, 1, y1)], kt),
             ("front", [c(-1, -1, y0), c(1, -1, y0), c(1, -1, y1), c(-1, -1, y1)], kf),
             ("back", [c(-1, 1, y0), c(1, 1, y0), c(1, 1, y1), c(-1, 1, y1)], kf * 0.9),
             ("left", [c(-1, -1, y0), c(-1, 1, y0), c(-1, 1, y1), c(-1, -1, y1)], ks),
             ("right", [c(1, -1, y0), c(1, 1, y0), c(1, 1, y1), c(1, -1, y1)], ks * 0.9)]
    ctr = (cx + dx * ca - dz * sa, (y0 + y1) / 2, cz + dx * sa + dz * ca)
    for name, pts, k in faces:
        fc = [sum(p[i] for p in pts) / 4 for i in range(3)]
        out = [fc[i] - ctr[i] for i in range(3)]                       # outward direction
        tocam = [0 - fc[0], 1.6 - fc[1], 0 - fc[2]]
        if sum(out[i] * tocam[i] for i in range(3)) <= 0: continue
        poly = _q([pj(*p) for p in pts]); col = shade(base, k)
        d.polygon(poly, fill=col, outline=shade(col, 0.82) if edge else None)
if WIDE:
    # floor lamp standing in the corner
    LX, LZ = 4.15, 9.55
    lb = pj(LX, 0, LZ); lt = pj(LX, 1.22, LZ)
    E([round(lb[0]) - 5, round(lb[1]) - 2, round(lb[0]) + 5, round(lb[1]) + 1], (70, 54, 48)); E([round(lb[0]) - 4, round(lb[1]) - 2, round(lb[0]) + 4, round(lb[1])], (90, 70, 60))
    R(round(lt[0]), round(lt[1]), round(lt[0]) + 1, round(lb[1]) - 1, (90, 70, 60))
    LMX, LMY = round(lt[0]), round(lt[1])
    P([(LMX - 7, LMY), (LMX + 8, LMY), (LMX + 5, LMY - 10), (LMX - 4, LMY - 10)], LAMP if LAMP_ON else (236, 214, 176), LAMP_ON)
    E([LMX - 7, LMY - 2, LMX + 8, LMY + 1], (220, 180, 120) if LAMP_ON else (214, 192, 156), LAMP_ON)
    # small round rug in front of the chair
    E([290, 124, 350, 146], RUG_D); E([292, 124, 350, 144], (170, 110, 120)); E([302, 128, 346, 140], (190, 130, 136))
    # armchair, turned to face into the room
    AX, AZ = 3.95, 9.25
    A = math.atan2(1.2 - AX, -(6.2 - AZ))         # local front (-z) points toward the middle of the room
    M = MUSTARD
    for sx in (-1, 1):
        for sz in (1, -1):
            wbox(AX, AZ, A, sx * 0.3, sz * 0.27, 0.05, 0.05, 0.0, 0.1, WOOD_D, edge=False)   # legs
    parts = [  # (dx, dz, w, depth, y0, y1, colour, top, front, side)
        (0.0, 0.31, 0.8, 0.16, 0.1, 0.92, M, 1.12, 0.92, 0.72),            # backrest
        (0.0, 0.0, 0.8, 0.74, 0.1, 0.34, M, 1.1, 0.96, 0.7),               # base
        (0.0, -0.05, 0.52, 0.56, 0.34, 0.44, M, 1.24, 1.06, 0.86),         # seat cushion
        (-0.33, -0.01, 0.14, 0.72, 0.1, 0.6, M, 1.22, 1.0, 0.74),          # arms
        (0.33, -0.01, 0.14, 0.72, 0.1, 0.6, M, 1.22, 1.0, 0.74),
    ]
    def dist(p):
        dx, dz = p[0], p[1]; ca, sa = math.cos(A), math.sin(A)
        X = AX + dx * ca - dz * sa; Z = AZ + dx * sa + dz * ca; return math.hypot(X, Z)
    backrest, base_, cushion, armL, armR = parts
    far_arm, near_arm = sorted([armL, armR], key=dist, reverse=True)
    for p in (backrest, far_arm, base_, cushion, near_arm):
        wbox(AX, AZ, A, *p[:6], p[6], p[7], p[8], p[9])
    wbox(AX, AZ, A, 0.18, 0.26, 0.3, 0.1, 0.5, 0.95, BLANK, 1.1, 1.0, 0.78)       # throw blanket over the back
    wbox(AX, AZ, A, -0.05, 0.1, 0.32, 0.12, 0.44, 0.7, QUILT2, 1.1, 1.0, 0.8)     # little cushion leaning on the back

_snap_prerug = img.copy()
# ---------- rug + floor clutter ----------
E([58, 112, 168, 148], RUG_D); E([60, 112, 166, 146], RUG); E([72, 117, 154, 141], RUG_L); E([80, 120, 146, 138], RUG)
for a in range(0, 360, 20):
    x = 113 + int(50 * math.cos(math.radians(a))); y = 129 + int(16 * math.sin(math.radians(a)))
    px(x, y, CREAM)
# floor cushion + book stack + slippers
E([92, 122, 120, 136], SAGE); E([95, 123, 117, 132], (146, 180, 140))
def floor_box(x0, x1, z0, z1, y0, y1, front, top, side):
    pts = lambda Y, Z: [pj(x0, Y, Z), pj(x1, Y, Z)]
    if x0 > 0: P(_q([pj(x0, y0, z0), pj(x0, y0, z1), pj(x0, y1, z1), pj(x0, y1, z0)]), side)
    if x1 < 0: P(_q([pj(x1, y0, z0), pj(x1, y0, z1), pj(x1, y1, z1), pj(x1, y1, z0)]), side)
    P(_q([pj(x0, y1, z1), pj(x1, y1, z1), pj(x1, y1, z0), pj(x0, y1, z0)]), top)
    P(_q([pj(x0, y0, z0), pj(x1, y0, z0), pj(x1, y1, z0), pj(x0, y1, z0)]), front)
bx0, _, bz = to_world(124, 130); bz = 640 / (130 - 40)
for i, (dx, c) in enumerate([(0.0, BOOKS[0]), (0.03, BOOKS[1]), (-0.03, BOOKS[2])]):
    X0 = (124 - VPX) * bz / 400 + dx
    floor_box(X0, X0 + 0.24, bz - 0.17, bz, i * 0.05, i * 0.05 + 0.045, c, CREAM if i == 2 else tuple(min(255, v + 30) for v in c), tuple(int(v * .75) for v in c))
R(140, 124, 146, 125, CREAM_D)
E([150, 138, 158, 142], (200, 160, 200)); E([158, 139, 166, 143], (200, 160, 200))


_snap_postrug = img.copy()
holiday_layer("floor")
# ---------- the pal (scene-dependent) ----------
BLUSH = (240, 140, 160); HI = (255, 255, 255)
def zzz(x, y):
    for (zx, zy, s) in [(x, y, 2), (x + 4, y - 6, 3)]:
        R(zx, zy, zx + s, zy, CREAM, True); R(zx, zy + s, zx + s, zy + s, CREAM, True)
        for k in range(s + 1): px(zx + s - k, zy + k, CREAM, True)
def note(x, y, c=(140, 220, 210)):
    R(x, y, x, y + 3, c, True); px(x - 1, y + 3, c, True); px(x - 2, y + 3, c, True); px(x + 1, y, c, True); px(x + 2, y + 1, c, True)
def pal(cx, top, face="open", back=False, body=True):
    if body:
        E([cx - 9, top, cx + 9, top + 18], PAL)
        if not back: E([cx - 7, top + 9, cx + 7, top + 18], PAL_D)
        else: E([cx - 6, top + 2, cx + 2, top + 8], (170, 236, 196))
    if back: return
    ey = top + 5
    if face == "open":
        R(cx - 4, ey, cx - 3, ey + 2, DARK); R(cx + 3, ey, cx + 4, ey + 2, DARK)
        px(cx - 1, top + 10, DARK); px(cx, top + 11, DARK); px(cx + 1, top + 10, DARK)
    elif face == "sleep":
        R(cx - 5, ey + 1, cx - 3, ey + 1, DARK); R(cx + 3, ey + 1, cx + 5, ey + 1, DARK); px(cx, top + 10, DARK)
    elif face == "happy":
        for dx in (-4, 4):
            px(cx + dx - 1, ey + 1, DARK); px(cx + dx, ey, DARK); px(cx + dx + 1, ey + 1, DARK)
        R(cx - 1, top + 10, cx + 1, top + 11, DARK)
    elif face == "wide":
        for dx in (-4, 4):
            R(cx + dx - 1, ey - 1, cx + dx + 1, ey + 2, DARK); px(cx + dx - 1, ey - 1, HI, True)
        px(cx, top + 11, DARK)
    elif face == "focus":
        R(cx - 4, ey + 1, cx - 3, ey + 2, DARK); R(cx + 3, ey + 1, cx + 4, ey + 2, DARK)
        R(cx - 5, ey - 1, cx - 3, ey - 1, DARK); R(cx + 3, ey - 1, cx + 5, ey - 1, DARK)
        px(cx + 1, top + 11, DARK)
    if face != "wide": px(cx - 6, top + 9, BLUSH); px(cx + 6, top + 9, BLUSH)

S = SCENE
if S in ("lump0", "lump1"):          # asleep completely under the quilt: a rounded lump, lit from the left
    LCX, LBY = 222, 98               # lump centre and the quilt line its front rests on
    A_, C_ = 12.5, 10.5 + (1 if S == "lump1" else 0)        # half-width and height in pixels (rises on the in-breath)
    TONES = [(128, 52, 50), (156, 66, 62), (180, 80, 74), BLANK, (214, 112, 98), (232, 136, 118)]
    Lx, Ly, Lz = -0.55, 0.65, 0.52                          # light from the upper left, a little toward us
    for y in range(int(LBY - C_) - 1, LBY + 1):
        for x in range(int(LCX - A_) - 1, int(LCX + A_) + 2):
            u = (x + 0.5 - LCX) / A_; v = (LBY + 0.5 - y) / C_
            r2 = u * u + v * v
            if r2 > 1 or v < 0: continue
            nz = math.sqrt(1 - r2)
            k = (u * Lx + v * Ly + nz * Lz)                  # -1..1
            k = max(0.0, min(0.999, 0.18 + 0.82 * k))
            px(x, y, TONES[int(k * len(TONES))])
    for (u, v) in ((-0.55, 0.45), (-0.1, 0.55), (0.35, 0.45), (-0.3, 0.15), (0.15, 0.2), (0.6, 0.15)):   # quilt squares follow the curve
        x = round(LCX + u * A_); y = round(LBY - v * C_ * 1.05)
        R(x, y, x + 1, y, QUILT2)
    d.line([(round(LCX - A_) + 1, LBY + 1), (round(LCX + A_) - 1, LBY + 1)], fill=(156, 66, 62))   # contact shadow on the quilt
if S == "sleep":                      # asleep in bed
    pal(205, 86, "sleep"); P([(192, 98), (218, 98), (220, 104), (190, 104)], QUILT2); zzz(216, 80)
elif S == "stretch":                  # sunrise stretch in bed
    pal(205, 82, "happy")
    d.line([(196, 88), (191, 78)], fill=PAL, width=2); d.line([(214, 88), (219, 78)], fill=PAL, width=2)
    P([(192, 98), (218, 98), (220, 104), (190, 104)], QUILT2)
elif S == "mug":                      # window seat with mug
    pal(88, 60, "happy")
    R(85, 70, 90, 75, CREAM); px(91, 72, CREAM); px(91, 73, CREAM)
    px(87, 67, (230, 230, 240)); px(88, 65, (230, 230, 240)); px(87, 63, (230, 230, 240))
elif S == "watch":                    # sunset: watching from window seat, back turned
    pal(86, 60, back=True)
elif S == "rain":                     # wrapped in blanket watching rain
    pal(86, 58, "open")
    P([(74, 77), (98, 77), (95, 66), (86, 64), (77, 66)], BLANK)
    d.line([(86, 66), (86, 77)], fill=BLANK_D); P([(77, 66), (86, 64), (95, 66), (86, 69)], BLANK_L)
elif S == "snow":                     # pressed up to the glass
    fog = Image.new("RGB", (W, H), (235, 240, 250)); fm = Image.new("L", (W, H), 0)
    ImageDraw.Draw(fm).ellipse([76, 50, 96, 62], fill=150)
    img.paste(fog, (0, 0), fm); emis.paste(255, (0, 0), fm); d = ImageDraw.Draw(img); de = ImageDraw.Draw(emis)
    pal(86, 56, back=True)
    E([74, 60, 79, 65], PAL); E([93, 60, 98, 65], PAL)    # little hands on glass
elif S == "draw":                     # drawing at the desk (from behind)
    pal(143, 66, back=True)
    d.line([(152, 76), (155, 72)], fill=(240, 200, 80), width=1)
    R(132, 88, 154, 90, WOOD); R(133, 92, 153, 94, WOOD_D)
elif S == "read":                     # reading on the rug cushion
    pal(106, 110, "focus")
    P([(97, 121), (106, 119), (106, 128), (97, 129)], BOOKS[3]); P([(106, 119), (115, 121), (115, 129), (106, 128)], BOOKS[3])
    P([(98, 121), (106, 120), (106, 127), (98, 128)], CREAM); P([(106, 120), (114, 121), (114, 128), (106, 127)], CREAM_D)
elif S == "music":                    # vibing to the record on the cushion
    pal(106, 108, "happy")
    d.line([(95, 112), (93, 110)], fill=CREAM); d.line([(117, 112), (119, 110)], fill=CREAM)
    note(124, 62); note(116, 56); note(108, 98, (250, 200, 120)); note(122, 94)
elif S == "hide":                     # storm: hiding under the quilt
    P([(190, 104), (196, 88), (214, 86), (222, 104)], BLANK)
    P([(196, 88), (214, 86), (216, 92), (194, 94)], BLANK_L)
    R(199, 95, 213, 99, DARK)
    for dx in (202, 210): R(dx - 1, 96, dx + 1, 98, (250, 250, 240)); px(dx, 97, DARK)
    for (x, y) in [(186, 92), (224, 92), (188, 86), (222, 84)]: px(x, y, CREAM)

# ---------- trainer's things (wide room): user-provided item sprites, at the room's own pixel scale ----------
if WIDE:
    # berries + fruit in a wooden bowl on the window seat, in front of the folded blanket
    place("berry_blue", 3, 82, 77); place("fruit_yellow", 3, 88, 77); place("berry_orange", 3, 85, 76)
    E([77, 75, 93, 80], (118, 82, 58)); E([78, 75, 92, 77], (156, 112, 78)); R(79, 78, 91, 78, (100, 68, 48))
    place("berry_blue", 3, 81, 78); place("berry_orange", 3, 89, 78)
    # potions lined up on the shelf above the desk
    for i, p in enumerate(("potion_purple", "potion_pink", "potion_orange")):
        place(p, 3, 159 + i * 6, 50)
    # an Ultra Ball tipped on its side on the headboard (nothing hangs above there)
    place("ultraball_15", 3, 250, 60)
    # Poké Ball (turned) and black glasses on the nightstand (glasses resting on the books)
    place("pokeball_13", 3, 272, 83); place("glasses_black", 3, 287, 78)
    # a Great Ball tilted back on the armchair's seat cushion
    place("greatball_12", 3, 314, 91)
    # a Fast Ball on the little rug by the armchair
    place("fastball", 3, 318, 136)
    # round glasses resting on the book stack on the rug
    place("glasses_round", 3, 131, 123)

_snap_prefg = img.copy()
# ---------- foreground (closer, darker) ----------
P([(-4, 114), (24, 114), (27, 160), (-4, 160)], POT)
P([(16, 114), (24, 114), (27, 160), (19, 160)], POT_D)
E([-6, 108, 26, 120], POT_D); E([-4, 110, 24, 118], (70, 50, 40))
for _ in range(70):
    a = random.uniform(-2.6, -0.4); L = random.uniform(10, 34)
    x0, y0 = 10, 112
    x1 = x0 + L * math.cos(a) * 1.2; y1 = y0 + L * math.sin(a)
    d.line([(x0, y0), (x1, y1)], fill=random.choice([GREEN_D, GREEN_DD, GREEN]), width=2)
_snap_fgplant = img.copy()   # the floor plant is in front of every decoration
# hanging plant from ceiling (right foreground)
d.line([(246, 0), (246, 18)], fill=(60, 44, 40))
E([238, 18, 254, 28], POT_D); E([238, 17, 254, 23], POT); E([240, 18, 252, 22], (70, 50, 40))

# ---------- shadows under furniture ----------
shadow = Image.new("L", (W, H), 0); sd = ImageDraw.Draw(shadow)
for kind, geom, val in globals().get("DECO_SHADOWS", []):          # holiday decorations' contact shadows
    (sd.ellipse if kind == "ellipse" else sd.polygon)(geom, fill=val)
def fpoly(pts): return _q([wp(x, FL, dd) for x, dd in pts])
sd.polygon(fpoly([(116, 0), (174, 0), (176, DESK_D + 0.15), (114, DESK_D + 0.15)]), fill=90)              # desk
sd.polygon(_q([pj(XL, 0, za - 0.1), pj(XL + SH_E + 0.12, 0, za - 0.1), pj(XL + SH_E + 0.12, 0, zb), pj(XL, 0, zb)]), fill=90)  # bookshelf
sd.polygon(fpoly([(132, C0), (154, C0), (156, C1 + 0.12), (130, C1 + 0.12)]), fill=70)                    # chair
sd.polygon(fpoly([(wx0 - 8, SEAT_D), (wx1 + 8, SEAT_D), (wx1 + 10, SEAT_D + 0.2), (wx0 - 10, SEAT_D + 0.2)]), fill=90)
sd.polygon(fpoly([(BED_L - 2, BED_D), (BR + 4, BED_D), (BR + 6, BED_D + 0.35), (BED_L - 6, BED_D + 0.35)]), fill=110)
sd.polygon(fpoly([(BED_L - 8, 0.2), (BED_L, 0.2), (BED_L, BED_D), (BED_L - 8, BED_D)]), fill=70)
if WIDE:
    sd.polygon(_q([pj(AX - 0.5, 0, AZ - 0.55), pj(AX + 0.45, 0, AZ - 0.6), pj(AX + 0.5, 0, AZ + 0.2), pj(AX - 0.45, 0, AZ + 0.3)]), fill=90)
sd.ellipse([56, 140, 168, 152], fill=50)
sd.polygon([(0, 150), (28, 150), (34, 160), (0, 160)], fill=80)

# shadows fall on the floor and rug only, never on the furniture casting them (or anything in front)
A_ = lambda im: np.asarray(im.convert("RGB")).astype(int)
objs = (A_(_snap_prerug) != A_(_snap_shell)).any(2) | (A_(img) != A_(_snap_postrug)).any(2)
_audit_sh = np.asarray(shadow) > 0
shadow = Image.fromarray(np.where(objs, 0, np.asarray(shadow)).astype(np.uint8))
if os.environ.get("AUDIT"):
    sh_ = _audit_sh
    bad = objs & sh_
    vis = A_(img).astype(np.uint8).copy()
    vis[sh_ & ~objs] = (vis[sh_ & ~objs] * 0.5 + np.array([0, 90, 255]) * 0.5).astype(np.uint8)   # blue: shadow on floor (fine)
    vis[bad] = (255, 0, 60)                                                                         # red: shadow on furniture
    Image.fromarray(vis).save(f"audit_shadow_{'wide' if WIDE else 'normal'}.png")
    print("shadow on objects (before clipping):", int(bad.sum()), "px; after:", int((objs & (np.asarray(shadow) > 0)).sum()))
# ---------- lighting pass ----------
base = np.asarray(img).astype(np.float32) / 255
yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
AMB = {"sunrise": (0.66, 0.56, 0.60), "day": (0.80, 0.80, 0.78), "sunset": (0.64, 0.50, 0.48), "night": (0.36, 0.34, 0.50)}[TIME]
WMUL = {"clear": 1.0, "cloudy": .86, "rain": .74, "storm": .58, "snow": .92}[WEATHER]
amb = np.array(AMB) * WMUL
if WEATHER in ("rain", "storm", "snow", "cloudy") and not NIGHT: amb = amb * 0.8 + amb.mean() * 0.2 * np.array([0.95, 0.98, 1.08])
light = np.zeros((H, W, 3), np.float32) + amb
def add(cx, cy, rad, col, k):
    dist = np.sqrt((xx - cx) ** 2 + ((yy - cy) * 1.15) ** 2)
    f = np.clip(1 - dist / rad, 0, 1) ** 1.8 * k
    light[...] += f[..., None] * np.array(col)
if LAMP_ON: add(165, 66, 95, (1.0, 0.70, 0.40), 0.95 if NIGHT or WEATHER == "storm" else 0.55)
if LAMP_ON and WIDE:
    add(NX, NY - 9, 46, (1.0, 0.72, 0.42), 0.6)                                                  # nightstand lamp
    add(LMX, LMY - 4, 80, (1.0, 0.70, 0.40), 0.8 if NIGHT or WEATHER == "storm" else 0.45)        # floor lamp
if NIGHT: add(156, 70, 26, (1.0, 0.68, 0.35), 0.45)
for (lx_, ly_, lr_, lc_, lk_) in globals().get("DECO_LIGHTS", []):   # glowing holiday decorations
    add(lx_, ly_, lr_, lc_, lk_)
bulbs_on = TIME in ("night", "sunset") or WEATHER in ("storm", "rain") and TIME != "day"
if bulbs_on:
    for (bx_, by_) in bulbs: add(bx_, by_, 16, (1.0, 0.72, 0.5), 0.25)
WIN = {"sunrise": (1.0, 0.70, 0.60), "day": (1.0, 0.96, 0.85), "sunset": (1.0, 0.58, 0.32), "night": (0.45, 0.55, 0.85)}[TIME]
wk = {"clear": 1.0, "cloudy": .55, "rain": .4, "storm": .3, "snow": .6}[WEATHER]
if WEATHER != "clear": WIN = tuple(0.6 * c + 0.4 * 0.8 for c in WIN)
# light from the window: only what comes through the open glass, falling down onto the window seat and
# the wall right around the frame. The curtains block it (it doesn't shine through them), and it doesn't
# reach across to the desk.
curtains = (np.asarray(_snap_postcurtain).astype(int) != np.asarray(_snap_precurtain).astype(int)).any(2)
curtains &= (np.asarray(img).astype(int)[..., :3] == np.asarray(_snap_postcurtain).astype(int)[..., :3]).all(2)   # only where still visible (not under the pillows)
wl = Image.new("L", (W, H), 0)
ImageDraw.Draw(wl).polygon([(wx0 + 2, wy0 - 12), (wx1 - 2, wy0 - 12), (wx1 + 16, FL + 2), (wx0 - 16, FL + 2)], fill=255)
wl = wl.filter(ImageFilter.GaussianBlur(9))        # wide, soft spread: nothing on the seat gets cut in half
wla = np.asarray(wl).astype(np.float32) / 255
wla *= np.clip(1.0 - (yy - wy0) / (FL - wy0) * 0.55, 0.3, 1.0)        # strongest by the glass
wla *= ~curtains
light += wla[..., None] * np.array(WIN) * (0.42 if NIGHT else 0.5) * wk
patch = {"sunrise": [(70, FL + 4), (112, FL + 4), (150, 150), (88, 150)], "day": [(64, FL + 4), (108, FL + 4), (124, 150), (54, 150)],
         "sunset": [(60, FL + 4), (102, FL + 4), (64, 150), (10, 150)], "night": [(64, FL + 4), (108, FL + 4), (124, 150), (54, 150)]}[TIME]
# the pool of window light on the floor: starts just in front of the window seat, soft-edged like real
# light, and only on the floor/rug (furniture and things standing in it aren't painted with it)
seat_front = round(wp(0, FL, SEAT_D + 0.05)[1])
patch = [(x, max(y, seat_front)) for x, y in patch]
mp = Image.new("L", (W, H), 0); ImageDraw.Draw(mp).polygon(patch, fill=int(70 * wk))
mp = mp.filter(ImageFilter.GaussianBlur(4))
mpa = np.asarray(mp).astype(np.float32)[..., None] / 255
mpa = mpa * (~objs)[..., None]
light += mpa * np.array(WIN)
if WEATHER == "storm": light += np.array([0.04, 0.05, 0.10])
sh = np.asarray(shadow).astype(np.float32)[..., None] / 255
light *= (1 - sh * 0.8)
# vignette
vig = 1 - (0.35 if NIGHT or WEATHER == 'storm' else 0.22) * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
light *= np.clip(vig, 0.55, 1)[..., None]
out = np.clip(base * light * 1.25, 0, 1)
em = np.asarray(emis)[..., None] > 0
out = np.where(em, base, out)
# quantize lightly to keep the pixel-art feel
out = (np.round(out * 255 / 8) * 8).clip(0, 255).astype(np.uint8)
final = Image.fromarray(out)
OUT = "out5_wide" if WIDE else "out5"
os.makedirs(OUT, exist_ok=True)
final.save(f"{OUT}/room_{TIME}_{WEATHER}.png")
# how much the lighting darkens/tints things in the top-right corner and on the shelf
def ratio(x, y, base):
    c = final.getpixel((x, y)); return [round(c[k] / base[k], 3) for k in range(3)]
EXPORT["plantTint"] = ratio(246, 26, POT_D)
EXPORT["shelfTint"] = ratio(200, 54, WOOD)
# average lighting on the right-hand foreground, where the trainer stands
_reg = np.clip(light[60:160, 200:256] * 1.25, 0, 1).reshape(-1, 3).mean(0)
EXPORT["trainerTint"] = [round(float(v), 3) for v in _reg]
# average lighting where the pal walks and sits (floor, window seat, bed)
_pal = np.clip(light[75:150, 50:215] * 1.25, 0, 1).reshape(-1, 3).mean(0)
EXPORT["palTint"] = [round(float(v), 3) for v in _pal]
_json.dump(EXPORT, open(f"{OUT}/room_{TIME}_{WEATHER}.json", "w"))
print("ok")
# glass mask: window pixels where the sky is actually visible (not frame, curtains, lights)
if TIME == "day" and WEATHER == "clear":
    skyq = np.asarray(sky).astype(int) // 8 * 8
    fin = np.asarray(final).astype(int)
    wm_ = np.asarray(wmask) > 0
    same = (np.abs(fin - np.round(np.asarray(sky).astype(float) / 8) * 8).max(axis=2) <= 8) & wm_
    Image.fromarray((same * 255).astype(np.uint8)).save(f"{OUT}/glass_mask.png")
    CHAIR_MASK.save(f"{OUT}/chair_mask.png")
    # everything decorations must tuck behind: the desk chair and the floor plant in the front corner
    _fg = (np.asarray(_snap_fgplant).astype(int) != np.asarray(_snap_prefg).astype(int)).any(axis=2)
    Image.fromarray(((np.asarray(CHAIR_MASK) > 0) | _fg).astype(np.uint8) * 255).save(f"{OUT}/front_mask.png")
