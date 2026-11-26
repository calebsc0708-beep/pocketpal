import Foundation
import SwiftUI
import WidgetKit

/// Which pal lives in the room, and its name. Saved on this device.
@MainActor
final class PalSettings: ObservableObject {
    static let shared = PalSettings()

    @Published private(set) var species: PalSpecies
    @Published private(set) var name: String

    private let defaults = UserDefaults.standard

    init() {
        let saved = PalSpecies(rawValue: UserDefaults.standard.string(forKey: "pal.species") ?? "") ?? .eevee
        species = saved
        name = UserDefaults.standard.string(forKey: "pal.name") ?? saved.displayName
        // make sure the widgets know the current pal (e.g. after an update)
        if SharedPal.species != saved.rawValue {
            SharedPal.save(saved.rawValue)
            Self.reloadWidgets()
        }
    }

    /// True once the pal changed this session; the widgets get one more reload when the app is left.
    private(set) var widgetsNeedReload = false

    /// Ask the room and Lock Screen widgets to redraw with the current pal. iOS can drop a reload asked for
    /// while a widget isn't on screen (the Lock Screen never is while you're in the app), so ask by kind,
    /// again a moment later, and once more when the app goes to the background (see HomeView).
    static func reloadWidgets() {
        let center = WidgetCenter.shared
        for kind in ["PokePalLock", "PokePalRoom"] { center.reloadTimelines(ofKind: kind) }
        Task { @MainActor in
            try? await Task.sleep(for: .seconds(2))
            for kind in ["PokePalLock", "PokePalRoom"] { center.reloadTimelines(ofKind: kind) }
        }
    }

    func appDidLeave() {
        guard widgetsNeedReload else { return }
        widgetsNeedReload = false
        WidgetCenter.shared.reloadAllTimelines()
    }

    /// Pick the room pal. Also makes it the Dynamic Island sprite, so they always match.
    func choose(_ species: PalSpecies, syncIsland: Bool = true) {
        // keep a custom name; otherwise follow the species
        if PalSpecies.allCases.map(\.displayName).contains(name) { name = species.displayName }
        self.species = species
        save()
        // the room and Lock Screen widgets follow the app's pal
        SharedPal.save(species.rawValue)
        Self.reloadWidgets()
        widgetsNeedReload = true
        if syncIsland {
            // same keys the Dynamic Island section reads with @AppStorage
            defaults.set(species.rawValue, forKey: "selectedSprite")
            defaults.set(false, forKey: "selectedIsCustom")
        }
    }

    func rename(_ newName: String) {
        let trimmed = newName.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        name = String(trimmed.prefix(12))
        save()
    }

    private func save() {
        defaults.set(species.rawValue, forKey: "pal.species")
        defaults.set(name, forKey: "pal.name")
    }
}
