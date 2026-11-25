"""Renders every room (normal 256 wide, and wide 344 for the rectangle widget) plus the sleeping-lump
covers overlays. Run from tools/room:  python3 render_all.py   (results land in final/)."""
import os, subprocess, shutil, json
from PIL import Image
T = ["sunrise", "day", "sunset", "night"]; WS = ["clear", "cloudy", "rain", "storm", "snow"]
CO, CS = (204, 82), (36, 20)                  # covers overlay origin / size (room px)
os.makedirs("final/normal", exist_ok=True); os.makedirs("final/wide", exist_ok=True); os.makedirs("final/covers", exist_ok=True)
for wide in (False, True):
    env = dict(os.environ, WIDE="1" if wide else "0"); out = "out5_wide" if wide else "out5"
    tag = "w" if wide else ""
    for t in T:
        for w in WS:
            for b in (0, 1):
                subprocess.run(["python3", "room.py", t, w, f"lump{b}"], env=env, check=True, capture_output=True)
                Image.open(f"{out}/room_{t}_{w}.png").crop((CO[0], CO[1], CO[0] + CS[0], CO[1] + CS[1])).save(f"final/covers/covers{tag}{b}_{t}_{w}.png")
            subprocess.run(["python3", "room.py", t, w], env=env, check=True, capture_output=True)
            dst = "final/wide" if wide else "final/normal"
            shutil.copy(f"{out}/room_{t}_{w}.png", f"{dst}/room_{t}_{w}.png")
            shutil.copy(f"{out}/room_{t}_{w}.json", f"{dst}/room_{t}_{w}.json")
    shutil.copy(f"{out}/glass_mask.png", f"final/{'wide' if wide else 'normal'}/glass_mask.png")
    shutil.copy(f"{out}/front_mask.png", f"final/{'wide' if wide else 'normal'}/front_mask.png")
    # overlays cut from each room: the desk chair (drawn over the animations) and the front plant (drawn over the pal)
    import numpy as np
    chair = np.asarray(Image.open(f"{out}/chair_mask.png").convert("L")) > 0
    plant = (np.asarray(Image.open(f"{out}/front_mask.png").convert("L")) > 0) & ~chair
    os.makedirs("final/overlays", exist_ok=True)
    boxes = {}
    for name, m in (("chair", chair), ("fgplant", plant)):
        ys, xs = np.nonzero(m); box = (int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1); boxes[name] = box
        for t in T:
            for w in WS:
                room = np.asarray(Image.open(f"{'final/wide' if wide else 'final/normal'}/room_{t}_{w}.png").convert("RGBA")).copy()
                room[~m, 3] = 0
                Image.fromarray(room).crop(box).save(f"final/overlays/{name}{tag}_{t}_{w}.png")
    json.dump(boxes, open(f"final/overlays/boxes{tag}.json", "w"))
    print("overlay boxes", tag or "normal", boxes)
print("done")
