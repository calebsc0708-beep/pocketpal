"""Turns the pals into frames for the desktop app: desktop/assets/<pal>/NN.png + frames.json.

- Pals with a GIF (Pals/<name>/front.gif) use every frame at the GIF's own timing — the same
  idle animation the Dynamic Island shows, just smoother.
- Island-only sprites (Sprites/<name>_1..10.png, like Absol) use their 10 frames.
- Single pictures (Sprites/rei_chibi.png) get a gentle 2-frame bob.
Every frame of a pal shares one canvas with the feet on the bottom row, so nothing jumps.
"""
import json, os, re, shutil, glob
from PIL import Image, ImageSequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "desktop", "assets")
NAMES = {"rei_chibi": "Rei"}   # pals in Pals/ take their name from pal.json (or the folder name)


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

def hard_alpha(im):
    """Pixel art: every pixel is either fully there or fully gone (needed for the see-through window)."""
    im = im.convert("RGBA")
    a = im.getchannel("A").point(lambda v: 255 if v >= 128 else 0)
    im.putalpha(a)
    return im


def gif_frames(path):
    g = Image.open(path)
    frames, durs = [], []
    for fr in ImageSequence.Iterator(g):
        frames.append(hard_alpha(fr.copy()))
        durs.append(max(20, fr.info.get("duration", g.info.get("duration", 100)) or 100))
    return frames, durs


def save_pal(key, frames, durs):
    boxes = [f.getbbox() for f in frames if f.getbbox()]
    l = min(b[0] for b in boxes); t = min(b[1] for b in boxes)
    r = max(b[2] for b in boxes); b_ = max(b[3] for b in boxes)
    d = os.path.join(OUT, key); os.makedirs(d, exist_ok=True)
    for i, f in enumerate(frames):
        save_png(f.crop((l, t, r, b_)), os.path.join(d, f"{i:03d}.png"))
    json.dump({"name": NAMES.get(key, key.title()), "durations": durs, "size": [r - l, b_ - t]},
              open(os.path.join(d, "frames.json"), "w"))
    print(f"{key}: {len(frames)} frames, {r - l}x{b_ - t}")


def main():
    shutil.rmtree(OUT, ignore_errors=True)
    os.makedirs(OUT)
    done = set()
    for gif in sorted(glob.glob(os.path.join(ROOT, "Pals", "*", "front.gif"))):
        key = os.path.basename(os.path.dirname(gif))
        meta = os.path.join(os.path.dirname(gif), "pal.json")
        NAMES[key] = json.load(open(meta)).get("name", key.title()) if os.path.exists(meta) else key.title()
        save_pal(key, *gif_frames(gif)); done.add(key)
    # island-only sprites with numbered frames
    seq = {}
    for p in glob.glob(os.path.join(ROOT, "Sprites", "*_*.png")):
        m = re.match(r"(.+)_(\d+)\.png$", os.path.basename(p))
        if m and m.group(1) not in done:
            seq.setdefault(m.group(1), []).append((int(m.group(2)), p))
    for key, items in sorted(seq.items()):
        frames = [hard_alpha(Image.open(p)) for _, p in sorted(items)]
        # big sprites (Absol is 192px) are shrunk to roughly the pals' size so they read as pixel art
        if frames[0].width > 96:
            k = frames[0].width // 64
            frames = [f.resize((f.width // k, f.height // k), Image.NEAREST) for f in frames]
        save_pal(key, frames, [120] * len(frames)); done.add(key)
    # single pictures: a little breathing bob
    for p in glob.glob(os.path.join(ROOT, "Sprites", "*.png")):
        key = os.path.splitext(os.path.basename(p))[0]
        if re.search(r"_\d+$", key) or key in done:
            continue
        im = hard_alpha(Image.open(p))
        if im.width > 96:
            k = im.width // 64
            im = im.resize((im.width // k, im.height // k), Image.NEAREST)
        up = Image.new("RGBA", (im.width, im.height + 1)); up.paste(im, (0, 0))
        down = Image.new("RGBA", (im.width, im.height + 1)); down.paste(im, (0, 1))
        save_pal(key, [down, up], [700, 700]); done.add(key)
    # window icon: the app icon
    icons = sorted(glob.glob(os.path.join(ROOT, "Pal", "PalSprites.xcassets", "AppIcon.appiconset", "*.png")))
    if icons:
        Image.open(icons[0]).convert("RGBA").resize((64, 64), Image.NEAREST).save(os.path.join(OUT, "icon.png"))


if __name__ == "__main__":
    main()
