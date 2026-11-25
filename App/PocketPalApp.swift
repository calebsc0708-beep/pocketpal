import SwiftUI
import ActivityKit

@main
struct PocketPalApp: App {
    var body: some Scene {
        WindowGroup { RootView() }
    }
}

/// Per-sprite zoom and position inside the island spot.
final class FitStore: ObservableObject {
    struct Fit: Codable, Equatable {
        var zoom = 1.0
        var x = 0.0
        var y = 0.0
    }

    @Published private var fits: [String: Fit] = [:]
    private let key = "spriteFits"

    init() {
        if let data = UserDefaults.standard.data(forKey: key),
           let decoded = try? JSONDecoder().decode([String: Fit].self, from: data) {
            fits = decoded
        }
    }

    func fit(for id: String) -> Fit { fits[id] ?? Fit() }

    func set(_ fit: Fit, for id: String) {
        fits[id] = fit
        if let data = try? JSONEncoder().encode(fits) { UserDefaults.standard.set(data, forKey: key) }
    }
}

/// The Dynamic Island controls, shown as a section on the main PokePal page.
struct IslandSection: View {
    @StateObject private var custom = CustomSpriteStore()
    @StateObject private var fits = FitStore()

    @AppStorage("selectedSprite") private var selected = ""
    @AppStorage("selectedIsCustom") private var selectedIsCustom = false
    @AppStorage("nickname") private var nickname = ""
    @AppStorage("animate") private var animate = true
    @AppStorage("trailing") private var trailing = "sparkles"
    @AppStorage("motion") private var motion = "hop"

    @State private var previewStart = Date()
    @State private var customPNG: Data?
    @State private var status = ""
    @State private var showImport = false
    @State private var showEditor = false

    private let bundled = Sprites.all

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Dynamic Island")
                .font(PalTheme.font(24, bold: true))
                .padding(.top, 6)

            PalCard {
                VStack(spacing: 16) {
                    islandPreview
                    spriteGrid
                }
                .padding(14)
            }

            PalCard {
                VStack(spacing: 16) {
                    controls
                    Rectangle().fill(PalTheme.ink.opacity(0.15)).frame(height: 2)
                    fitControls
                }
                .padding(14)
            }

            HStack(spacing: 12) {
                Button { Task { await start() } } label: {
                    PalCard(fill: PalTheme.pink) {
                        Text("Show in Island")
                            .font(PalTheme.font(19, bold: true))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                    }
                }
                .buttonStyle(.plain)
                .disabled(selected.isEmpty)
                .opacity(selected.isEmpty ? 0.5 : 1)

                Button { Task { await stopAll(); status = "Pal put away." } } label: {
                    PalCard {
                        Text("Put away")
                            .font(PalTheme.font(19, bold: true))
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                    }
                }
                .buttonStyle(.plain)
            }

