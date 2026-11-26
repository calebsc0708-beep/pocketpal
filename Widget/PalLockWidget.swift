import WidgetKit
import SwiftUI
import AppIntents
import CoreLocation

/// Lock Screen widget: your pal next to the clock, with the weather in the wider sizes.
struct PalLockIntent: WidgetConfigurationIntent {
    static var title: LocalizedStringResource = "PokePal"
    static var description = IntentDescription("Your pal on the Lock Screen.")

    /// Leave empty to show the pal you picked in the app.
    @Parameter(title: "Pal (empty = same as app)") var palOverride: RoomPal?
}

struct PalLockEntry: TimelineEntry {
    let date: Date
    let pal: RoomPal
    let time: RoomTime
    let weather: RoomWeather?
    let temperature: Int?
}

struct PalLockProvider: AppIntentTimelineProvider {
    func placeholder(in context: Context) -> PalLockEntry {
        PalLockEntry(date: Date(), pal: RoomProvider.pal(nil), time: .day, weather: .clear, temperature: 68)
    }

    func snapshot(for configuration: PalLockIntent, in context: Context) async -> PalLockEntry {
        PalLockEntry(date: Date(), pal: RoomProvider.pal(configuration.palOverride),
                     time: WeatherSync.clockTime(Date(), sunrise: nil, sunset: nil), weather: nil, temperature: nil)
    }

    func timeline(for configuration: PalLockIntent, in context: Context) async -> Timeline<PalLockEntry> {
        var snap: WeatherSync.Snapshot? = nil
        if let loc = CLLocationManager().location {
            // use the weather the room widget/app already fetched when it's under an hour old, so this timeline is
            // ready right away (a slow fetch can leave iOS showing the old timeline, with the old pal)
            snap = await WeatherSync.sharedSnapshot(lat: loc.coordinate.latitude, lon: loc.coordinate.longitude, maxAge: 60 * 60)
        }
        let now = Date()
        // every 15 minutes for 2 hours (day/night can change), then ask again
        let entries = (0..<8).map { i -> PalLockEntry in
            let date = now.addingTimeInterval(Double(i) * 15 * 60)
            return PalLockEntry(date: date, pal: RoomProvider.pal(configuration.palOverride),
                                time: WeatherSync.clockTime(date, sunrise: snap?.sunrise, sunset: snap?.sunset),
                                weather: snap?.weather,
                                temperature: snap.map { Int($0.temperature.rounded()) })
        }
        return Timeline(entries: entries, policy: .atEnd)
    }
}

struct PalLockView: View {
    let entry: PalLockEntry
    @Environment(\.widgetFamily) private var family

    private var species: PalSpecies { entry.pal.species }
    private var asleep: Bool { entry.time == .night }
    private var weatherText: String {
        guard let w = entry.weather else { return "" }
        if let t = entry.temperature { return "\(w.label) \(t)°" }
        return w.label
    }

    var body: some View {
        switch family {
        case .accessoryCircular:
            ZStack {
                AccessoryWidgetBackground()
                palImage.padding(4)
                if asleep {
                    Text("z").font(.system(size: 12, weight: .heavy)).offset(x: 14, y: -14)
                }
            }
            .containerBackground(for: .widget) { Color.clear }
        case .accessoryRectangular:
            HStack(spacing: 6) {
                palImage.frame(width: 48, height: 48)
                VStack(alignment: .leading, spacing: 1) {
                    Text(species.displayName).font(.headline).widgetAccentable()
                    Text(asleep ? "Sleeping" : PalActivity.forSlot(Int(entry.date.timeIntervalSinceReferenceDate / 300)).name)
                        .font(.caption).lineLimit(1)
                    if !weatherText.isEmpty { Text(weatherText).font(.caption).lineLimit(1) }
                }
                Spacer(minLength: 0)
            }
            .containerBackground(for: .widget) { Color.clear }
        default:   // inline, next to the date
            Text(weatherText.isEmpty ? species.displayName : "\(species.displayName) · \(weatherText)")
                .containerBackground(for: .widget) { Color.clear }
        }
    }

    private var palImage: some View {
        Image(species.front.frames[0].image)
            .resizable()
            .interpolation(.none)
            .scaledToFit()
    }
}

struct PalLockWidget: Widget {
    var body: some WidgetConfiguration {
        AppIntentConfiguration(kind: "PokePalLock", intent: PalLockIntent.self, provider: PalLockProvider()) { entry in
            PalLockView(entry: entry)
        }
        .configurationDisplayName("PokePal")
        .description("Your pal on the Lock Screen, with the weather.")
        .supportedFamilies([.accessoryCircular, .accessoryRectangular, .accessoryInline])
    }
}
