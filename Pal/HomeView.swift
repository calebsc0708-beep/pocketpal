import SwiftUI

/// The main PokePal screen: the room, your pal's needs, care buttons and the berry pantry.
struct HomeView: View {
    @StateObject private var care = PalCare.shared
    @StateObject private var sky = WeatherSync.shared
    @Environment(\.scenePhase) private var scenePhase

    @State private var feeding: FeedingEvent?
    @State private var showFeedMenu = false
    @State private var toast: String?

    private let ticker = Timer.publish(every: 30, on: .main, in: .common).autoconnect()

    var body: some View {
        ScrollView {
            VStack(spacing: 18) {
                header
                room
                needsCard
                actions
                pantry
            }
            .padding(16)
        }
        .background(PalTheme.paper.ignoresSafeArea())
        .onAppear {
            care.refresh()
            sky.start()
            if care.state.notificationsOn { PalNotifications.requestPermission() }
        }
        .onChange(of: scenePhase) { _, phase in
            care.refresh()
            if phase == .active { sky.start() }
        }
        .onReceive(ticker) { _ in
            care.refresh()
            sky.refreshTime()
        }
        .confirmationDialog("Feed \(care.state.name)", isPresented: $showFeedMenu, titleVisibility: .visible) {
            ForEach(Food.allCases) { food in
                Button("\(food.name) (x\(care.state.pantry[food] ?? 0))") { feed(food) }
            }
        }
    }

    // MARK: sections

