"""Cut the item sprites out of the sheets the user sent (backgrounds removed by flood fill from each cell's edge)."""
import numpy as np
from PIL import Image
from collections import deque
U = "/mnt/user-data/uploads/"

def cells_by_separators(a, sep):
    """Split on full rows/columns made only of separator colours."""
    def runs(mask):
        out, start = [], None
        for i, v in enumerate(mask):
            if not v and start is None: start = i
            if v and start is not None: out.append((start, i)); start = None
        if start is not None: out.append((start, len(mask)))
        return out
    is_sep = np.zeros(a.shape[:2], bool)
    for c in sep: is_sep |= (a[..., :3] == c).all(2)
    cols = runs(is_sep.all(0)); rows = runs(is_sep.all(1))
    return [(x0, y0, x1, y1) for (y0, y1) in rows for (x0, x1) in cols]

def cut(a, box):
    x0, y0, x1, y1 = box
    c = a[y0:y1, x0:x1].copy()
    H, W = c.shape[:2]
    rgb = c[..., :3].astype(int)
    magenta = (rgb[..., 0] > 190) & (rgb[..., 1] < 80) & (rgb[..., 2] > 190)     # guide ticks (any magenta shade)
    # background = the colours on the cell's border (ignoring magenta guide ticks)
    ring = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    ring = [tuple(v) for v in ring if tuple(v) != (255, 0, 255)]
    bgs = set(v for v in ring if ring.count(v) > 2)
    isbg = np.zeros((H, W), bool)
    for b in bgs: isbg |= (rgb == b).all(2)
    isbg |= magenta
    gone = np.zeros((H, W), bool); q = deque()
    for y in range(H):
        for x in (0, W - 1):
            if isbg[y, x]: q.append((y, x))
    for x in range(W):
        for y in (0, H - 1):
            if isbg[y, x]: q.append((y, x))
    while q:
        y, x = q.popleft()
        if gone[y, x] or not isbg[y, x]: continue
        gone[y, x] = True
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            ny, nx = y + dy, x + dx
            if 0 <= ny < H and 0 <= nx < W and not gone[ny, nx]: q.append((ny, nx))
    gone |= magenta
    # background colours of the green sheets also show through enclosed gaps (bag handle): clear them too
    for b in bgs:
        if b in ((56, 224, 152), (120, 240, 192)):
            gone |= (rgb == b).all(2)
    # keep only real sprite pieces: drop tiny specks left from guide marks / cell edges
    keep = ~gone
    lab = np.zeros((H, W), int); n = 0; sizes = {}
    for y in range(H):
        for x in range(W):
            if keep[y, x] and not lab[y, x]:
                n += 1; q = deque([(y, x)]); lab[y, x] = n; cnt = 0
                while q:
                    cy, cx = q.popleft(); cnt += 1
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)):
                        ny, nx = cy + dy, cx + dx
                        if 0 <= ny < H and 0 <= nx < W and keep[ny, nx] and not lab[ny, nx]:
                            lab[ny, nx] = n; q.append((ny, nx))
                sizes[n] = cnt
    big = max(sizes.values()) if sizes else 0
    for k, v in sizes.items():
        if v < max(6, big * 0.04): gone |= lab == k
    out = c.copy(); out[..., 3] = np.where(gone, 0, 255)
    im = Image.fromarray(out, "RGBA")
    bb = im.getbbox()
    return im.crop(bb) if bb else None

def load(n): return np.asarray(Image.open(U + n + "-image.png").convert("RGBA"))

items = {}
# ball sheet: first row (closed, facing you): ultra, great, poke
a = load("72490f92")
row = a[0:40]
for name, (x0, x1) in zip(["ultraball", "greatball", "pokeball"], [(0, 39), (39, 78), (78, 117)]):
    items[name] = cut(a, (x0, 2, x1, 36))
sheets = {
    "2a9b84d6": ["ultraball_icon", "greatball_icon", "fastball"],
    "b76e2d28": ["potion_purple", "potion_pink", "potion_orange"],
    "a7ed567c": ["berry_orange", "berry_blue"],
    "4babb49c": ["fruit_yellow"],
    "fa6637ec": ["witch_hat", "santa_hat"],
    "3c1800e1": ["pikachu_bag", "pink_bag"],
    "f928af3d": ["glasses_black", "glasses_round"],
}
for n, names in sheets.items():
    a = load(n)
    boxes = cells_by_separators(a, [(255, 255, 255), (224, 224, 224)])
    boxes = [b for b in boxes if (b[2] - b[0]) > 8 and (b[3] - b[1]) > 8]
    for name, b in zip(names, boxes):
        items[name] = cut(a, b)
for k, im in items.items():
    im.save(f"{k}.png"); print(k, im.size)
