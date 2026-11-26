"""Animated room details (Python copy of Pal/PalRoomAmbience.swift), used to pre-draw the widget's
once-a-second effect fonts. Pure functions of time t (seconds).
Everything is drawn at room scale (256x160), one room pixel per pixel."""
from PIL import Image, ImageDraw
import math

# Every motion repeats exactly every LOOP seconds, so the widget's 60-frame effect loop has no seam.
LOOP = 60.0
def qf(w):            # angular speed (rad/s) -> nearest one that fits a whole number of turns in LOOP
    return 2 * math.pi * max(1, round(w * LOOP / (2 * math.pi))) / LOOP
def qs(speed, span):  # px/s over a wrap of `span` px -> nearest whole number of wraps in LOOP
    return span * max(1, round(speed * LOOP / span)) / LOOP
def qp(period):       # period (s) -> nearest one that divides LOOP
    return LOOP / max(1, round(LOOP / period))
def fade(p, a=0.15, b=0.15):   # 0 at both ends of a 0..1 cycle, 1 in the middle (no pop when it wraps)
    return min(1.0, p / a) * min(1.0, (1 - p) / b)

def rnd(i, salt=0.0):
    v = math.sin(i * 12.9898 + salt * 78.233) * 43758.5453
    return v - math.floor(v)

WX0, WX1, WY0, WY1 = 62, 108, 26, 74
LW, CT = 44, 14

def window_mask():
    m = Image.new("L", (256, 160), 0); d = ImageDraw.Draw(m)
    d.rectangle([WX0, WY0, WX1, 65], fill=255)  # stop above the pillows on the window seat; d.ellipse([WX0, WY0 - 11, WX1, WY0 + 9], fill=255)
    return m
import os as _os
WMASK = Image.open(_os.path.join(_os.path.dirname(__file__), 'glass_mask.png')).convert('L')

def bulbs():
    out = []
    for x in range(LW, 256, 10):
        out.append((x, CT + 3 + int(5 * abs(math.sin((x - LW) / 42 * math.pi))) + 1))
    for x in range(4, LW, 10):
        out.append((x, int(CT * x / LW) + 3 + int(3 * abs(math.sin(x / 22 * math.pi))) + 1))
    return out
BULBS = bulbs()
BULB_COLORS = [(255, 200, 120), (255, 170, 140), (255, 226, 150)]

def lights_on(time, weather): return time in ("night", "sunset") or (weather in ("storm", "rain") and time != "day")
def music_on(time, weather): return time != "night"

def blend(img, x, y, c, a):
    if 0 <= x < 256 and 0 <= y < 160 and a > 0:
        b = img.getpixel((x, y))
        img.putpixel((x, y), tuple(int(b[k] + (c[k] - b[k]) * min(a, 1)) for k in range(3)) + (255,))

def note_px(x, y):
    return [(x, y), (x, y + 1), (x, y + 2), (x, y + 3), (x - 1, y + 3), (x - 2, y + 3), (x + 1, y), (x + 2, y + 1)]

