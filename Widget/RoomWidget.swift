import WidgetKit
import SwiftUI
import AppIntents
import CoreLocation

// MARK: - Configuration (long-press the widget → Edit Widget)

enum RoomPal: String, AppEnum {
    case eevee, pikachu, minccino

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Pal"
    static var caseDisplayRepresentations: [RoomPal: DisplayRepresentation] = [
        .eevee: "Eevee", .pikachu: "Pikachu", .minccino: "Minccino",
    ]
    var species: PalSpecies { PalSpecies(rawValue: rawValue) ?? .eevee }
}

enum RoomMotion: String, AppEnum {
    case still, idle, hop

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Motion"
    static var caseDisplayRepresentations: [RoomMotion: DisplayRepresentation] = [
        .still: "Still (new spot each refresh)",
        .idle: "Idle (animates once a second)",
        .hop: "Hop around (once a second)",
    ]
}

struct RoomWidgetIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "PokePal Room"
    static var description = IntentDescription("Your pal in its room, matching your time of day and weather.")

    @Parameter(title: "Pal", default: .eevee) var pal: RoomPal
    @Parameter(title: "Motion", default: .idle) var motion: RoomMotion
}

// MARK: - Timeline

struct RoomEntry: TimelineEntry {
    let date: Date
    let time: RoomTime
    let weather: RoomWeather
    let pal: RoomPal
    let motion: RoomMotion
    let spot: Int          // which of the 10 floor spots (Still mode)
    let timerStart: Date   // drives the 1-frame-per-second fonts
}

struct RoomProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> RoomEntry {
        RoomEntry(date: Date(), time: .day, weather: .clear, pal: .eevee, motion: .still, spot: 0, timerStart: Date())
    }

    func snapshot(for configuration: RoomWidgetIntent, in context: Context) async -> RoomEntry {
        let now = Date()
        return RoomEntry(date: now, time: WeatherSync.clockTime(now, sunrise: nil, sunset: nil), weather: .clear,
                         pal: configuration.pal, motion: configuration.motion, spot: 0, timerStart: now)
    }

    func timeline(for configuration: RoomWidgetIntent, in context: Context) async -> Timeline<RoomEntry> {
        // Weather for your last known location (the app asks for location permission).
        var snap: WeatherSync.Snapshot? = nil
        if let loc = CLLocationManager().location {
            snap = await WeatherSync.fetchSnapshot(lat: loc.coordinate.latitude, lon: loc.coordinate.longitude)
        }
        let now = Date()
        // A new picture every 15 minutes for the next 2 hours, then iOS asks again.
        let entries = (0..<8).map { i -> RoomEntry in
            let date = now.addingTimeInterval(Double(i) * 15 * 60)
            return RoomEntry(date: date,
                             time: WeatherSync.clockTime(date, sunrise: snap?.sunrise, sunset: snap?.sunset),
                             weather: snap?.weather ?? .clear,
                             pal: configuration.pal, motion: configuration.motion,
                             spot: Int.random(in: 0..<10), timerStart: now)
        }
        return Timeline(entries: entries, policy: .atEnd)
    }
}

// MARK: - View

/// Shared geometry with tools/build_room_fonts.py.
enum RoomWidgetGeometry {
    static let hopOrigin = CGPoint(x: 20, y: 0)   // top-left of the hop font's picture, room px
    static let hopSide: CGFloat = 160             // it covers 160x160 room px
    static let palSize: CGFloat = 34              // pal height in room px
    /// 10 spots in a loop around the rug (feet position, room px).
    static func spot(_ k: Int) -> CGPoint {
        let a = 2 * Double.pi * Double(k) / 10
        return CGPoint(x: 102 + 40 * cos(a), y: 128 + 12 * sin(a))
    }
}

struct RoomWidgetView: View {
    let entry: RoomEntry
    @Environment(\.widgetFamily) private var family

