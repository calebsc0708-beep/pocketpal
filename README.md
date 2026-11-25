# PokePal

A cozy pixel room where your pal lives. It wanders around, faces the way it walks, turns its back when it
heads to the back wall, and curls up under the covers at night. The room follows your real time of day and
weather (clouds, rain, snow, storms, sunrise and sunset). The original Dynamic Island sprite feature is in the
**Island** tab.

## The Room tab
- Pick your pal (Eevee, Pikachu or Minccino) and its name in **Settings** (gear button).
- Weather comes from Open-Meteo using your rough location (allow location when asked). Without it, the room follows the clock.
- Code and art live in the `Pal` folder: Swift files, `PalSprites.xcassets` (pals, rooms, quilt, app icon) and the Pixelify Sans font.

## Room widget (medium and large)
Add **PokePal Room** from the widget gallery, then long-press it → **Edit Widget** to choose the pal and motion:
- **Still**: the pal stands somewhere new each time the widget refreshes (about every 15 minutes)
- **Idle**: plays the pal's animation in place, once a second
- **Hop around**: the pal hops between 10 spots on the rug, once a second

Home Screen widgets can't really animate, so Idle and Hop use the same font trick as the Dynamic Island
(`tools/build_room_fonts.py` builds those fonts during the GitHub build). It's 1 frame a second, and a future
iOS update could break it; if it does, the widget falls back to a still picture. At night the pal is asleep
under the covers in every mode.

## Dynamic Island sprites (Island tab)
Puts a little sprite of your choice in your iPhone's Dynamic Island (iPhone 14 Pro or newer).

## 1. Add your sprites
Drop PNG files into the `Sprites` folder.

- **Still sprite:** one file, e.g. `pikachu.png`
- **Animated sprite:** numbered frames, e.g. `pikachu_1.png`, `pikachu_2.png`. The frames change once per second.
  2, 5 or 10 frames loop perfectly. Other counts hiccup once every 10 seconds.
- Square, small pixel sprites with transparent backgrounds look best (around 32–128 px). All frames should be the same size.

## 2. Build the .ipa on GitHub (no Mac needed)
1. Create a new repository on github.com and upload everything in this folder, including the hidden `.github` folder. Use GitHub Desktop or `git push`; the web uploader can skip hidden folders.
2. Go to the **Actions** tab. A build starts on every push, or you can run **Build IPA** by hand.
3. When it finishes (about 3–5 min), open the run and download **PocketPal-ipa** at the bottom. It's a .zip containing `PocketPal.ipa`.

## 3. Install with SideStore
1. Unzip the download and get `PocketPal.ipa` onto your phone (iCloud Drive, AirDrop from a Mac, etc.).
2. Open SideStore → My Apps → **+** → choose the .ipa.
3. Open Pocket Pal, tap a sprite, then tap **Show in Dynamic Island**.

## Things to know
- iOS keeps a Live Activity in the Dynamic Island for up to 8 hours, then ends it. Open the app and tap Show again.
- Animation uses a workaround: a ticking timer drawn in a custom font whose digits are your frames. That limits it to 1 frame per second, and a future iOS update could break it. If it does, the sprite falls back to a still image.
- The app plus its widget uses 2 of your free Apple ID's App IDs in SideStore.
- To change sprites, edit the `Sprites` folder, push, and install the new build over the old one.
