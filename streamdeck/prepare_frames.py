"""Pre-renders everything the Stream Deck key needs, at key size (144 x 144, the @2x key):

  <plugin>/imgs/pals/<pal>/NNN.png   the pal's idle frames, pixel-doubled, feet near the bottom
  <plugin>/imgs/pals/<pal>/pal.json  name + frame durations
  <plugin>/imgs/bg/<time>.png        a slice of the pixel room for each time of day
  plus the plugin/action icons.

Frames come from desktop/prepare_assets.py (same idle animation as the Dynamic Island).
"""
import json, os, shutil, subprocess, sys
from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "streamdeck", "com.calebsc.pokepal.sdPlugin")
DESK = os.path.join(ROOT, "desktop", "assets")
ROOMS = os.path.join(ROOT, "Pal", "PalSprites.xcassets")
KEY = 144
FLOOR = 132          # pal's feet line on the key
BG_CROP = (60, 76, 132, 148)   # 72x72 room px: window seat, desk leg, rug and floor -> doubled to 144


def save_png(img, path):
    """Lossless and small: pixel art gets a colour palette (exactly the same pixels) when it fits in 256."""
    import numpy as np
    a = np.asarray(img.convert("RGBA"))
    packed = np.ascontiguousarray(a).view(np.uint32).reshape(-1)
    packed = np.where(a[..., 3].reshape(-1) == 0, 0, packed)
    uniq, idx = np.unique(packed, return_inverse=True)
    if len(uniq) <= 256:
        cols = uniq.view(np.uint8).reshape(-1, 4)
        p = Image.fromarray(idx.reshape(a.shape[:2]).astype(np.uint8), "P")
        p.putpalette(cols[:, :3].flatten().tolist())
        p.save(path, optimize=True, transparency=bytes(cols[:, 3].tolist()))
    else:
        img.save(path, optimize=True)

def main():
    subprocess.run([sys.executable, os.path.join(ROOT, "desktop", "prepare_assets.py")], check=True)
    out = os.path.join(PLUGIN, "imgs")
    for sub in ("pals", "bg"):
        shutil.rmtree(os.path.join(out, sub), ignore_errors=True)

    # --- pal frames
    for key in sorted(os.listdir(DESK)):
        meta_p = os.path.join(DESK, key, "frames.json")
        if not os.path.exists(meta_p):
            continue
        meta = json.load(open(meta_p))
        w, h = meta["size"]
        s = max(1, min(3, 128 // h, 160 // w))           # whole-number pixel scale; a swinging tail may clip a little
        d = os.path.join(out, "pals", key); os.makedirs(d)
        for i in range(len(meta["durations"])):
            f = Image.open(os.path.join(DESK, key, f"{i:03d}.png")).convert("RGBA")
            f = f.resize((f.width * s, f.height * s), Image.NEAREST)
            c = Image.new("RGBA", (KEY, KEY))
            c.paste(f, ((KEY - f.width) // 2, FLOOR - f.height), f)
            save_png(c, os.path.join(d, f"{i:03d}.png"))
        json.dump({"name": meta["name"], "durations": meta["durations"], "scale": s},
                  open(os.path.join(d, "pal.json"), "w"))
        print(f"{key}: {len(meta['durations'])} frames at {s}x")

    # --- room backgrounds (clear weather; one per time of day), with a soft shadow spot for the pal
    os.makedirs(os.path.join(out, "bg"))
    for t in ("sunrise", "day", "sunset", "night"):
        im = Image.open(os.path.join(ROOMS, f"room_{t}_clear.imageset", f"room_{t}_clear.png")).convert("RGBA")
        im = im.crop(BG_CROP).resize((KEY, KEY), Image.NEAREST)
        sh = Image.new("RGBA", (KEY, KEY)); ImageDraw.Draw(sh).ellipse([KEY // 2 - 30, FLOOR - 5, KEY // 2 + 30, FLOOR + 5], fill=(0, 0, 0, 70))
        im.alpha_composite(sh)
        im.convert("RGB").save(os.path.join(out, "bg", f"{t}.png"), optimize=True)
    dark = Image.new("RGBA", (KEY, KEY), (24, 22, 30, 255))
    sh = Image.new("RGBA", (KEY, KEY)); ImageDraw.Draw(sh).ellipse([KEY // 2 - 30, FLOOR - 5, KEY // 2 + 30, FLOOR + 5], fill=(0, 0, 0, 120))
    dark.alpha_composite(sh); dark.convert("RGB").save(os.path.join(out, "bg", "dark.png"))

    # --- icons: plugin/category/action icons from the pal, key default image from the day room + eevee
    eevee = Image.open(os.path.join(out, "pals", "eevee", "000.png")).convert("RGBA")
    def icon(path, size, mono=False):
        src = eevee.crop(eevee.getbbox())
        if mono:   # Stream Deck wants white glyphs for the action list / category
            a = src.getchannel("A"); src = Image.new("RGBA", src.size, (255, 255, 255, 255)); src.putalpha(a)
        k = min(size / src.width, size / src.height)
        src = src.resize((max(1, int(src.width * k)), max(1, int(src.height * k))), Image.NEAREST)
        c = Image.new("RGBA", (size, size)); c.paste(src, ((size - src.width) // 2, (size - src.height) // 2), src)
        os.makedirs(os.path.dirname(path), exist_ok=True); c.save(path)
    for base, size, mono in (("plugin/category-icon", 28, True), ("actions/pal/icon", 20, True), ("plugin/marketplace", 256, False)):
        icon(os.path.join(out, base + ".png"), size, mono)
        icon(os.path.join(out, base + "@2x.png"), size * 2, mono)
    # the key's settings list every pal that was built
    pals = sorted(k for k in os.listdir(os.path.join(out, "pals")))
    order = {"eevee": 0, "pikachu": 1, "minccino": 2}
    pals.sort(key=lambda k: (order.get(k, 9), k))
    opts = "\n".join(f'\t\t\t\t<option value="{k}">{json.load(open(os.path.join(out, "pals", k, "pal.json")))["name"]}</option>'
                     for k in pals)
    ui = os.path.join(PLUGIN, "ui", "pal.html")
    html = open(ui).read()
    start = html.index('<sdpi-select setting="pal" default="eevee">') + len('<sdpi-select setting="pal" default="eevee">')
    end = html.index("</sdpi-select>", start)
    open(ui, "w").write(html[:start] + "\n" + opts + "\n\t\t\t" + html[end:])
    keyimg = Image.open(os.path.join(out, "bg", "day.png")).convert("RGBA"); keyimg.alpha_composite(eevee)
    keyimg.save(os.path.join(out, "actions", "pal", "key@2x.png"))
    keyimg.resize((72, 72), Image.NEAREST).save(os.path.join(out, "actions", "pal", "key.png"))


if __name__ == "__main__":
    main()