    var body: some View {
        GeometryReader { geo in
            // Fill the widget with the room, keeping the window, rug and bed in view.
            let s = max(geo.size.width / 256, geo.size.height / 160)
            // large: the rug by day, the bed at night (so the sleeping pal is in view)
            let focusX: CGFloat = family == .systemLarge ? (entry.time == .night ? 176 : 112) : 128
            let ox = min(0, max(geo.size.width - 256 * s, geo.size.width / 2 - focusX * s))
            let oy = min(0, max(geo.size.height - 160 * s, geo.size.height / 2 - 100 * s))
            room(scale: s)
                .frame(width: 256 * s, height: 160 * s)
                .offset(x: ox, y: oy)
        }
        .clipped()
        .containerBackground(for: .widget) { Color.black }
    }

    @ViewBuilder
    private func room(scale s: CGFloat) -> some View {
        let night = entry.time == .night
        ZStack(alignment: .topLeading) {
            Image(entry.time.roomImage(entry.weather))
                .resizable()
                .interpolation(.none)
                .frame(width: 256 * s, height: 160 * s)

            PalRoomAmbience(time: entry.time, weather: entry.weather,
                            t: entry.date.timeIntervalSinceReferenceDate, palAsleep: night)
                .frame(width: 256 * s, height: 160 * s)

            if night {
                // asleep under the covers, whatever the motion setting
                PalSleepLayer(time: entry.time, weather: entry.weather, t: 0.5, scale: s)
                    .frame(width: 256 * s, height: 160 * s)
            } else {
                pal(scale: s)
            }
        }
    }

    @ViewBuilder
    private func pal(scale s: CGFloat) -> some View {
        let species = entry.pal.species
        switch entry.motion {
        case .hop:
            let font = "PokePal-\(species.rawValue)-hop"
            let side = RoomWidgetGeometry.hopSide * s
            if Sprites.hasFont(font, size: side) {
                Text(entry.timerStart, style: .timer)
                    .font(.custom(font, fixedSize: side))
                    .lineLimit(1)
                    .frame(width: side, height: side)
                    .position(x: (RoomWidgetGeometry.hopOrigin.x + RoomWidgetGeometry.hopSide / 2) * s,
                              y: (RoomWidgetGeometry.hopOrigin.y + RoomWidgetGeometry.hopSide / 2) * s)
            } else {
                stillPal(species, spot: entry.spot, scale: s)
            }
        case .idle:
            let font = "PokePal-\(species.rawValue)-idle"
            let side = RoomWidgetGeometry.palSize * s
            let feet = RoomWidgetGeometry.spot(2)                  // front of the rug
            if Sprites.hasFont(font, size: side) {
                Text(entry.timerStart, style: .timer)
                    .font(.custom(font, fixedSize: side))
                    .lineLimit(1)
                    .frame(width: side, height: side)
                    .position(x: feet.x * s, y: feet.y * s - side / 2)
            } else {
                stillPal(species, spot: 2, scale: s)
            }
        case .still:
            stillPal(species, spot: entry.spot, scale: s)
        }
    }

    /// One frame of the pal at a floor spot, facing a random-but-stable way.
    private func stillPal(_ species: PalSpecies, spot: Int, scale s: CGFloat) -> some View {
        let feet = RoomWidgetGeometry.spot(spot)
        let side = RoomWidgetGeometry.palSize * s
        let frames = species.front.frames
        let frame = frames[(spot * 7) % frames.count].image
        let faceRight = spot % 2 == 0
        return Image(frame)
            .resizable()
            .interpolation(.none)
            .frame(width: side, height: side)
            .scaleEffect(x: faceRight ? -1 : 1, y: 1)            // front art faces left
            .position(x: feet.x * s, y: feet.y * s - side / 2)
    }
}

// MARK: - Widget

struct RoomWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: "PokePalRoom", intent: RoomWidgetIntent.self, provider: RoomProvider()) { entry in
            RoomWidgetView(entry: entry)
        }
        .configurationDisplayName("PokePal Room")
        .description("Your pal in its cozy room, matching your time of day and weather.")
        .supportedFamilies([.systemMedium, .systemLarge])
        .contentMarginsDisabled()
    }
}
