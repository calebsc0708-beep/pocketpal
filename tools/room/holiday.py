"""Holiday decorations drawn INTO the room (before lighting), in the room's perspective and style.

room.py calls draw(layer, g) at three points in its drawing order:
  "wall"  - after the back wall, window, shelves and string lights (garlands, wreaths, bats, banners...)
  "desk"  - after the window seat and desk, before the desk chair (things sitting on them)
  "floor" - after the rug, before the front plant (things standing on the floor / rug)
`g` is room.py's globals (its drawing helpers and state). Glowing bits light up in the evening.
"""
import math
import numpy as np

HOLIDAYS = ("halloween", "autumn", "christmas", "newyear", "valentine")


def draw(layer, g):
    h = g.get("HOLIDAY")
    if h not in HOLIDAYS:
        return
    D = Draw(g)
    getattr(D, f"{h}_{layer}")()


class Draw:
    def __init__(self, g):
        self.g = g
        self.img, self.d = g["img"], g["d"]
        self.P, self.R, self.E, self.px = g["P"], g["R"], g["E"], g["px"]
        self.Pd, self.Rd, self.Ed, self.Ld = g["Pd"], g["Rd"], g["Ed"], g["Ld"]
        self.wp, self.pj, self.q = g["wp"], g["pj"], g["_q"]
        self.glow = g["LAMP_ON"]                         # evening: candles, tree lights and carved faces glow
        self.wide = g["WIDE"]
        self.W = g["W"]
        self.wx0, self.wx1, self.wy0, self.wy1 = g["wx0"], g["wx1"], g["wy0"], g["wy1"]
        self.FL = g["FL"]
        self.shadows = g.setdefault("DECO_SHADOWS", [])  # contact shadows, added in the room's shadow pass

    # ------------------------------------------------------------ helpers
    @staticmethod
    def sh(c, k):
        return tuple(max(0, min(255, int(v * k))) for v in c)

    def floor_y(self, d):
        """Screen y of the floor at depth d (m out from the back wall)."""
        return self.wp(0, self.FL, d)[1]

    def depth_at(self, y):
        """Depth (m from the back wall) of the floor seen at screen y."""
        Z = 400 * 1.6 / (y - 40)
        return 10 - Z

    def scale_at(self, y):
        """Room px per 'wall px' for things standing on the floor at screen y (bigger nearer)."""
        return self.g["K"](self.depth_at(y))

    def ball(self, cx, cy, rx, ry, col, light=(-0.6, -0.7), e=False, spec=True):
        """A shaded round thing (pumpkin, ornament, apple): lit from the upper left like the room."""
        for y in range(int(cy - ry) - 1, int(cy + ry) + 2):
            for x in range(int(cx - rx) - 1, int(cx + rx) + 2):
                u, v = (x + 0.5 - cx) / rx, (y + 0.5 - cy) / ry
                r2 = u * u + v * v
                if r2 > 1:
                    continue
                nz = math.sqrt(1 - r2)
                k = 0.72 + 0.42 * (-(u * light[0] + v * light[1]) * 0.6 + nz * 0.55)
                c = self.sh(col, k)
                if spec and -0.75 < u < -0.2 and -0.8 < v < -0.3 and r2 < 0.45:
                    c = self.sh(col, 1.28)
                self.px(x, y, c, e)

    def contact(self, cx, y, rx, ry=1.5):
        self.shadows.append(("ellipse", [cx - rx, y - ry, cx + rx, y + ry], 95))

    def pumpkin(self, cx, base, w, h, face=False, col=(232, 124, 44)):
        rx, ry = w / 2, h / 2
        cy = base - ry
        self.ball(cx, cy, rx, ry, col)
        for k in (-0.45, 0.0, 0.45):                         # ribs, curving with the body
            x = round(cx + k * rx)
            for y in range(round(cy - ry * 0.75), round(cy + ry * 0.8)):
                if abs(k) > 0:
                    self.px(x, y, self.sh(col, 0.78))
        self.R(round(cx) - 1, round(base - h) - 2, round(cx), round(base - h), (96, 120, 60))   # stem
        self.px(round(cx) + 1, round(base - h) - 2, (110, 140, 70))
        if face:
            Y = (255, 214, 90) if self.glow else (90, 50, 30)
            ix, iy = round(cx), round(cy)
            if w >= 11:   # big jack-o'-lantern: triangle eyes, nose, toothy grin
                face_px = [(-3, -2), (-2, -2), (-1, -2), (-2, -1),  (1, -2), (2, -2), (3, -2), (2, -1),  (0, 0),
                           (-3, 1), (-2, 2), (-1, 2), (0, 1), (1, 2), (2, 2), (3, 1)]
            else:         # little one: two eyes and a smile
                face_px = [(-2, -1), (-1, -1), (1, -1), (2, -1), (-2, 1), (-1, 2), (0, 2), (1, 2), (2, 1)]
            for (fx, fy) in face_px:
                self.px(ix + fx, iy + fy, Y, self.glow)
            if self.glow:   # it lights up what's around it a little
                self.g.setdefault("DECO_LIGHTS", []).append((cx, cy, 14 + w, (1.0, 0.62, 0.25), 0.45))
        self.contact(cx, base, rx * 1.05)

    def garland(self, x0, x1, ytop, sag, dd, color, every=0, stamp=None):
        """A string sagging between two points on a plane at depth dd; returns the points along it."""
        pts = []
        for x in range(x0, x1 + 1):
            t = (x - x0) / max(1, x1 - x0)
            pts.append((x, ytop + sag * math.sin(t * math.pi)))
        scr = [self.wp(x, y, dd) for x, y in pts]
        for i, (x, y) in enumerate(scr):
            self.px(round(x), round(y), color)
            self.px(round(x), round(y) + 1, self.sh(color, 0.8))
        return scr

    def stamp(self, rows, x, y, cols, e=False):
        for r, row in enumerate(rows):
            for c, ch in enumerate(row):
                if ch in cols:
                    self.px(round(x) + c, round(y) + r, cols[ch], e)

    def box(self, X0, X1, Z0, Z1, Y1, col, ribbon=None):
        """A box on the floor in world coords (m), with visible top, front and side shaded like the room."""
        pj, q = self.pj, self.q
        top, front, side = self.sh(col, 1.12), col, self.sh(col, 0.76)
        if X0 > 0:
            self.P(q([pj(X0, 0, Z0), pj(X0, 0, Z1), pj(X0, Y1, Z1), pj(X0, Y1, Z0)]), side)
        if X1 < 0:
            self.P(q([pj(X1, 0, Z0), pj(X1, 0, Z1), pj(X1, Y1, Z1), pj(X1, Y1, Z0)]), side)
        self.P(q([pj(X0, Y1, Z1), pj(X1, Y1, Z1), pj(X1, Y1, Z0), pj(X0, Y1, Z0)]), top)
        self.P(q([pj(X0, 0, Z0), pj(X1, 0, Z0), pj(X1, Y1, Z0), pj(X0, Y1, Z0)]), front)
        if ribbon:
            xm = (X0 + X1) / 2; zm = (Z0 + Z1) / 2
            self.d.line(q([pj(xm, 0, Z0), pj(xm, Y1, Z0), pj(xm, Y1, Z1)]), fill=ribbon)
            self.d.line(q([pj(X0, Y1, zm), pj(X1, Y1, zm)]), fill=self.sh(ribbon, 1.05))
            bx, by = pj(xm, Y1, zm)
            self.stamp(["#.#", ".#."], bx - 1, by - 2, {"#": ribbon})
        a, b = pj(X0, 0, Z0), pj(X1, 0, Z0)
        self.shadows.append(("polygon", q([a, b, (b[0] + 2, b[1] + 2), (a[0] - 1, a[1] + 2)]), 90))

    def world_x(self, sx, y):
        """World X of screen x on the floor at screen y."""
        Z = 400 * 1.6 / (y - 40)
        return (sx - 150) * Z / 400, Z

    def hang_sprite(self, name, div, cx, bottom):
        self.g["place"](name, div, cx, bottom)

    # ------------------------------------------------------------ shared pieces
    def rod_garland(self, col, leaves=None, bows=None, lights=False):
        """Garland draped along the curtain rod (it's 0.15 m out from the wall)."""
        pts = self.garland(self.wx0 - 6, self.wx1 + 6, self.wy0 - 14, 5, 0.15, col)
        for i, (x, y) in enumerate(pts[::5]):
            if leaves:
                self.stamp([".#.", "###", ".#."], x - 1, y + 1, {"#": leaves[i % len(leaves)]})
        if bows:
            for (x, y) in pts[3::14]:
                self.stamp(["#.#", ".#.", "#.#"], x - 1, y + 1, {"#": bows})
        if lights:
            for i, (x, y) in enumerate(pts[6::9]):
                self.px(round(x), round(y) + 2, [(255, 120, 120), (255, 230, 120), (140, 200, 255)][i % 3], self.glow)
        return pts

    def shelf_garland(self, col, leaves=None, bows=None, lights=False):
        """Garland hanging from the front edge of the shelf above the desk (0.28 m out)."""
        pts = self.garland(118, 170, 52, 2, 0.28, col)
        for i, (x, y) in enumerate(pts[::5]):
            if leaves:
                self.stamp([".#.", "###", ".#."], x - 1, y + 1, {"#": leaves[i % len(leaves)]})
        if bows:
            for (x, y) in pts[4::13]:
                self.stamp(["#.#", ".#.", "#.#"], x - 1, y + 1, {"#": bows})
        if lights:
            for i, (x, y) in enumerate(pts[2::7]):
                self.px(round(x), round(y) + 2, [(255, 120, 120), (255, 230, 120), (140, 200, 255)][i % 3], self.glow)
        return pts

    def wreath(self, cx, cy, ring, accent, bow):
        """Round wreath on the back wall: lit along its top, shaded along its bottom."""
        for y in range(cy - 11, cy + 12):
            for x in range(cx - 11, cx + 12):
                r = math.hypot(x - cx, y - cy)
                if 5.5 <= r <= 10.5:
                    k = 1.15 - 0.35 * ((y - cy) / 10.5 + 1) / 2 - 0.12 * ((r - 5.5) / 5 - 0.5) ** 2 * 4
                    c = self.sh(ring, k)
                    if (x * 7 + y * 3) % 11 == 0:
                        c = self.sh(ring, 1.3)
                    self.px(x, y, c)
        for a in range(0, 360, 45):
            self.px(cx + round(8 * math.cos(math.radians(a))), cy + round(8 * math.sin(math.radians(a))), accent)
        self.stamp(["#.#", ".#.", "#.#"], cx - 1, cy + 8, {"#": bow})
        self.g["DECO_WALLSHADOWS"] = self.g.get("DECO_WALLSHADOWS", []) + [("ring", (cx + 1, cy + 2), 0)]

    def tree(self, cx, base):
        G = (52, 120, 76)
        s = self.scale_at(base)
        self.R(round(cx - 2 * s), round(base - 4 * s), round(cx + 1 * s), round(base), (110, 72, 48))   # trunk
        for (top, half) in [(base - 12 * s, 12 * s), (base - 20 * s, 10 * s), (base - 28 * s, 7 * s)]:
            # each tier: lit left side, shaded right side, darker underside edge
            apex = (cx, top - 9 * s)
            left, right = (cx - half, top + 6 * s), (cx + half, top + 6 * s)
            self.P(self.q([apex, (cx, top + 6 * s), left]), self.sh(G, 1.12))
            self.P(self.q([apex, right, (cx, top + 6 * s)]), self.sh(G, 0.86))
            self.d.line(self.q([left, right]), fill=self.sh(G, 0.7))
        rng = np.random.default_rng(3)
        cols = [(220, 60, 70), (250, 200, 80), (90, 150, 230)]
        for i in range(12):                                   # ornaments (round, shaded)
            t = rng.random(); yy = base - (6 + t * 26) * s; half = (12 - t * 7) * s * 0.8
            xx = cx + (rng.random() * 2 - 1) * half * (1 - (t * 0.3))
            self.ball(xx, yy, 1.2, 1.2, cols[i % 3], spec=False)
        for i in range(10):                                   # little lights: glow in the evening
            t = rng.random(); yy = base - (6 + t * 26) * s; half = (12 - t * 7) * s * 0.75
            xx = cx + (rng.random() * 2 - 1) * half
            self.px(round(xx), round(yy), [(255, 140, 140), (255, 236, 150), (150, 210, 255)][i % 3], self.glow)
        if self.glow:
            self.g.setdefault("DECO_LIGHTS", []).append((cx, base - 18 * s, 34, (1.0, 0.85, 0.6), 0.35))
        sy = base - 37 * s                                    # star
        for p in [(0, -1), (-1, 0), (0, 0), (1, 0), (0, 1), (-2, 0), (2, 0)]:
            self.px(round(cx + p[0]), round(sy + p[1]), (250, 220, 90), self.glow)
        self.contact(cx, base, 9 * s, 2)

    # ------------------------------------------------------------ Halloween
    def halloween_wall(self):
        BAT = (50, 40, 56)
        rod = self.rod_garland((60, 50, 60))
        for i, (x, y) in enumerate(rod[4::9]):              # bats hanging from the rod
            yb = y + 2 + (i % 2) * 2
            self.d.line([(round(x), round(y) + 1), (round(x), round(yb))], fill=(70, 60, 70))
            self.P(self.q([(x - 3, yb + 1), (x, yb), (x + 3, yb + 1), (x + 1, yb + 2), (x - 1, yb + 2)]), BAT)
        for (x, y) in [(160, 30), (176, 22), (232, 40)]:     # bats flying across the wall
            self.stamp(["#.....#", "##.#.##", ".#####.", "..#.#.."], x, y, {"#": BAT})
        pts = self.garland(176, 236, 18, 6, 0.0, (60, 50, 60))   # pennant banner above the bed
        for i, (x, y) in enumerate(pts[::8]):
            col = [(240, 130, 40), (140, 80, 190), (40, 34, 44)][i % 3]
            self.P(self.q([(x - 3, y + 1), (x + 3, y + 1), (x, y + 7)]), col)
            self.d.line(self.q([(x - 3, y + 1), (x, y + 7)]), fill=self.sh(col, 1.15))
        # cobweb in the corner where the left wall meets the back wall and ceiling
        for k in range(0, 14):
            self.px(44 + k, 14 + k // 2, (220, 220, 230)); self.px(44 + k // 2, 14 + k, (220, 220, 230))
        for r in (5, 9, 13):
            for a in range(0, 91, 10):
                self.px(44 + int(r * math.cos(math.radians(a))), 14 + int(r * math.sin(math.radians(a))), (196, 196, 210))
        # ghost hanging under the front edge of the desk shelf (0.25 m out from the wall)
        gx, gy = 130, 53
        self.Ld([(gx, 52), (gx, gy)], 0.25, (200, 200, 210))
        ghost = [".###.", "#####", "#.#.#", "#####", "#####", "#.#.#"]
        for r, row in enumerate(ghost):
            for c, ch in enumerate(row):
                if ch == "#":
                    x, y = self.wp(gx - 2 + c, gy + r, 0.25)
                    self.px(round(x), round(y), self.sh((245, 245, 250), 1.0 - 0.06 * r - (0.08 if c > 2 else 0)))

    def seat(self):
        # the window-seat spot: beside the blanket, or in the wide room (where the pal's bed sits there)
        # at the left end, in front of the orange pillow
        return (61, 78) if self.wide else (73, 76)

    def halloween_desk(self):
        self.pumpkin(*self.seat(), 7, 6, True)                      # on the window seat, between the pillow and blanket
        x, y = self.wp(146, 78, 0.35)                         # on the desk, behind the chair's back
        self.pumpkin(x, y, 8, 6, True)

    def halloween_floor(self):
        if self.wide:                                         # witch hat perched on the floor lamp's shade
            lx, ly = self.g["LMX"], self.g["LMY"]
            self.hang_sprite("witch_hat", 2, lx + 1, ly - 9)
        self.pumpkin(50, 123, 14, 10, True)
        self.pumpkin(64, 125, 9, 7, False, (220, 112, 40))
        # candy bowl on the rug: a purple bowl seen from above, sweets heaped inside
        cx, base = 110, 141
        self.E([cx - 8, base - 6, cx + 8, base], (120, 66, 166))
        self.E([cx - 7, base - 7, cx + 7, base - 3], (150, 90, 200))
        self.E([cx - 6, base - 6, cx + 6, base - 4], (90, 50, 130))
        for (dx, dy, c) in [(-4, -7, (250, 200, 60)), (-1, -8, (240, 90, 90)), (2, -7, (120, 220, 120)), (4, -6, (250, 160, 60)), (0, -6, (240, 240, 250))]:
            self.R(cx + dx, base + dy, cx + dx + 1, base + dy, c)
        self.contact(cx, base, 8)

    # ------------------------------------------------------------ autumn (November)
    LEAFC = [(220, 90, 40), (240, 160, 50), (190, 60, 40), (230, 190, 70)]

    def autumn_wall(self):
        self.rod_garland((110, 80, 50), leaves=self.LEAFC)
        self.shelf_garland((110, 80, 50), leaves=self.LEAFC)
        cx, cy = 214, 32                                      # leaf wreath above the bed
        for a in range(0, 360, 24):
            x, y = cx + 9 * math.cos(math.radians(a)), cy + 9 * math.sin(math.radians(a))
            c = self.LEAFC[(a // 24) % 4]
            self.stamp([".#.", "###", ".#."], x - 1, y - 1, {"#": self.sh(c, 1.08 if y < cy else 0.88)})
        self.stamp(["#.#", ".#.", "#.#"], cx - 1, cy + 8, {"#": (190, 60, 40)})

    def autumn_desk(self):
        self.pumpkin(*self.seat(), 7, 5, False)
        x, y = self.wp(146, 78, 0.35)                         # pie on the desk
        x, y = round(x), round(y)
        self.E([x - 6, y - 3, x + 6, y + 1], (200, 150, 90)); self.E([x - 5, y - 4, x + 5, y - 1], (226, 176, 104))
        for k in range(x - 4, x + 5, 2):
            self.px(k, y - 3, (170, 110, 60))

    def autumn_floor(self):
        self.pumpkin(50, 123, 12, 9, False)
        self.ball(63, 120, 5, 4, (230, 190, 70)); self.d.line([(63, 116), (63, 114)], fill=(110, 140, 70)); self.contact(63, 124, 5)
        # apple crate on the rug: a wooden box in perspective with apples on top
        X0, Z0 = self.world_x(100, 138)
        self.box(X0, X0 + 0.32, Z0 - 0.22, Z0, 0.16, (170, 120, 70))
        tx, ty = self.pj(X0 + 0.16, 0.16, Z0 - 0.11)
        for (dx, c) in [(-5, (210, 50, 50)), (-1, (230, 70, 60)), (3, (200, 40, 40)), (6, (230, 190, 70))]:
            self.ball(tx + dx, ty - 1, 2.2, 2, c, spec=False)
        rng = np.random.default_rng(11)                       # fallen leaves on the floor
        for i in range(18):
            x, y = int(60 + rng.random() * 100), int(114 + rng.random() * 30)
            if 92 < x < 122 and y > 126:
                continue
            self.stamp([".#.", "###", ".#."], x, y, {"#": self.LEAFC[i % 4]})

    # ------------------------------------------------------------ Christmas
    def christmas_wall(self):
        G1 = (52, 120, 76)
        self.rod_garland(G1, leaves=[self.sh(G1, 0.85)], bows=(210, 60, 70), lights=True)
        self.shelf_garland(G1, leaves=[self.sh(G1, 0.85)], bows=(210, 60, 70), lights=True)
        self.wreath(214, 32, G1, (220, 60, 70), (210, 60, 70))
        self.d.line([(150, 2), (150, 13)], fill=(150, 120, 90))   # mistletoe from the ceiling beam
        for p in [(150, 14), (151, 15), (149, 15)]:
            self.px(*p, G1)
        self.px(150, 16, (245, 245, 245))
        glass = self.g["_glass_now"]
        for (x, y) in [(68, 30), (97, 34), (79, 55), (102, 58), (66, 50)]:   # snowflake stickers on the glass
            if glass[y, x]:
                self.stamp(["#.#.#", ".###.", "##.##", ".###.", "#.#.#"], x, y, {"#": (240, 246, 255)})
        if self.wide:                                         # santa hat on the bedpost
            self.hang_sprite("santa_hat", 2, 263, 59)

    def christmas_desk(self):
        for x in (66, 100):                                   # stockings hanging on the window seat's front
            sd = self.g["SEAT_D"]
            self.Rd(x, 82, x + 4, 89, sd, (210, 70, 80)); self.Rd(x, 89, x + 7, 92, sd, (210, 70, 80))
            self.Rd(x + 3, 83, x + 4, 91, sd, (176, 52, 64)); self.Rd(x, 81, x + 4, 82, sd, (245, 245, 250))
        x, y = self.wp(156, 77, 0.25)                         # candy cane on the desk
        x, y = round(x), round(y)
        for k in range(8):
            self.px(x, y - k, (220, 60, 70) if k % 3 == 0 else (245, 245, 245))
        self.px(x + 1, y - 8, (220, 60, 70)); self.px(x + 2, y - 7, (245, 245, 245))

    def christmas_floor(self):
        self.tree(40, 112)
        for (sx, base, w, d_, hgt, c, r) in [(47, 116, 0.22, 0.18, 0.16, (210, 70, 80), (250, 220, 120)),
                                              (28, 117, 0.18, 0.14, 0.12, (90, 140, 210), (240, 240, 250)),
                                              (58, 119, 0.18, 0.15, 0.10, (90, 170, 110), (250, 220, 120))]:
            X0, Z0 = self.world_x(sx, base)
            self.box(X0, X0 + w, Z0 - d_, Z0, hgt, c, ribbon=r)

    # ------------------------------------------------------------ New Year
    GOLD, SILVER = (240, 200, 80), (210, 214, 230)

    def newyear_wall(self):
        for col, sag, dy in ((self.GOLD, 6, 0), (self.SILVER, 5, 3)):
            pts = self.garland(self.wx0 - 4, self.wx1 + 4, self.wy0 - 15 + dy, sag, 0.15, col)
            for (x, y) in pts[::3]:
                self.px(round(x), round(y) + 2, self.sh(col, 1.1))
        pts = self.garland(176, 236, 18, 6, 0.0, self.GOLD)
        for (x, y) in pts[::3]:
            self.px(round(x), round(y) + 2, self.GOLD)
        glass = self.g["_glass_now"]
        for (x, y) in [(70, 20), (90, 28), (102, 18), (80, 40)]:     # fireworks sparkles in the window
            if glass[y, x]:
                for p in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                    self.px(x + p[0], y + p[1], (255, 240, 180), True)

    def party_hat(self, x, base):
        x = round(x); base = round(base)
        self.P([(x, base - 8), (x - 3, base), (x + 3, base)], (120, 110, 220))
        self.P([(x, base - 8), (x + 3, base), (x + 1, base)], (96, 86, 190))
        self.d.line([(x - 2, base - 3), (x + 2, base - 3)], fill=self.GOLD)
        self.px(x, base - 9, self.GOLD)

    def newyear_desk(self):
        self.party_hat(*self.seat())                                # on the window seat
        x, y = self.wp(146, 78, 0.3); self.party_hat(x, y)    # on the desk

    def newyear_floor(self):
        rng = np.random.default_rng(7)
        cols = [self.GOLD, self.SILVER, (230, 80, 120), (110, 200, 230), (150, 120, 230)]
        for i in range(80):
            x, y = int(50 + rng.random() * 120), int(110 + rng.random() * 40)
            self.px(x, y, cols[i % 5])

    # ------------------------------------------------------------ Valentine's
    HEART = [".##.##.", "#######", "#######", ".#####.", "..###.."]

    def valentine_wall(self):
        pts = self.rod_garland((200, 160, 170))
        for i, (x, y) in enumerate(pts[2::9]):
            c = (236, 90, 120) if i % 2 == 0 else (250, 170, 190)
            self.stamp(self.HEART, x - 3, y + 1, {"#": c})
            self.px(round(x) - 2, round(y) + 2, self.sh(c, 1.2))
        pts = self.shelf_garland((200, 160, 170))
        for i, (x, y) in enumerate(pts[3::8]):
            self.stamp(self.HEART[:4], x - 3, y + 1, {"#": (236, 90, 120) if i % 2 else (250, 170, 190)})
        for (x, y) in [(124, 28), (140, 34)]:                 # valentines pinned on the corkboard
            self.stamp(self.HEART, x, y, {"#": (236, 90, 120)}); self.px(x + 1, y + 1, (250, 160, 180))

    def valentine_desk(self):
        x, y = self.wp(147, 78, 0.3)                          # roses in a vase on the desk
        x, y = round(x), round(y)
        self.R(x - 2, y - 5, x + 2, y, (200, 220, 235)); self.R(x + 1, y - 5, x + 2, y, (170, 190, 210))
        for (dx, dy, c) in [(-2, -8, (220, 50, 70)), (1, -9, (240, 90, 120)), (0, -7, (210, 40, 60)), (3, -8, (220, 50, 70))]:
            self.ball(x + dx, y + dy, 1.4, 1.4, c, spec=False)
        self.d.line([(x, y - 6), (x, y - 5)], fill=(80, 140, 80))

    def valentine_floor(self):
        pass
