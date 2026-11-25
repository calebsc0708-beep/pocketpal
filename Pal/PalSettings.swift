import Foundation
import SwiftUI

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
    }

    /// Pick the room pal. Also makes it the Dynamic Island sprite, so they always match.
    func choose(_ species: PalSpecies, syncIsland: Bool = true) {
        // keep a custom name; otherwise follow the species
        if PalSpecies.allCases.map(\.displayName).contains(name) { name = species.displayName }
        self.species = species
        save()
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
