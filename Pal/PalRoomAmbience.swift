import SwiftUI

enum RoomTime: String, CaseIterable { case sunrise, day, sunset, night }
enum RoomWeather: String, CaseIterable { case clear, cloudy, rain, storm, snow }

extension RoomTime {
    /// Asset name of the matching room background, e.g. "room_day_clear".
    func roomImage(_ weather: RoomWeather) -> String { "room_\(rawValue)_\(weather.rawValue)" }
}

/// Animated details drawn on top of the room art: floating music notes from the record player,
/// mug steam, candle flicker, twinkling string lights, dust in the sunbeam, rain/snow/stars
/// in the window and lightning. Everything is a pure function of `t`, so there's no state.
/// Coordinates are room pixels (the room art is 256 x 160).
struct PalRoomAmbience: View {
    let time: RoomTime
    let weather: RoomWeather
    let t: Double
    var palAsleep: Bool = false

    var body: some View {
        Canvas { ctx, size in
            let s = size.width / 256
            func dot(_ x: Double, _ y: Double, _ c: (Double, Double, Double), _ a: Double) {
                guard a > 0 else { return }
                ctx.fill(Path(CGRect(x: x.rounded(.down) * s, y: y.rounded(.down) * s, width: s, height: s)),
                         with: .color(Color(red: c.0 / 255, green: c.1 / 255, blue: c.2 / 255).opacity(min(a, 1))))
            }
            func rect(_ x0: Double, _ y0: Double, _ x1: Double, _ y1: Double) -> CGRect {
                CGRect(x: x0 * s, y: y0 * s, width: (x1 - x0 + 1) * s, height: (y1 - y0 + 1) * s)
            }

            let look = RoomLook.of(time, weather)
            // Only the visible window glass (not the frame, curtains or string lights).
            var glass = Path()
            for (y, x0, x1) in RoomLook.glassSpans {
                glass.addRect(rect(Double(x0), Double(y), Double(x1), Double(y)))
            }

            // ---- clouds drifting across the window (behind the trees) ----
            ctx.drawLayer { w in
                w.clip(to: glass)
                let ymax = weather == .clear ? 34.0 : 44.0
                for i in 0..<look.clouds {
                    let cy = 18 + (rnd(i, 21) * (ymax - 18)).rounded(.down)
                    let sp = (1.2 + rnd(i, 22) * 1.8) * (weather == .storm ? 2.2 : 1)
                    let cx = 42 + (rnd(i, 23) * 87 + t * sp).truncatingRemainder(dividingBy: 87).rounded(.down)
                    for px in Self.cloudShapes[i % Self.cloudShapes.count] {
                        let x = cx + px.dx, y = cy + px.dy
                        guard y < Self.treeLine(Int(x)) else { continue }
                        let c = px.body ? look.cloud : look.cloudShadow
                        w.fill(Path(CGRect(x: x * s, y: y * s, width: s, height: s)),
                               with: .color(Color(red: c.0 / 255, green: c.1 / 255, blue: c.2 / 255)))
                    }
                }
            }

            // ---- inside the window (clipped to the glass) ----
            ctx.drawLayer { w in
                w.clip(to: glass)
                func wdot(_ x: Double, _ y: Double, _ c: (Double, Double, Double), _ a: Double) {
                    w.fill(Path(CGRect(x: x.rounded(.down) * s, y: y.rounded(.down) * s, width: s, height: s)),
                           with: .color(Color(red: c.0 / 255, green: c.1 / 255, blue: c.2 / 255).opacity(min(a, 1))))
                }
                if weather == .rain || weather == .storm {
                    let storm = weather == .storm
                    let n = storm ? 60 : 40, speed = storm ? 110.0 : 80.0
                    for i in 0..<n {
                        let x = 62 + (rnd(i, 1) * 47).rounded(.down)
                        let y = 14 + (t * speed * (0.8 + 0.4 * rnd(i, 2)) + rnd(i, 3) * 60).truncatingRemainder(dividingBy: 62).rounded(.down)
                        for k in 0..<3 { wdot(x - (storm ? Double(k / 2) : 0), y + Double(k), (190, 205, 235), 0.75) }
                    }
                }
                if weather == .snow {
                    for i in 0..<36 {
                        let sp = 7 + 7 * rnd(i, 4)
                        let y = 14 + (t * sp + rnd(i, 5) * 62).truncatingRemainder(dividingBy: 62)
                        let x = 62 + rnd(i, 6) * 47 + sin(t * 1.3 + Double(i)) * 2
                        wdot(x, y, (255, 255, 255), 0.95)
                    }
                }
                if time == .night && weather == .clear {
                    for i in 0..<10 {
                        let a = 0.5 + 0.5 * sin(t * (1.5 + rnd(i, 9) * 2) + Double(i) * 2)
                        wdot(65 + (rnd(i, 7) * 41).rounded(.down), 20 + (rnd(i, 8) * 26).rounded(.down), (255, 255, 230), a)
                    }
                }
                if lightning {
                    let white = Color(red: 245 / 255, green: 245 / 255, blue: 1).opacity(0.78)
                    for r in [rect(62, 15, 84, 47), rect(87, 15, 108, 47), rect(62, 50, 84, 65), rect(87, 50, 108, 65)] {
                        w.fill(Path(r), with: .color(white))   // leaves the window frame visible
                    }
                }
            }

            // ---- dust motes in the sunbeam ----
            if weather == .clear && time != .night {
                for i in 0..<14 {
                    let bx = 66 + rnd(i, 10) * 56, by = 60 + rnd(i, 11) * 80
                    let y = by - (t * 2.5 + rnd(i, 12) * 30).truncatingRemainder(dividingBy: 30)
                    let x = bx + sin(t * 0.4 + Double(i)) * 3
                    dot(x, y, (255, 245, 210), 0.25 + 0.35 * (0.5 + 0.5 * sin(t * 2 + Double(i))))
                }
            }

            // ---- string lights twinkle ----
            if lightsOn {
                let colors: [(Double, Double, Double)] = [(255, 200, 120), (255, 170, 140), (255, 226, 150)]
                for (i, b) in Self.bulbs.enumerated() {
                    let a = 0.5 + 0.5 * sin(t * 2.2 + Double(i) * 1.7)
                    for (dx, dy) in [(-1.0, 0.0), (1, 0), (0, -1), (0, 2), (-1, 1), (1, 1)] {
                        dot(b.x + dx, b.y + dy, colors[i % 3], 0.35 * a)
                    }
                    dot(b.x, b.y, (255, 250, 230), 0.6 * a); dot(b.x, b.y + 1, (255, 250, 230), 0.6 * a)
                }
            }

            // ---- candle flicker (night) ----
            if time == .night {
                let f = 0.5 + 0.25 * sin(t * 13) + 0.25 * sin(t * 7.3 + 1)
                for dx in -7...7 {
                    for dy in -7...7 {
                        let r = hypot(Double(dx), Double(dy))
                        if r < 7 { dot(156 + Double(dx), 70 + Double(dy), (255, 190, 110), 0.10 * f * (1 - r / 7)) }
                    }
                }
                dot(156, 71, (255, 180, 80), 1); dot(156, 70, (255, 235, 170), 1)
                if f > 0.55 { dot(156 + (sin(t * 5) > 0.6 ? 1 : 0), 69, (255, 220, 140), 0.9) }
            }

            // ---- record player: spinning platter + floating notes ----
            if musicOn {
                let ang = t * 2 * .pi * 0.75
                dot((129 + 5 * cos(ang)).rounded(), (72 + 1.4 * sin(ang)).rounded(), (120, 110, 130), 1)
                let colors: [(Double, Double, Double)] = [(140, 220, 210), (250, 210, 120), (240, 150, 170)]
                for i in 0..<4 {
                    let p = (t / 3.2 + Double(i) / 4).truncatingRemainder(dividingBy: 1)
                    let side: Double = i % 2 == 1 ? -1 : 1
                    let x = (128 + side * p * 9 + sin(p * 9 + Double(i)) * 1.5).rounded()
                    let y = (66 - p * 26).rounded()
                    let a = min(1, p / 0.12) * min(1, (1 - p) / 0.35)
                    // ♪ shape: stem, head, flag
                    for (px, py) in [(0.0, 0.0), (0, 1), (0, 2), (0, 3), (-1, 3), (-2, 3), (1, 0), (2, 1)] {
                        dot(x + px, y + py, colors[i % 3], a)
                    }
                }
            }

            // ---- steam from the mug on the window seat ----
            if time != .night {
                for i in 0..<3 {
                    let p = (t / 2.4 + Double(i) / 3).truncatingRemainder(dividingBy: 1)
                    dot((100 + sin(p * 7 + Double(i) * 2) * 1.5).rounded(), (71 - p * 10).rounded(), (240, 240, 250), 0.55 * (1 - p))
                }
            }

            func tinted(_ c: (Double, Double, Double), _ k: (Double, Double, Double)) -> (Double, Double, Double) {
                (min(255, c.0 * k.0), min(255, c.1 * k.1), min(255, c.2 * k.2))
            }

            // ---- hanging plant swaying (top-right) ----
            for i in 0..<18 {
                let x0 = 238 + (rnd(i, 30) * 17).rounded(.down)
                let len = 6 + Int(rnd(i, 31) * 21)
                for yi in 24..<(24 + len) {
                    let y = Double(yi)
                    let sway = (sin(t * 1.1 + Double(i) * 0.5) * 1.6 * (y - 24) / 26).rounded()
                    let green: (Double, Double, Double) = (yi + i) % 2 == 1 ? (84, 156, 92) : (56, 116, 70)
                    dot(x0 + Double((yi / 4) % 2) + sway, y, tinted(green, look.plantTint), 1)
                }
            }

            // ---- fish tank on the shelf above the bed ----
            let fishColors: [(Double, Double, Double)] = [(250, 140, 60), (250, 210, 90), (110, 170, 240)]
            for i in 0..<3 {
                let sp = 3 + rnd(i, 40) * 3, span = 15.0
                let p = (t * sp / span + rnd(i, 41) * 2).truncatingRemainder(dividingBy: 2)   // there and back
                let right = p < 1
                let x = 193 + ((right ? p : 2 - p) * span).rounded(.down)
                let y = 45 + (rnd(i, 42) * 5).rounded(.down) + sin(t * 2 + Double(i)).rounded()
                let c = tinted(fishColors[i], look.shelfTint)
                for dx in 0..<3 { dot(x + Double(dx), y, c, 1) }
                dot(x + (right ? 2 : 0), y - 1, c, 1)                                        // fin
                dot(x + (right ? -1 : 3), y + (Int(t * 4) % 2 == 1 ? 1 : -1), c, 1)          // tail wiggle
                dot(x + (right ? 2 : 0), y, (30, 30, 40), 1)                                 // eye
            }
            for i in 0..<3 {
                let p = (t / 2.2 + Double(i) / 3).truncatingRemainder(dividingBy: 1)
                dot(206 + (sin(p * 12) > 0 ? 1 : 0), (50 - p * 7).rounded(.down), (220, 240, 250), 0.8 * (1 - p * 0.5))
            }

            // ---- digital clock with blinking colon (your phone's time) ----
            let now = Calendar.current.dateComponents([.hour, .minute, .second], from: Date())
            let hh = now.hour ?? 0, mm = now.minute ?? 0
            let digits = [hh / 10, hh % 10, mm / 10, mm % 10]
            let xs: [Double] = [216, 220, 226, 230]
            let lcd: (Double, Double, Double) = (120, 240, 160)
            for (k, n) in digits.enumerated() where !(k == 0 && n == 0) {   // no leading zero
                for (r, row) in Self.fontRows[n].enumerated() {
                    for (cIdx, bit) in row.enumerated() where bit == "1" {
                        dot(xs[k] + Double(cIdx), 47 + Double(r), lcd, 1)
                    }
                }
            }
            if (now.second ?? 0) % 2 == 0 { dot(224, 48, lcd, 1); dot(224, 50, lcd, 1) }

            // ---- lightning brightens the whole room for a moment ----
            if lightning {
                ctx.fill(Path(CGRect(origin: .zero, size: size)),
                         with: .color(Color(red: 220 / 255, green: 225 / 255, blue: 1).opacity(40.0 / 255)))
            }
        }
        .allowsHitTesting(false)
    }