    private var header: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 6) {
                Text("PokePal")
                    .font(PalTheme.font(30, bold: true))
                Text(care.state.name)
                    .font(PalTheme.font(17))
                    .opacity(0.75)
            }
            .foregroundStyle(PalTheme.ink)
            Spacer()
            VStack(alignment: .trailing, spacing: 8) {
                HStack(spacing: 10) {
                    chip(fill: Color(red: 1, green: 240 / 255, blue: 190 / 255)) {
                        HStack(spacing: 6) {
                            Image(systemName: "circle.fill").foregroundStyle(Color(red: 250 / 255, green: 214 / 255, blue: 100 / 255))
                            Text("\(care.state.coins)").font(PalTheme.font(18, bold: true))
                        }
                    }
                    SettingsButton()
                }
                if !sky.summary.isEmpty {
                    chip(fill: Color(red: 206 / 255, green: 228 / 255, blue: 252 / 255)) {
                        Text(sky.summary).font(PalTheme.font(13))
                    }
                }
            }
        }
    }

    private var room: some View {
        ZStack(alignment: .top) {
            PalRoomView(time: sky.time, weather: sky.weather, asleep: care.isAsleep,
                        species: care.state.species, feeding: feeding)
                .clipShape(RoundedRectangle(cornerRadius: 10))
                .padding(4)
                .background(RoundedRectangle(cornerRadius: 14).fill(PalTheme.ink))
                .onTapGesture {
                    care.pet()
                    flash("♥")
                }

            if let text = bubbleText {
                Text(text)
                    .font(PalTheme.font(16, bold: true))
                    .foregroundStyle(PalTheme.ink)
                    .padding(.horizontal, 12).padding(.vertical, 6)
                    .background(Capsule().fill(Color.white))
                    .overlay(Capsule().strokeBorder(PalTheme.ink, lineWidth: 2.5))
                    .padding(.top, 14)
                    .transition(.scale.combined(with: .opacity))
            }
            if let toast {
                Text(toast)
                    .font(PalTheme.font(15, bold: true))
                    .foregroundStyle(PalTheme.ink)
                    .padding(.horizontal, 10).padding(.vertical, 4)
                    .background(Capsule().fill(PalTheme.pinkLight))
                    .frame(maxHeight: .infinity, alignment: .bottom)
                    .padding(.bottom, 14)
                    .transition(.opacity)
            }
        }
        .animation(.snappy, value: bubbleText)
    }

    private var needsCard: some View {
        PalCard {
            Grid(horizontalSpacing: 18, verticalSpacing: 12) {
                GridRow {
                    meter("Hunger", value: care.needs.hunger, color: Color(red: 252 / 255, green: 186 / 255, blue: 120 / 255))
                    meter("Happy", value: care.needs.happy, color: PalTheme.pink)
                }
                GridRow {
                    meter("Energy", value: care.needs.energy, color: Color(red: 250 / 255, green: 214 / 255, blue: 100 / 255))
                    meter("Clean", value: care.needs.clean, color: Color(red: 130 / 255, green: 186 / 255, blue: 240 / 255))
                }
            }
            .padding(14)
        }
    }

    private var actions: some View {
        HStack(spacing: 12) {
            actionButton("Feed", fill: Color(red: 1, green: 226 / 255, blue: 196 / 255), alert: care.state.isHungry) {
                Image(Food.sitrus.imageName).resizable().interpolation(.none).frame(width: 44, height: 44)
            } action: { showFeedMenu = true }
            actionButton("Play", fill: PalTheme.pinkLight, alert: care.state.wantsToPlay) {
                Image(systemName: "tennisball.fill").font(.system(size: 28))
            } action: {
                care.play()
                flash("+5 coins")
            }
            actionButton("Wash", fill: Color(red: 206 / 255, green: 228 / 255, blue: 252 / 255), alert: care.state.isDirty) {
                Image(systemName: "bubbles.and.sparkles.fill").font(.system(size: 28))
            } action: {
                care.wash()
                flash("Squeaky clean!")
            }
            actionButton(care.isAsleep ? "Wake" : "Sleep", fill: Color(red: 206 / 255, green: 240 / 255, blue: 222 / 255), alert: false) {
                Image(systemName: care.isAsleep ? "sun.max.fill" : "moon.zzz.fill").font(.system(size: 28))
            } action: { care.toggleSleep() }
        }
        .disabled(feeding.map { !$0.isFinished(Date()) } ?? false)
    }

    private var pantry: some View {
        PalCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text("Berry pantry").font(PalTheme.font(20, bold: true))
                    Spacer()
                    Text("hold to buy or give").font(PalTheme.font(13)).opacity(0.6)
                }
                HStack(spacing: 10) {
                    ForEach(Food.allCases) { food in
                        berryButton(food)
                    }
                }
                if let held = care.state.heldBerry {
                    Text("Holding a \(held.name). It'll eat it when it needs it.")
                        .font(PalTheme.font(14)).opacity(0.7)
                }
            }
            .foregroundStyle(PalTheme.ink)
            .padding(14)
        }
    }

    // MARK: pieces

    private func berryButton(_ food: Food) -> some View {
        let count = care.state.pantry[food] ?? 0
        return Button { feed(food) } label: {
            VStack(spacing: 4) {
                Image(food.imageName).resizable().interpolation(.none).frame(width: 48, height: 48)
                Text(food.name.replacingOccurrences(of: " Berry", with: "")).font(PalTheme.font(15, bold: true))
                Text("x\(count)").font(PalTheme.font(13)).opacity(0.7)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .background(RoundedRectangle(cornerRadius: 10).fill(count > 0 ? Color.white : PalTheme.shadow))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(PalTheme.ink, lineWidth: 2.5))
        }
        .buttonStyle(.plain)
        .contextMenu {
            Button { if care.buy(food) { flash("Bought a \(food.name)") } else { flash("Not enough coins") } } label: {
                Label("Buy for \(food.price) coins", systemImage: "cart")
            }
            Button { if care.hold(food) { flash("Holding a \(food.name)") } } label: {
                Label("Give it to hold", systemImage: "hand.raised")
            }
            Text(food.blurb)
        }
    }

    private func meter(_ title: String, value: Double, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(PalTheme.font(16, bold: true)).foregroundStyle(PalTheme.ink)
            HStack(spacing: 3) {
                ForEach(0..<10, id: \.self) { i in
                    RoundedRectangle(cornerRadius: 2)
                        .fill(Double(i) < (value / 10).rounded(.up) ? color : color.opacity(0.25))
                        .overlay(RoundedRectangle(cornerRadius: 2).strokeBorder(PalTheme.ink, lineWidth: 1.5))
                        .frame(height: 12)
                }
            }
        }
    }

    private func actionButton<Icon: View>(_ title: String, fill: Color, alert: Bool,
                                          @ViewBuilder icon: () -> Icon, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            PalCard(fill: fill) {
                VStack(spacing: 6) {
                    icon().foregroundStyle(PalTheme.ink).frame(height: 44)
                    Text(title).font(PalTheme.font(17, bold: true)).foregroundStyle(PalTheme.ink)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 12)
            }
            .overlay(alignment: .topTrailing) {
                if alert {
                    Text("!")
                        .font(PalTheme.font(14, bold: true))
                        .foregroundStyle(.white)
                        .frame(width: 22, height: 22)
                        .background(Circle().fill(Color(red: 240 / 255, green: 90 / 255, blue: 100 / 255)))
                        .overlay(Circle().strokeBorder(PalTheme.ink, lineWidth: 2))
                        .offset(x: 6, y: -6)
                }
            }
        }
        .buttonStyle(.plain)
    }

    private func chip<Content: View>(fill: Color, @ViewBuilder content: () -> Content) -> some View {
        content()
            .foregroundStyle(PalTheme.ink)
            .padding(.horizontal, 10).padding(.vertical, 6)
            .background(RoundedRectangle(cornerRadius: 10).fill(fill))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(PalTheme.ink, lineWidth: 2.5))
    }

    // MARK: logic

    private var bubbleText: String? {
        if care.isAsleep { return nil }
        if care.state.isHungry { return "hungry!" }
        if care.state.wantsToPlay { return "let's play!" }
        if care.state.isDirty { return "bath time?" }
        return nil
    }

    private func feed(_ food: Food) {
        if care.isAsleep { flash("Shh... \(care.state.name) is sleeping"); return }
        if (care.state.pantry[food] ?? 0) == 0 { flash("Out of \(food.name)s. Hold to buy more"); return }
        if care.feed(food) {
            feeding = FeedingEvent(food: food, trainer: care.state.trainer)
        }
    }

    private func flash(_ text: String) {
        withAnimation { toast = text }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
            withAnimation { if toast == text { toast = nil } }
        }
    }
}

/// App root: the PokePal home plus the original Dynamic Island screen.
struct RootView: View {
    var body: some View {
        TabView {
            HomeView()
                .tabItem { Label("Home", systemImage: "house.fill") }
            ContentView()
                .tabItem { Label("Island", systemImage: "capsule.fill") }
        }
        .tint(PalTheme.pink)
    }
}

#Preview {
    RootView()
}