def draw(img, t, time, weather):
    """img: RGBA room image (256x160). Returns a new image with the effects."""
    img = img.copy()
    # ---- inside the window (clipped) ----
    win = Image.new("RGBA", (256, 160), (0, 0, 0, 0))
    if weather in ("rain", "storm"):
        n, speed, slant = (60, 110, 1) if weather == "storm" else (40, 80, 0)
        for i in range(n):
            x = WX0 + int(rnd(i, 1) * 47); y = WY0 - 12 + int((t * qs(speed * (0.8 + 0.4 * rnd(i, 2)), 62) + rnd(i, 3) * 60) % 62)
            for k in range(3):
                blend(win, x - (slant * k) // 2, y + k, (190, 205, 235), 0.75)
    if weather == "snow":
        for i in range(36):
            sp = 7 + 7 * rnd(i, 4)
            y = WY0 - 12 + int((t * qs(sp, 62) + rnd(i, 5) * 62) % 62)
            x = WX0 + int(rnd(i, 6) * 47 + math.sin(t * qf(1.3) + i) * 2)
            blend(win, x, y, (255, 255, 255), 0.95)
    if time == "night" and weather == "clear":
        for i in range(10):
            x = WX0 + 3 + int(rnd(i, 7) * 41); y = WY0 - 6 + int(rnd(i, 8) * 26)
            a = 0.5 + 0.5 * math.sin(t * qf(1.5 + rnd(i, 9) * 2) + i * 2)
            blend(win, x, y, (255, 255, 230), a)
    flash = 0.0
    if weather == "storm":
        ph = t % 10.0
        if ph < 0.12 or 0.25 < ph < 0.33: flash = 1.0
    if flash:
        wd = ImageDraw.Draw(win)
        wd.rectangle([0, 0, 255, 159], fill=(245, 245, 255, 200))
        wd.rectangle([85, 0, 86, 159], fill=(0, 0, 0, 0)); wd.rectangle([0, 48, 255, 49], fill=(0, 0, 0, 0))  # keep the window frame
    if any(win.getchannel("A").getdata()):
        a = win.getchannel("A"); a = Image.composite(a, Image.new("L", a.size, 0), WMASK)
        win.putalpha(a); img.alpha_composite(win)

    # ---- dust motes in the sunbeam ----
    if weather == "clear" and time != "night":
        for i in range(14):
            bx = 66 + rnd(i, 10) * 56; by = 60 + rnd(i, 11) * 80
            rise = (t * qs(2.5, 30) + rnd(i, 12) * 30) % 30
            y = by - rise
            x = bx + math.sin(t * qf(0.4) + i) * 3
            a = (0.25 + 0.35 * (0.5 + 0.5 * math.sin(t * qf(2) + i))) * fade(rise / 30)
            blend(img, int(x), int(y), (255, 245, 210), a)

    # ---- string lights twinkle ----
    if lights_on(time, weather):
        for i, (x, y) in enumerate(BULBS):
            a = 0.5 + 0.5 * math.sin(t * 1.885 + i * 1.7)
            c = BULB_COLORS[i % 3]
            for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 2), (-1, 1), (1, 1)]:
                blend(img, x + dx, y + dy + 0, c, 0.35 * a)
            blend(img, x, y, (255, 250, 230), 0.6 * a); blend(img, x, y + 1, (255, 250, 230), 0.6 * a)

    # ---- candle flicker (night) ----
    if time == "night":
        f = 0.5 + 0.25 * math.sin(t * qf(13)) + 0.25 * math.sin(t * qf(7.3) + 1)
        for dx in range(-7, 8):
            for dy in range(-7, 8):
                r = math.hypot(dx, dy)
                if r < 7: blend(img, 156 + dx, 70 + dy, (255, 190, 110), 0.10 * f * (1 - r / 7))
        blend(img, 156, 71, (255, 180, 80), 1); blend(img, 156, 70, (255, 235, 170), 1)
        if f > 0.55: blend(img, 156 + (1 if math.sin(t * qf(5)) > 0.6 else 0), 69, (255, 220, 140), 0.9)

    # ---- record player + floating notes ----
    if music_on(time, weather):
        ang = t * 2 * math.pi * 0.75
        blend(img, int(round(129 + 5 * math.cos(ang))), int(round(72 + 1.4 * math.sin(ang))), (120, 110, 130), 1)
        cols = [(140, 220, 210), (250, 210, 120), (240, 150, 170)]
        for i in range(4):
            p = (t / qp(3.2) + i / 4) % 1
            side = -1 if i % 2 else 1
            x = int(round(128 + side * p * 9 + math.sin(p * 9 + i) * 1.5)); y = int(round(66 - p * 26))
            a = min(1, p / 0.12) * min(1, (1 - p) / 0.35)
            for (px, py) in note_px(x, y): blend(img, px, py, cols[i % 3], a)

    # ---- mug steam (not at night) ----
    if time != "night":
        for i in range(3):
            p = (t / qp(2.4) + i / 3) % 1
            x = int(round(100 + math.sin(p * 7 + i * 2) * 1.5)); y = int(round(71 - p * 10))
            blend(img, x, y, (240, 240, 250), 0.55 * (1 - p))

    # ---- storm flash lights the room a little ----
    if flash:
        ov = Image.new("RGBA", (256, 160), (220, 225, 255, 40)); img.alpha_composite(ov)
    return img

# ======== round 2: clouds, swaying plant, fish tank, clock ========
GREEN = (84, 156, 92); GREEN_D = (56, 116, 70)
FISH = [(250, 140, 60), (250, 210, 90), (110, 170, 240)]
DIGITS = {  # 3x5 pixel font
    "0": ["111", "101", "101", "101", "111"], "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"], "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"], "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"], "7": ["111", "001", "010", "010", "010"],
    "8": ["111", "101", "111", "101", "111"], "9": ["111", "101", "111", "001", "111"]}