    private var lightsOn: Bool {
        time == .night || time == .sunset || ((weather == .storm || weather == .rain) && time != .day)
    }
    private var musicOn: Bool { time != .night && !palAsleep }   // no music while the pal sleeps
    private var lightning: Bool {
        guard weather == .storm else { return false }
        let ph = t.truncatingRemainder(dividingBy: 7)
        return ph < 0.12 || (ph > 0.25 && ph < 0.33)
    }

    /// String-light bulb positions (matches the room art).
    static let bulbs: [CGPoint] = {
        var out: [CGPoint] = []
        for x in stride(from: 44, to: 256, by: 10) {
            out.append(CGPoint(x: Double(x), y: Double(14 + 3 + Int(5 * abs(sin(Double(x - 44) / 42 * .pi))) + 1)))
        }
        for x in stride(from: 4, to: 44, by: 10) {
            out.append(CGPoint(x: Double(x), y: Double(Int(14.0 * Double(x) / 44) + 3 + Int(3 * abs(sin(Double(x) / 22 * .pi))) + 1)))
        }
        return out
    }()

    /// 3x5 pixel digits for the clock.
    static let fontRows: [[String]] = [
        ["111", "101", "101", "101", "111"], ["010", "110", "010", "010", "111"],
        ["111", "001", "111", "100", "111"], ["111", "001", "111", "001", "111"],
        ["101", "101", "111", "001", "001"], ["111", "100", "111", "001", "111"],
        ["111", "100", "111", "101", "111"], ["111", "001", "010", "010", "010"],
        ["111", "101", "111", "101", "111"], ["111", "101", "111", "001", "111"],
    ]

