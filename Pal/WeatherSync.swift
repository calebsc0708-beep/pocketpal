import Foundation
import CoreLocation

/// Keeps the room in step with your phone: time of day from your local sunrise/sunset,
/// weather from Open-Meteo (free, no API key, works on a sideloaded app).
@MainActor
final class WeatherSync: NSObject, ObservableObject, CLLocationManagerDelegate {
    static let shared = WeatherSync()

    @Published private(set) var time: RoomTime = WeatherSync.clockTime(Date(), sunrise: nil, sunset: nil)
    @Published private(set) var weather: RoomWeather = .clear
    @Published private(set) var summary = ""          // e.g. "Cloudy 46°  sunset 4:52"

    private let manager = CLLocationManager()
    private var sunrise: Date?
    private var sunset: Date?
    private var lastFetch: Date?

    override init() {
        super.init()
        manager.delegate = self
        manager.desiredAccuracy = kCLLocationAccuracyKilometer
    }

    /// Call when the app opens or comes back to the foreground.
    func start() {
        refreshTime()
        if let lastFetch, Date().timeIntervalSince(lastFetch) < 20 * 60 { return }   // every 20 min at most
        switch manager.authorizationStatus {
        case .notDetermined: manager.requestWhenInUseAuthorization()
        case .authorizedWhenInUse, .authorizedAlways: manager.requestLocation()
        default: break   // no location: the room still follows the clock
        }
    }

    func refreshTime() {
        let t = Self.clockTime(Date(), sunrise: sunrise, sunset: sunset)
        if t != time { time = t }
    }

    // MARK: CLLocationManagerDelegate

    nonisolated func locationManagerDidChangeAuthorization(_ manager: CLLocationManager) {
        let status = manager.authorizationStatus
        Task { @MainActor in
            if status == .authorizedWhenInUse || status == .authorizedAlways { self.manager.requestLocation() }
        }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
        guard let c = locations.last?.coordinate else { return }
        let lat = c.latitude, lon = c.longitude
        Task { @MainActor in await self.fetch(lat: lat, lon: lon) }
    }

    nonisolated func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {}

    // MARK: Open-Meteo

    struct Snapshot {
        let weather: RoomWeather
        let temperature: Double
        let sunrise: Date?
        let sunset: Date?
    }

    private struct Response: Decodable {
        struct Current: Decodable { let temperature_2m: Double; let weather_code: Int }
        struct Daily: Decodable { let sunrise: [String]; let sunset: [String] }
        let utc_offset_seconds: Int
        let current: Current
        let daily: Daily
    }

    /// Current weather + today's sunrise/sunset for a spot. Used by the app and the widget.
    nonisolated static func fetchSnapshot(lat: Double, lon: Double) async -> Snapshot? {
        var parts = URLComponents(string: "https://api.open-meteo.com/v1/forecast")!
        parts.queryItems = [
            .init(name: "latitude", value: String(format: "%.2f", lat)),
            .init(name: "longitude", value: String(format: "%.2f", lon)),
            .init(name: "current", value: "temperature_2m,weather_code"),
            .init(name: "daily", value: "sunrise,sunset"),
            .init(name: "timezone", value: "auto"),
            .init(name: "forecast_days", value: "1"),
            .init(name: "temperature_unit", value: Locale.current.measurementSystem == .us ? "fahrenheit" : "celsius"),
        ]
        guard let url = parts.url,
              let (data, _) = try? await URLSession.shared.data(for: URLRequest(url: url, timeoutInterval: 8)),
              let r = try? JSONDecoder().decode(Response.self, from: data) else { return nil }
        let f = DateFormatter()
        f.dateFormat = "yyyy-MM-dd'T'HH:mm"
        f.timeZone = TimeZone(secondsFromGMT: r.utc_offset_seconds)
        return Snapshot(weather: weather(code: r.current.weather_code),
                        temperature: r.current.temperature_2m,
                        sunrise: r.daily.sunrise.first.flatMap { f.date(from: $0) },
                        sunset: r.daily.sunset.first.flatMap { f.date(from: $0) })
    }