def cloud_pixels(i):
    """Pixel cloud built from 4 overlapping ellipses: returns {(dx,dy): 'body'|'shadow'}."""
    out = {}
    for k in range(4):
        r = 4 + int(rnd(i, 20 + k) * 4); ry = r / 1.4; ox = k * 5 - 8
        for dy in range(-7, 8):
            for dx in range(-16, 16):
                if ((dx - ox) / r) ** 2 + (dy / ry) ** 2 <= 1:
                    inner = ((dx - ox) / (r - 1)) ** 2 + ((dy + 1.5) / (ry - 0.5)) ** 2 <= 1
                    if inner: out[(dx, dy)] = "body"
                    elif out.get((dx, dy)) != "body": out[(dx, dy)] = "shadow"
    return out
CLOUDS = [cloud_pixels(i) for i in range(12)]

def tint(c, k): return tuple(min(255, int(c[j] * k[j])) for j in range(3))

def draw2(img, t, time, weather, info, clock=(9, 41)):
    img = img.copy()
    # clouds drifting across the window (behind the trees, which sit lower)
    win = Image.new("RGBA", (256, 160), (0, 0, 0, 0))
    body, shadow = tuple(info["cloud"]), tuple(info["cloudShadow"])
    ymax = 34 if weather == "clear" else 44
    for i in range(info["clouds"]):
        cy = 18 + int(rnd(i, 21) * (ymax - 18))
        sp = (1.2 + rnd(i, 22) * 1.8) * (2.2 if weather == "storm" else 1)
        cx = 42 + int((rnd(i, 23) * 87 + t * qs(sp, 87)) % 87)
        for (dx, dy), kind in CLOUDS[i].items():
            blend(win, cx + dx, cy + dy, body if kind == "body" else shadow, 1)
    a = Image.composite(win.getchannel("A"), Image.new("L", (256, 160), 0), WMASK); win.putalpha(a)
    # keep the trees in front: only paint clouds over pixels above the tree line
    trees = Image.new("L", (256, 160), 255); td = ImageDraw.Draw(trees)
    for x in range(256):
        th = int(60 + 5 * math.sin(x / 3) + 3 * math.sin(x / 1.3)); td.line([(x, th), (x, 159)], fill=0)
    win.putalpha(Image.composite(win.getchannel("A"), Image.new("L", (256, 160), 0), trees))
    img.alpha_composite(win)
    # then everything from round 1 (rain, lights, notes...) on top
    img = draw(img, t, time, weather)
    # swaying hanging plant
    pk = info["plantTint"]
    for i in range(18):
        x0 = 238 + int(rnd(i, 30) * 17); L = 6 + int(rnd(i, 31) * 21)
        for y in range(24, 24 + L):
            sway = round(math.sin(t * qf(1.1) + i * 0.5) * 1.6 * (y - 24) / 26)
            blend(img, x0 + (y // 4) % 2 + sway, y, tint(GREEN if (y + i) % 2 else GREEN_D, pk), 1)
    # fish tank
    sk = info["shelfTint"]
    for i in range(3):
        sp = 3 + rnd(i, 40) * 3; span = 15
        p = (t * qs(sp, 2 * span) / span + rnd(i, 41) * 2) % 2           # 0..2: there and back
        right = p < 1
        x = 193 + int((p if right else 2 - p) * span); y = 45 + int(rnd(i, 42) * 5) + round(math.sin(t * qf(2) + i))
        c = tint(FISH[i], sk)
        for dx in range(3): blend(img, x + dx, y, c, 1)
        blend(img, x + (2 if right else 0), y - 1, c, 1)                        # fin
        blend(img, x + (-1 if right else 3), y, tint((255, 255, 255), sk), 0.0)
        blend(img, x + (-1 if right else 3), y + (1 if int(t * 4) % 2 else -1), c, 1)  # tail wiggle
        blend(img, x + (2 if right else 0), y, (30, 30, 40), 1)                  # eye
    for i in range(3):
        p = (t / qp(2.2) + i / 3) % 1
        blend(img, 206 + (1 if math.sin(p * 12) > 0 else 0), int(50 - p * 7), (220, 240, 250), 0.8 * fade(p, 0.1, 0.25))
    # digital clock with blinking colon (real time in the app; fixed here)
    if clock is None: return img
    hh, mm = clock
    txt = f"{hh:2d}{mm:02d}"
    xs = [217, 221, 227, 231]
    for ch, x in zip(txt, xs):
        if ch == " ": continue
        for r, row in enumerate(DIGITS[ch]):
            for cidx, bit in enumerate(row):
                if bit == "1": blend(img, x + cidx - 1 if x == 217 else x + cidx - 1, 47 + r, (120, 240, 160), 1)
    if int(t * 2) % 2 == 0:
        blend(img, 224, 48, (120, 240, 160), 1); blend(img, 224, 50, (120, 240, 160), 1)
    return img
