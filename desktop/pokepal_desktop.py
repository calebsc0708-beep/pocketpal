"""PokePal for the desktop: your pal sitting in the corner of the screen, playing its idle animation.

- Sits just above the taskbar in the bottom-right corner (drag it anywhere; it remembers).
- Click it for a little hop. Right-click for: pal, size, start with Windows, quit.
Windows only (uses a see-through window).
"""
import json, os, sys, tkinter as tk

APP = "PokePal"
KEY = "#ff00fe"                       # this exact colour is see-through
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(HERE, "assets")
CONF_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), APP)
CONF = os.path.join(CONF_DIR, "settings.json")
MARGIN = 12                           # gap from the screen edges


def load_settings():
    try:
        return json.load(open(CONF))
    except Exception:
        return {}


def save_settings(s):
    try:
        os.makedirs(CONF_DIR, exist_ok=True)
        json.dump(s, open(CONF, "w"))
    except Exception:
        pass


def work_area(root):
    """Screen area without the taskbar (Windows), so the pal sits right on top of it."""
    try:
        import ctypes
        from ctypes import wintypes
        r = wintypes.RECT()
        ctypes.windll.user32.SystemParametersInfoW(48, 0, ctypes.byref(r), 0)   # SPI_GETWORKAREA
        return r.left, r.top, r.right, r.bottom
    except Exception:
        return 0, 0, root.winfo_screenwidth(), root.winfo_screenheight() - 48


# ---------------- start with Windows (current user only) ----------------
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def autostart_enabled():
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as k:
            winreg.QueryValueEx(k, APP)
            return True
    except Exception:
        return False


def set_autostart(on):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
            if on:
                exe = sys.executable if getattr(sys, "frozen", False) else f'"{sys.executable}" "{os.path.abspath(__file__)}"'
                winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, f'"{exe}"' if getattr(sys, "frozen", False) else exe)
            else:
                winreg.DeleteValue(k, APP)
    except Exception:
        pass


# ---------------- frames ----------------
def pal_list():
    out = []
    for key in sorted(os.listdir(ASSETS)):
        meta = os.path.join(ASSETS, key, "frames.json")
        if os.path.exists(meta):
            out.append((key, json.load(open(meta))["name"]))
    order = {"eevee": 0, "pikachu": 1, "minccino": 2}
    return sorted(out, key=lambda p: (order.get(p[0], 9), p[1]))


def load_frames(key, scale):
    """Frames as Tk images, enlarged with hard pixel edges (no blur)."""
    meta = json.load(open(os.path.join(ASSETS, key, "frames.json")))
    frames = []
    for i in range(len(meta["durations"])):
        img = tk.PhotoImage(file=os.path.join(ASSETS, key, f"{i:03d}.png"))
        frames.append(img.zoom(scale, scale))
    return frames, meta["durations"]