    /// Where the trees start in the window view, for each x (clouds stay behind them).
    static func treeLine(_ x: Int) -> Double {
        Double(Int(60 + 5 * sin(Double(x) / 3) + 3 * sin(Double(x) / 1.3)))
    }

    struct CloudPixel { let dx: Double; let dy: Double; let body: Bool }

    /// Pixel clouds, each built from 4 overlapping ellipses (same recipe as the preview).
    static let cloudShapes: [[CloudPixel]] = (0..<12).map { i in
        var cells: [String: Bool] = [:]   // "dx,dy" -> isBody
        for k in 0..<4 {
            let r = 4 + Double(Int(PalRoomAmbience.hash01(i, 20 + Double(k)) * 4)), ry = r / 1.4, ox = Double(k * 5 - 8)
            for dy in -7...7 {
                for dx in -16..<16 {
                    let fx = Double(dx), fy = Double(dy)
                    guard pow((fx - ox) / r, 2) + pow(fy / ry, 2) <= 1 else { continue }
                    let inner = pow((fx - ox) / (r - 1), 2) + pow((fy + 1.5) / (ry - 0.5), 2) <= 1
                    let key = "\(dx),\(dy)"
                    if inner { cells[key] = true } else if cells[key] != true { cells[key] = false }
                }
            }
        }
        return cells.map { key, body in
            let parts = key.split(separator: ",").compactMap { Double($0) }
            return CloudPixel(dx: parts[0], dy: parts[1], body: body)
        }
    }

    /// Stable pseudo-random number in 0..<1 for particle `i`.
    static func hash01(_ i: Int, _ salt: Double) -> Double {
        let v = sin(Double(i) * 12.9898 + salt * 78.233) * 43758.5453
        return v - v.rounded(.down)
    }
    private func rnd(_ i: Int, _ salt: Double) -> Double { PalRoomAmbience.hash01(i, salt) }
}
