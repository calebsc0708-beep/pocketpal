import SwiftUI

/// The main PokePal screen: your pal wandering its room, synced to your time of day and weather.
struct HomeView: View {
    @StateObject private var settings = PalSettings.shared
    @StateObject private var sky = WeatherSync.shared
    @Environment(\.scenePhase) private var scenePhase

    private let ticker = Timer.publish(every: 30, on: .main, in: .common).autoconnect()

    var body: some View {
        VStack(spacing: 16) {
            header
            PalRoomView(time: sky.time, weather: sky.weather, asleep: sky.time == .night, species: settings.species)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .padding(4)
                .background(RoundedRectangle(cornerRadius: 14).fill(PalTheme.ink))
                .background(RoundedRectangle(cornerRadius: 14).fill(PalTheme.shadow).offset(y: 4))
            Spacer(minLength: 0)
        }
        .padding(16)
        .background(PalTheme.paper.ignoresSafeArea())
        .onAppear { sky.start() }
        .onChange(of: scenePhase) { _, phase in if phase == .active { sky.start() } }
        .onReceive(ticker) { _ in sky.refreshTime() }
    }

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 6) {
                Text("PokePal")
                    .font(PalTheme.font(30, bold: true))
                Text(settings.name)
                    .font(PalTheme.font(17))
                    .opacity(0.75)
            }
            .foregroundStyle(PalTheme.ink)
            Spacer()
            VStack(alignment: .trailing, spacing: 8) {
                SettingsButton()
                if !sky.summary.isEmpty {
                    Text(sky.summary)
                        .font(PalTheme.font(13))
                        .foregroundStyle(PalTheme.ink)
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .background(RoundedRectangle(cornerRadius: 10).fill(Color(red: 206 / 255, green: 228 / 255, blue: 252 / 255)))
                        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(PalTheme.ink, lineWidth: 2.5))
                }
            }
        }
    }
}

/// App root: the PokePal room plus the original Dynamic Island screen.
struct RootView: View {
    var body: some View {
        TabView {
            HomeView()
                .tabItem { Label("Room", systemImage: "house.fill") }
            ContentView()
                .tabItem { Label("Island", systemImage: "capsule.fill") }
        }
        .tint(PalTheme.pink)
    }
}

#Preview {
    RootView()
}
