import streamDeck, { action, KeyAction, KeyDownEvent, SingletonAction, WillAppearEvent, WillDisappearEvent, DidReceiveSettingsEvent } from "@elgato/streamdeck";
import { readFileSync, readdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

/** Settings chosen in the key's settings panel. */
type PalSettings = {
	pal?: string;          // eevee, pikachu, minccino, absol, rei_chibi
	background?: string;   // "room" (follows your time of day) or "dark"
};

const IMGS = join(dirname(fileURLToPath(import.meta.url)), "..", "imgs");
const TICK = 100;                 // ms between key updates (10 fps is plenty, and kind to Stream Deck)

type Pal = { frames: string[]; durations: number[]; total: number };
const pals = new Map<string, Pal>();
const backgrounds = new Map<string, string>();

function b64(path: string): string {
	return readFileSync(path).toString("base64");
}

/** Loads a pal's frames once (as base64 PNGs) the first time a key needs it. */
function getPal(key: string): Pal {
	let pal = pals.get(key);
	if (pal) return pal;
	let dir = join(IMGS, "pals", key);
	if (!existsSync(dir)) dir = join(IMGS, "pals", "eevee");
	const meta = JSON.parse(readFileSync(join(dir, "pal.json"), "utf8")) as { durations: number[] };
	const files = readdirSync(dir).filter((f) => f.endsWith(".png")).sort();
	pal = { frames: files.map((f) => b64(join(dir, f))), durations: meta.durations, total: meta.durations.reduce((a, b) => a + b, 0) };
	pals.set(key, pal);
	return pal;
}

function getBackground(name: string): string {
	let bg = backgrounds.get(name);
	if (!bg) {
		bg = b64(join(IMGS, "bg", `${name}.png`));
		backgrounds.set(name, bg);
	}
	return bg;
}

/** Same day/night split as the room: sunrise 6–8, day 8–17, sunset 17–19:30, night otherwise. */
function timeOfDay(now = new Date()): string {
	const h = now.getHours() + now.getMinutes() / 60;
	if (h >= 6 && h < 8) return "sunrise";
	if (h >= 8 && h < 17) return "day";
	if (h >= 17 && h < 19.5) return "sunset";
	return "night";
}

const HOP = [0, 6, 10, 12, 12, 10, 6, 0, 2, 0];   // key pixels (of 144), one step per tick
const HEART = ["0110110", "1111111", "1111111", "0111110", "0011100", "0001000"];

/** One running key: its settings and where it is in the animation. */
class Running {
	start = Date.now();
	hop = -1;
	last = "";   // what's on the key now: skip sending the same picture again
	heart = -1;
	timer: NodeJS.Timeout;
	constructor(public action: KeyAction<PalSettings>, public settings: PalSettings) {
		this.timer = setInterval(() => this.draw(), TICK);
		this.draw();
	}
	draw(): void {
		const pal = getPal(this.settings.pal ?? "eevee");
		// pick the frame by elapsed time so it plays at the GIF's own speed
		let t = (Date.now() - this.start) % pal.total, i = 0;
		while (t >= pal.durations[i]) { t -= pal.durations[i]; i++; }
		const bgName = this.settings.background === "dark" ? "dark" : timeOfDay();
		const bg = getBackground(bgName);
		const lift = this.hop >= 0 ? HOP[this.hop] : 0;
		const state = `${this.settings.pal}|${i}|${bgName}|${this.hop}|${this.heart}`;
		if (state === this.last) return;      // nothing changed since the last tick (e.g. a slow frame)
		this.last = state;
		let heart = "";
		if (this.heart >= 0) {
			const y = 34 - this.heart * 3, x = 96, a = Math.max(0, 1 - this.heart / 12);
			HEART.forEach((row, r) => [...row].forEach((c, k) => {
				if (c === "1") heart += `<rect x="${x + k * 3}" y="${y + r * 3}" width="3" height="3" fill="#ff6b8a" opacity="${a.toFixed(2)}"/>`;
			}));
		}
		const svg =
			`<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="144" height="144" viewBox="0 0 144 144" shape-rendering="crispEdges">` +
			`<image width="144" height="144" xlink:href="data:image/png;base64,${bg}"/>` +
			`<image y="${-lift}" width="144" height="144" xlink:href="data:image/png;base64,${pal.frames[i]}"/>` +
			heart + `</svg>`;
		this.action.setImage(`data:image/svg+xml;base64,${Buffer.from(svg).toString("base64")}`).catch(() => {});
		if (this.hop >= 0 && ++this.hop >= HOP.length) this.hop = -1;
		if (this.heart >= 0 && ++this.heart > 12) this.heart = -1;
	}
	stop(): void {
		clearInterval(this.timer);
	}
}

/** The PokePal key: your pal's idle animation on a slice of its room. Press it to make it hop. */
@action({ UUID: "com.calebsc.pokepal.pal" })
export class PalKey extends SingletonAction<PalSettings> {
	private running = new Map<string, Running>();

	override onWillAppear(ev: WillAppearEvent<PalSettings>): void {
		if (!ev.action.isKey()) return;
		this.running.get(ev.action.id)?.stop();
		this.running.set(ev.action.id, new Running(ev.action, ev.payload.settings));
	}

	override onWillDisappear(ev: WillDisappearEvent<PalSettings>): void {
		this.running.get(ev.action.id)?.stop();
		this.running.delete(ev.action.id);
	}

	override onDidReceiveSettings(ev: DidReceiveSettingsEvent<PalSettings>): void {
		const r = this.running.get(ev.action.id);
		if (r) { r.settings = ev.payload.settings; r.start = Date.now(); r.last = ""; r.draw(); }
	}

	override onKeyDown(ev: KeyDownEvent<PalSettings>): void {
		const r = this.running.get(ev.action.id);
		if (r) { r.hop = 0; r.heart = 0; }
		streamDeck.logger.info(`hop: ${ev.payload.settings.pal ?? "eevee"}`);
	}
}
