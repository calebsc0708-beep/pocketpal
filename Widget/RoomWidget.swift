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
    case activities, hop

    static var typeDisplayRepresentation: TypeDisplayRepresentation = "Motion"
    static var caseDisplayRepresentations: [RoomMotion: DisplayRepresentation] = [
        .activities: "Activities (new one every 5 min)",
        .hop: "Hop around (once a second)",
    ]
}

struct RoomWidgetIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "PokePal Room"
    static var description = IntentDescription("Your pal in its room, matching your time of day and weather.")

    @Parameter(title: "Pal", default: .eevee) var pal: RoomPal
    @Parameter(title: "Motion", default: .activities) var motion: RoomMotion
}

// MARK: - Timeline

struct RoomEntry: TimelineEntry {
    let date: Date
    let time: RoomTime
    let weather: RoomWeather
    let pal: RoomPal
    let motion: RoomMotion
    let slot: Int          // which 5-minute slot (picks the activity)
    let timerStart: Date   // drives the 1-frame-per-second fonts
}

struct RoomProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> RoomEntry {
        RoomEntry(date: Date(), time: .day, weather: .clear, pal: .eevee, motion: .activities, slot: 0, timerStart: Date())
    }

    func snapshot(for configuration: RoomWidgetIntent, in context: Context) async -> RoomEntry {
        let now = Date()
        return RoomEntry(date: now, time: WeatherSync.clockTime(now, sunrise: nil, sunset: nil), weather: .clear,
                         pal: configuration.pal, motion: configuration.motion, slot: Self.slot(now), timerStart: now)
    }

    func timeline(for configuration: RoomWidgetIntent, in context: Context) async -> Timeline<RoomEntry> {
        // Weather for your last known location (the app asks for location permission).
        var snap: WeatherSync.Snapshot? = nil
        if let loc = CLLocationManager().location {
            snap = await WeatherSync.fetchSnapshot(lat: loc.coordinate.latitude, lon: loc.coordinate.longitude)
        }
        let now = Date()
        // A new picture every minute for the next 2 hours, so the wall clock stays right.
        // Planned entries don't use up the widget's refresh budget; iOS asks again at the end.
        let firstMinute = Calendar.current.dateInterval(of: .minute, for: now)?.end ?? now
        let dates = [now] + (0..<120).map { firstMinute.addingTimeInterval(Double($0) * 60) }
        let entries = dates.map { date -> RoomEntry in
            return RoomEntry(date: date,
                             time: WeatherSync.clockTime(date, sunrise: snap?.sunrise, sunset: snap?.sunset),
                             weather: snap?.weather ?? .clear,
                             pal: configuration.pal, motion: configuration.motion,
                             slot: Self.slot(date), timerStart: now)
        }
        return Timeline(entries: entries, policy: .atEnd)
    }

    /// 5-minute slots on the clock, so the activity changes at :00, :05, :10...
    static func slot(_ date: Date) -> Int { Int(date.timeIntervalSinceReferenceDate / 300) }
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
                            t: entry.date.timeIntervalSinceReferenceDate, palAsleep: night,
                            clock: entry.date)
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
                activityPal(species, PalActivity.forSlot(entry.slot), scale: s)
            }
        case .activities:
            activityPal(species, PalActivity.forSlot(entry.slot), scale: s)
        }
    }

    /// The pal doing an activity, animating once a second (font trick) or as a still frame if fonts aren't available.
    @ViewBuilder
    private func activityPal(_ species: PalSpecies, _ act: PalActivity, scale s: CGFloat) -> some View {
        let side = act.size * s
        let font = "PokePal-\(species.rawValue)-\(act.back ? "back" : "idle")"
        let x = act.perch.x * s
        let y = act.perch.y * s - side / 2
        if Sprites.hasFont(font, size: side) {
            Text(entry.timerStart, style: .timer)
                .font(.custom(font, fixedSize: side))
                .lineLimit(1)
                .frame(width: side, height: side)
                .scaleEffect(x: act.flip ? -1 : 1, y: 1)
                .position(x: x, y: y)
        } else {
            Image((act.back ? species.back : species.front).frames[0].image)
                .resizable()
                .interpolation(.none)
                .frame(width: side, height: side)
                .scaleEffect(x: act.flip ? -1 : 1, y: 1)
                .position(x: x, y: y)
        }
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
