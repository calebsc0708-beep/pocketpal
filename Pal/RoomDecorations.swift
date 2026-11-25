import SwiftUI

/// Holiday decorations that appear in the room on their own, by date.
/// Each is a room-sized overlay (drawn at room resolution); some have a glowing part for the evening.
enum RoomDecorations {
    /// Asset names for the decorations on `date`.
    static func names(for date: Date) -> [String] {
        let c = Calendar.current.dateComponents([.month, .day], from: date)
        let month = c.month ?? 1, day = c.day ?? 1
        var out: [String] = []
        if month == 10 { out.append("deco_halloween") }                 // pumpkins and bats
        if month == 12 { out.append("deco_christmas") }                 // tree, gifts, stockings
        if month == 2 && day <= 14 { out.append("deco_valentine") }    // heart garland
        if month == 12 || month == 1 || month == 2 { out.append("deco_frost") }   // frosty window
        return out
    }

    static let withGlow: Set<String> = ["deco_halloween", "deco_christmas"]
}

/// Draws the decorations for a date, lit like the room. Place it over the room, under the pal.
struct RoomDecorationLayer: View {
    let date: Date
    let time: RoomTime
    let weather: RoomWeather

    var body: some View {
        let tint = RoomLook.of(time, weather).palColor
        let glowing = time != .day          // jack-o'-lanterns and tree lights glow from sunset to sunrise
        ZStack {
            ForEach(RoomDecorations.names(for: date), id: \.self) { name in
                Image(name)
                    .resizable()
                    .interpolation(.none)
                    .colorMultiply(tint)
                if glowing && RoomDecorations.withGlow.contains(name) {
                    Image(name + "_glow")
                        .resizable()
                        .interpolation(.none)
                }
            }
        }
        .allowsHitTesting(false)
    }
}