            if !status.isEmpty {
                Text(status)
                    .font(PalTheme.font(15))
                    .opacity(0.75)
                    .frame(maxWidth: .infinity)
                    .multilineTextAlignment(.center)
            }
        }
        .foregroundStyle(PalTheme.ink)
        .tint(PalTheme.pink)
        .sheet(isPresented: $showImport) {
            ImportSpriteView(store: custom) { selectCustom($0) }
        }
        .sheet(isPresented: $showEditor) {
            PixelEditorView(store: custom) { selectCustom($0) }
        }
        .onAppear(perform: restoreSelection)
    }

    // MARK: Sections

    private var spriteGrid: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 84))], spacing: 12) {
            ForEach(bundled) { entry in
                tile(name: entry.name, isSelected: !selectedIsCustom && selected == entry.name, badge: entry.isAnimated) {
                    IslandSprite(customPNG: nil, state: tileState(entry.name), size: 64)
                }
                .onTapGesture { selectBundled(entry.name) }
            }
            ForEach(custom.sprites) { sprite in
                tile(name: sprite.name, isSelected: selectedIsCustom && selected == sprite.name, badge: false) {
                    SpriteImage(image: custom.image(sprite)).frame(width: 64, height: 64)
                }
                .onTapGesture { selectCustom(sprite.name) }
                .contextMenu {
                    ShareLink(item: sprite.url) { Label("Share / save PNG", systemImage: "square.and.arrow.up") }
                    Button(role: .destructive) {
                        if selectedIsCustom && selected == sprite.name { selected = ""; customPNG = nil }
                        custom.delete(sprite)
                    } label: { Label("Delete", systemImage: "trash") }
                }
            }
            Button { showImport = true } label: {
                addTile(title: "Import", symbol: "photo.badge.plus")
            }
            .buttonStyle(.plain)
            Button { showEditor = true } label: {
                addTile(title: "Draw", symbol: "pencil.and.scribble")
            }
            .buttonStyle(.plain)
        }
    }

    private var islandPreview: some View {
        VStack(spacing: 6) {
            HStack(spacing: 0) {
                IslandSprite(customPNG: selectedIsCustom ? customPNG : nil, state: previewState, size: 26)
                Spacer()
                TrailingView(state: previewState).foregroundStyle(.white)
            }
            .padding(.horizontal, 14)
            .frame(width: 200, height: 37)
            .background(Capsule().fill(.black))
            .overlay(Capsule().strokeBorder(PalTheme.ink, lineWidth: 3))
            Text("Island preview").font(PalTheme.font(13)).opacity(0.6)
        }
    }

    private var controls: some View {
        VStack(spacing: 14) {
            TextField("Nickname (optional)", text: $nickname)
                .font(PalTheme.font(17))
                .padding(.horizontal, 12).padding(.vertical, 10)
                .background(RoundedRectangle(cornerRadius: 10).fill(Color.white))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(PalTheme.ink, lineWidth: 2.5))

            if selectedIsCustom {
                Text("Sprites added in the app stay still. To animate or move one, long-press it → Share / save PNG, then add it to the Sprites folder on GitHub.")
                    .font(PalTheme.font(14))
                    .opacity(0.7)
            } else {
                if selectedEntry?.isAnimated == true {
                    Toggle(isOn: $animate) { Text("Animate").font(PalTheme.font(17, bold: true)) }
                }
                pickerRow("Movement", selection: $motion, options: Sprites.motions)
            }

            pickerRow("Next to your pal", selection: $trailing, options: TrailingOption.all)
        }
    }

    private var fitControls: some View {
        let id = fitID
        let fit = fits.fit(for: id)
        return VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Fit in island").font(PalTheme.font(19, bold: true))
                Spacer()
                Button("Reset") { fits.set(.init(), for: id) }
                    .font(PalTheme.font(15, bold: true))
                    .disabled(fit == .init())
            }
            sliderRow("Size", value: binding(id, \.zoom), range: 0.5...1.6)
            sliderRow("Left / right", value: binding(id, \.x), range: -0.35...0.35)
            sliderRow("Up / down", value: binding(id, \.y), range: -0.35...0.35)
        }
        .disabled(selected.isEmpty)
    }

    // MARK: Building blocks

    private func tile<Content: View>(name: String, isSelected: Bool, badge: Bool,
                                     @ViewBuilder content: () -> Content) -> some View {
        VStack(spacing: 6) {
            content()
            HStack(spacing: 3) {
                Text(name).font(PalTheme.font(14, bold: true)).lineLimit(1)
                if badge { Image(systemName: "sparkles").font(.caption2) }
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .background(RoundedRectangle(cornerRadius: 12).fill(isSelected ? PalTheme.pinkLight : Color.white))
        .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(PalTheme.ink, lineWidth: isSelected ? 3 : 2))
        .contentShape(Rectangle())
    }

    private func addTile(title: String, symbol: String) -> some View {
        VStack(spacing: 6) {
            Image(systemName: symbol).font(.title2).frame(width: 64, height: 64)
            Text(title).font(PalTheme.font(14, bold: true))
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .foregroundStyle(PalTheme.ink)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(PalTheme.ink.opacity(0.6), style: StrokeStyle(lineWidth: 2, dash: [5]))
        )
    }

    private func pickerRow(_ title: String, selection: Binding<String>,
                           options: [(label: String, value: String)]) -> some View {
        HStack {
            Text(title).font(PalTheme.font(17, bold: true))
            Spacer()
            Picker(title, selection: selection) {
                ForEach(options, id: \.value) { Text($0.label).tag($0.value) }
            }
        }
    }

    private func sliderRow(_ title: String, value: Binding<Double>, range: ClosedRange<Double>) -> some View {
        HStack {
            Text(title).font(PalTheme.font(15)).frame(width: 96, alignment: .leading)
            Slider(value: value, in: range)
        }
    }

    private func binding(_ id: String, _ path: WritableKeyPath<FitStore.Fit, Double>) -> Binding<Double> {
        Binding(
            get: { fits.fit(for: id)[keyPath: path] },
            set: { newValue in
                var fit = fits.fit(for: id)
                fit[keyPath: path] = newValue
                fits.set(fit, for: id)
            }
        )
    }

    // MARK: State

    private var selectedEntry: SpriteEntry? {
        selectedIsCustom ? nil : bundled.first { $0.name == selected }
    }

    private var fitID: String { (selectedIsCustom ? "custom:" : "bundled:") + selected }

    private func tileState(_ name: String) -> PetAttributes.ContentState {
        .init(spriteName: name, nickname: "", startDate: previewStart, animate: true,
              trailing: "none", motion: "none", zoom: 1, offsetX: 0, offsetY: 0)
    }

    private var previewState: PetAttributes.ContentState {
        makeState(start: previewStart)
    }

    private func makeState(start: Date) -> PetAttributes.ContentState {
        let fit = fits.fit(for: fitID)
        return .init(spriteName: selected, nickname: nickname, startDate: start, animate: animate,
                     trailing: trailing, motion: selectedIsCustom ? "none" : motion,
                     zoom: fit.zoom, offsetX: fit.x, offsetY: fit.y)
    }

    private func selectBundled(_ name: String) {
        selected = name
        selectedIsCustom = false
        customPNG = nil
        // picking one of the room pals here makes it the room pal too
        if let species = PalSpecies(rawValue: name) { PalSettings.shared.choose(species, syncIsland: false) }
        if let s = Sprites.settings[name] {
            if let m = s.motion, Sprites.motions.contains(where: { $0.value == m }) { motion = m }
            if let icon = s.icon { trailing = icon }
            if let n = s.nickname { nickname = n }
        }
    }

    private func selectCustom(_ name: String) {
        selected = name
        selectedIsCustom = true
        customPNG = custom.sprite(named: name).flatMap { custom.image($0) }.flatMap { ImageTools.islandPNG($0) }
    }

    private func restoreSelection() {
        if selectedIsCustom, custom.sprite(named: selected) != nil {
            selectCustom(selected)
        } else {
            selectedIsCustom = false
            if !bundled.contains(where: { $0.name == selected }) {
                selected = bundled.first?.name ?? ""
            }
        }
    }

    // MARK: Live Activity

    private func start() async {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            status = "Live Activities are turned off. Turn them on in Settings → PokePal."
            return
        }
        if selectedIsCustom && customPNG == nil {
            status = "This sprite has too much detail to fit in the island. Try importing it again with Pixelate on."
            return
        }
        await stopAll()
        do {
            _ = try Activity.request(
                attributes: PetAttributes(customPNG: selectedIsCustom ? customPNG : nil),
                content: .init(state: makeState(start: Date()), staleDate: nil, relevanceScore: 100),
                pushType: nil
            )
            status = "Your pal is out! Swipe home to see it in the Dynamic Island."
        } catch {
            status = "Couldn't start: \(error.localizedDescription)"
        }
    }

    private func stopAll() async {
        for activity in Activity<PetAttributes>.activities {
            await activity.end(nil, dismissalPolicy: .immediate)
        }
    }
}