    /// The weather shared by the app and all widgets (App Group). Only goes online when what's saved is
    /// older than `maxAge` or from somewhere else, so several widgets refreshing together make one request.
    nonisolated static func sharedSnapshot(lat: Double, lon: Double, maxAge: TimeInterval = 30 * 60) async -> Snapshot? {
        if let c = cached(), Date().timeIntervalSince(c.fetched) < maxAge,
           abs(c.lat - lat) < 0.1, abs(c.lon - lon) < 0.1 {
            return c.snap
        }
        guard let snap = await fetchSnapshot(lat: lat, lon: lon) else { return cached()?.snap }   // offline: last known
        save(snap, lat: lat, lon: lon)
        return snap
    }

    private struct Cached: Codable {
        let weather: String; let temperature: Double; let sunrise: Date?; let sunset: Date?
        let fetched: Date; let lat: Double; let lon: Double
    }
    private nonisolated static let cacheKey = "weather.snapshot"

    nonisolated static func save(_ s: Snapshot, lat: Double, lon: Double) {
        let c = Cached(weather: s.weather.rawValue, temperature: s.temperature, sunrise: s.sunrise, sunset: s.sunset,
                       fetched: Date(), lat: lat, lon: lon)
        if let data = try? JSONEncoder().encode(c) { SharedPal.defaults?.set(data, forKey: cacheKey) }
    }

    private nonisolated static func cached() -> (snap: Snapshot, fetched: Date, lat: Double, lon: Double)? {
        guard let data = SharedPal.defaults?.data(forKey: cacheKey),
              let c = try? JSONDecoder().decode(Cached.self, from: data),
              let w = RoomWeather(rawValue: c.weather) else { return nil }
        return (Snapshot(weather: w, temperature: c.temperature, sunrise: c.sunrise, sunset: c.sunset), c.fetched, c.lat, c.lon)
    }

    private func fetch(lat: Double, lon: Double) async {
        guard let snap = await Self.sharedSnapshot(lat: lat, lon: lon, maxAge: 10 * 60) else { return }
        sunrise = snap.sunrise
        sunset = snap.sunset
        weather = snap.weather
        lastFetch = Date()
        refreshTime()

        let clock = DateFormatter()
        clock.dateFormat = "h:mm"
        let next: String
        if let sunset, Date() < sunset { next = "sunset \(clock.string(from: sunset))" }
        else if let sunrise { next = "sunrise \(clock.string(from: sunrise.addingTimeInterval(Date() > sunrise ? 86_400 : 0)))" }
        else { next = "" }
        summary = "\(weather.label) \(Int(snap.temperature.rounded()))°  \(next)"
    }

    /// WMO weather codes -> the five room looks.
    nonisolated static func weather(code: Int) -> RoomWeather {
        switch code {
        case 0, 1: .clear
        case 2, 3, 45, 48: .cloudy
        case 71...77, 85, 86: .snow
        case 95...99: .storm
        case 51...67, 80...82: .rain
        default: .cloudy
        }
    }

    /// Sunrise = the hour around sunrise, sunset = the hour around sunset. Falls back to the clock.
    nonisolated static func clockTime(_ now: Date, sunrise: Date?, sunset: Date?) -> RoomTime {
        if let sunrise, let sunset {
            if now >= sunrise.addingTimeInterval(-30 * 60) && now < sunrise.addingTimeInterval(60 * 60) { return .sunrise }
            if now >= sunset.addingTimeInterval(-60 * 60) && now < sunset.addingTimeInterval(30 * 60) { return .sunset }
            if now >= sunrise && now < sunset { return .day }
            return .night
        }
        let h = Calendar.current.component(.hour, from: now)
        switch h {
        case 6..<8: return .sunrise
        case 8..<17: return .day
        case 17..<19: return .sunset
        default: return .night
        }
    }
}

extension RoomWeather {
    var label: String {
        switch self {
        case .clear: "Clear"
        case .cloudy: "Cloudy"
        case .rain: "Rain"
        case .storm: "Storm"
        case .snow: "Snow"
        }
    }
}