class Pal:
    HOP = [0, -3, -5, -6, -6, -5, -3, 0, -1, 0]     # pixels (before scaling), one step every 30 ms

    def __init__(self):
        self.settings = load_settings()
        self.pals = pal_list()
        keys = [k for k, _ in self.pals]
        self.key = self.settings.get("pal") if self.settings.get("pal") in keys else keys[0]
        self.scale = int(self.settings.get("scale", 3))

        self.root = tk.Tk()
        self.root.title(APP)
        self.root.overrideredirect(True)           # no border, no title bar, no taskbar button
        self.root.attributes("-topmost", True)
        self.root.configure(bg=KEY)
        try:
            self.root.attributes("-transparentcolor", KEY)
        except tk.TclError:
            pass                                    # not Windows: shows a pink box, but still runs
        icon = os.path.join(ASSETS, "icon.png")
        if os.path.exists(icon):
            try:
                self.root.iconphoto(True, tk.PhotoImage(file=icon))
            except tk.TclError:
                pass

        self.canvas = tk.Canvas(self.root, bg=KEY, bd=0, highlightthickness=0)
        self.canvas.pack()
        self.sprite = self.canvas.create_image(0, 0, anchor="s")
        self.label = self.canvas
        self.frame_i = 0
        self.hop_i = None
        self.anim_job = None

        self.label.bind("<ButtonPress-1>", self.press)
        self.label.bind("<B1-Motion>", self.drag)
        self.label.bind("<ButtonRelease-1>", self.release)
        self.label.bind("<Button-3>", self.menu)

        self.load()
        self.place_initial()
        self.root.after(2000, self.keep_on_top)

    # ----- frames / sizing -----
    def load(self):
        self.frames, self.durs = load_frames(self.key, self.scale)
        w = max(f.width() for f in self.frames); h = max(f.height() for f in self.frames)
        self.pad = 6 * self.scale                   # headroom for the hop
        self.w, self.h = w, h + self.pad
        self.canvas.configure(width=self.w, height=self.h)
        self.frame_i = 0
        if self.anim_job:
            self.root.after_cancel(self.anim_job)
        self.animate()

    def animate(self):
        self.frame_i %= len(self.frames)
        self.show()
        self.anim_job = self.root.after(self.durs[self.frame_i], self.next_frame)

    def next_frame(self):
        self.frame_i += 1
        self.animate()

    def show(self):
        lift = self.HOP[self.hop_i] if self.hop_i is not None else 0
        # feet on the bottom edge; the hop just lifts it inside the window
        self.canvas.itemconfigure(self.sprite, image=self.frames[self.frame_i % len(self.frames)])
        self.canvas.coords(self.sprite, self.w // 2, self.h + lift * self.scale)

    # ----- position -----
    def place_initial(self):
        l, t, r, b = work_area(self.root)
        x, y = self.settings.get("x"), self.settings.get("y")
        if x is None or y is None or not (l - self.w < x < r and t - self.h < y < b):
            x, y = r - self.w - MARGIN, b - self.h          # bottom-right, sitting on the taskbar
        self.move(x, y)

    def move(self, x, y):
        self.x, self.y = int(x), int(y)
        self.root.geometry(f"{self.w}x{self.h}+{self.x}+{self.y}")

    def keep_on_top(self):
        self.root.attributes("-topmost", True)      # some full-screen apps knock us down; climb back up
        self.root.after(5000, self.keep_on_top)

    # ----- mouse -----
    def press(self, e):
        self.drag_from = (e.x_root, e.y_root, self.x, self.y)
        self.dragged = False

    def drag(self, e):
        dx = e.x_root - self.drag_from[0]; dy = e.y_root - self.drag_from[1]
        if abs(dx) + abs(dy) > 3:
            self.dragged = True
        if self.dragged:
            self.move(self.drag_from[2] + dx, self.drag_from[3] + dy)

    def release(self, e):
        if self.dragged:
            self.settings.update(x=self.x, y=self.y); save_settings(self.settings)
        else:
            self.hop()

    def hop(self):
        if self.hop_i is not None:
            return
        self.hop_i = 0
        def step():
            self.show()
            self.hop_i += 1
            if self.hop_i < len(self.HOP):
                self.root.after(30, step)
            else:
                self.hop_i = None; self.show()
        step()

    def menu(self, e):
        m = tk.Menu(self.root, tearoff=0)
        pm = tk.Menu(m, tearoff=0)
        self.pal_var = tk.StringVar(value=self.key)
        for key, name in self.pals:
            pm.add_radiobutton(label=name, value=key, variable=self.pal_var, command=self.pick_pal)
        m.add_cascade(label="Pal", menu=pm)
        sm = tk.Menu(m, tearoff=0)
        self.size_var = tk.IntVar(value=self.scale)
        for s in (2, 3, 4, 5):
            sm.add_radiobutton(label=f"{s}×", value=s, variable=self.size_var, command=self.pick_size)
        m.add_cascade(label="Size", menu=sm)
        m.add_separator()
        self.auto_var = tk.BooleanVar(value=autostart_enabled())
        m.add_checkbutton(label="Start with Windows", variable=self.auto_var,
                          command=lambda: set_autostart(self.auto_var.get()))
        m.add_command(label="Back to the corner", command=self.reset_corner)
        m.add_separator()
        m.add_command(label="Quit", command=self.root.destroy)
        m.tk_popup(e.x_root, e.y_root)

    def pick_pal(self):
        self.keep_feet(lambda: setattr(self, "key", self.pal_var.get()))
        self.settings["pal"] = self.key; save_settings(self.settings)

    def pick_size(self):
        self.keep_feet(lambda: setattr(self, "scale", self.size_var.get()))
        self.settings["scale"] = self.scale; save_settings(self.settings)

    def keep_feet(self, change):
        """Swap pal/size but keep its feet and right edge where they were."""
        right, bottom = self.x + self.w, self.y + self.h
        change(); self.load()
        self.move(right - self.w, bottom - self.h)
        self.settings.update(x=self.x, y=self.y); save_settings(self.settings)

    def reset_corner(self):
        l, t, r, b = work_area(self.root)
        self.move(r - self.w - MARGIN, b - self.h)
        self.settings.update(x=self.x, y=self.y); save_settings(self.settings)

    def run(self):
        if os.environ.get("POKEPAL_SMOKE"):          # CI check: cycle every pal and size, then quit
            steps = [(k, sc) for k, _ in self.pals for sc in (2, 5)]
            def nxt(i=0):
                if i == len(steps):
                    print("smoke ok:", len(steps), "pal/size combos"); self.root.destroy(); return
                self.key, self.scale = steps[i]; self.load(); self.hop()
                self.root.after(150, lambda: nxt(i + 1))
            self.root.after(300, nxt)
        self.root.mainloop()


if __name__ == "__main__":
    try:  # crisp on high-DPI screens
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    Pal().run()
