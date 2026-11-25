import SwiftUI

/// Holiday decorations that appear in the room on their own, by date.
/// Each is a room-sized overlay (drawn at room resolution); some have a glowing part for the evening.
enum RoomDecorations {
    /// Holidays in the order they're drawn (later ones on top).
    static func holidays(for date: Date) -> [String] {
        let c = Calendar.current.dateComponents([.month, .day], from: date)
        let month = c.month ?? 1, day = c.day ?? 1
        var out: [String] = []
        if month == 10 { out.append("halloween") }                        // pumpkins, bats, ghost
        if month == 11 { out.append("autumn") }                           // Thanksgiving: leaves, pie
        if month == 12 { out.append("christmas") }                        // tree, wreath, stockings
        if (month == 12 && day == 31) || (month == 1 && day == 1) { out.append("newyear") }
        if month == 2 && day <= 14 { out.append("valentine") }           // hearts, roses
        return out
    }

    /// Asset names of the still decorations for `date`.
    static func names(for date: Date) -> [String] {
        var out = holidays(for: date).map { "deco_" + $0 }
        let month = Calendar.current.component(.month, from: date)
        if month == 12 || month == 1 || month == 2 { out.append("deco_frost") }   // frosty window
        return out
    }

    static let withGlow: Set<String> = ["deco_halloween", "deco_autumn", "deco_christmas", "deco_newyear", "deco_valentine"]

    typealias RGB = (Double, Double, Double)
    /// String-light colors for a holiday (must match tools/build_fx_fonts.py).
    static let palettes: [String: [RGB]] = [
        "halloween": [(255, 150, 40), (170, 90, 230), (120, 230, 90)],
        "autumn": [(255, 190, 90), (240, 130, 60), (255, 220, 130)],
        "christmas": [(255, 70, 70), (80, 220, 110), (255, 210, 90)],
        "newyear": [(255, 215, 100), (220, 220, 255), (255, 240, 180)],
        "valentine": [(255, 110, 150), (255, 180, 200), (240, 60, 90)],
    ]

    /// The holiday whose lights are up (the latest one wins), or nil on a normal day.
    static func lightHoliday(for date: Date) -> String? { holidays(for: date).last }

    struct Balloon {
        let image: String
        let x: CGFloat, y: CGFloat, w: CGFloat, h: CGFloat
        let phase: Double
    }

    /// Balloons that bob around (by the bed), for holidays that have them.
    static func balloons(for date: Date) -> (holiday: String, items: [Balloon])? {
        let hols = holidays(for: date)
        if hols.contains("newyear") { return ("newyear", newYearBalloons) }
        if hols.contains("valentine") { return ("valentine", valentineBalloons) }
        return nil
    }

    static let newYearBalloons: [Balloon] = [
            Balloon(image: "balloon_newyear_0", x: 170, y: 64, w: 15, h: 39, phase: 0.0),
            Balloon(image: "balloon_newyear_1", x: 179, y: 58, w: 12, h: 39, phase: 2.1),
            Balloon(image: "balloon_newyear_2", x: 186, y: 66, w: 15, h: 39, phase: 4.2)
    ]
    static let valentineBalloons: [Balloon] = [
            Balloon(image: "balloon_valentine_0", x: 171, y: 60, w: 12, h: 39, phase: 0.0),
            Balloon(image: "balloon_valentine_1", x: 181, y: 54, w: 12, h: 39, phase: 2.1),
            Balloon(image: "balloon_valentine_2", x: 190, y: 62, w: 12, h: 39, phase: 4.2)
    ]
}

/// Draws the decorations for a date, lit like the room. Place it over the room, under the pal.
/// `t` animates the balloons in the app; the widget passes nil and uses its once-a-second balloon font instead.
struct RoomDecorationLayer: View {
    let date: Date
    let time: RoomTime
    let weather: RoomWeather
    var t: Double? = nil

    var body: some View {
        GeometryReader { geo in
            let s: CGFloat = geo.size.width / 256
            let tint: Color = RoomLook.of(time, weather).palColor
            let glowing: Bool = time != .day       // jack-o'-lanterns, tree lights etc. glow from sunset to sunrise
            ZStack(alignment: .topLeading) {
                ForEach(RoomDecorations.names(for: date), id: \.self) { name in
                    Image(name)
                        .resizable()
                        .interpolation(.none)
                        .colorMultiply(tint)
                        .frame(width: geo.size.width, height: geo.size.height)
                    if glowing && RoomDecorations.withGlow.contains(name) {
                        Image(name + "_glow")
                            .resizable()
                            .interpolation(.none)
                            .frame(width: geo.size.width, height: geo.size.height)
                    }
                }
                if let t, let set = RoomDecorations.balloons(for: date) {
                    ForEach(set.items, id: \.image) { b in
                        let dy: CGFloat = CGFloat(sin(t * 1.25 + b.phase)) * 1.2
                        let dx: CGFloat = CGFloat(sin(t * 0.63 + b.phase)) * 1.0
                        Image(b.image)
                            .resizable()
                            .interpolation(.none)
                            .colorMultiply(tint)
                            .frame(width: b.w * s, height: b.h * s)
                            .position(x: (b.x + b.w / 2 + dx) * s, y: (b.y + b.h / 2 + dy) * s)
                    }
                }
            }
        }
        .allowsHitTesting(false)
    }
}
