import Foundation

/// Snacks the pal can eat, based on how these berries work in Pokémon Black/White and Black 2/White 2.
/// Needs run 0...100, so "HP" maps to Hunger and "PP" maps to Energy.
/// Images are 36x36 pixel art in PalSprites.xcassets.
enum Food: String, CaseIterable, Identifiable, Codable {
    case oran, sitrus, leppa

    var id: String { rawValue }
    var name: String {
        switch self {
        case .oran:   "Oran Berry"
        case .sitrus: "Sitrus Berry"
        case .leppa:  "Leppa Berry"
        }
    }
    var imageName: String { "food_\(rawValue)" }

    /// What it says on the bag screen.
    var blurb: String {
        switch self {
        case .oran:   "Restores 10 Hunger."
        case .sitrus: "Restores 25% of Hunger."
        case .leppa:  "Restores 10 Energy."
        }
    }

    /// Effect when fed (or eaten while held).
    /// Oran: restores 10 HP        -> +10 Hunger (a flat amount)
    /// Sitrus: restores 25% max HP -> +25 Hunger (25% of the 100 max)
    /// Leppa: restores 10 PP       -> +10 Energy, no Hunger
    var hunger: Double {
        switch self {
        case .oran: 10
        case .sitrus: 0.25 * Needs.max
        case .leppa: 0
        }
    }
    var energy: Double { self == .leppa ? 10 : 0 }

    /// Held-item behaviour: the pal can hold one berry and eats it on its own when the trigger hits.
    /// Oran/Sitrus: eaten once Hunger is at or below half (like HP at 1/2 max).
    /// Leppa: eaten once Energy runs out (like a move hitting 0 PP).
    func heldTrigger(_ needs: Needs) -> Bool {
        switch self {
        case .oran, .sitrus: needs.hunger <= Needs.max / 2
        case .leppa: needs.energy <= 0
        }
    }

    /// Price in coins. In BW/B2W2 all three sell to the gourmet maniac on Route 5 for $20,
    /// so they're all the same price here too.
    var price: Int { 20 }
}

/// The pal's needs, 0...100 each.
struct Needs: Codable {
    static let max: Double = 100
    var hunger: Double = 80
    var happy: Double = 80
    var energy: Double = 80
    var clean: Double = 80

    mutating func eat(_ food: Food) {
        hunger = min(Self.max, hunger + food.hunger)
        energy = min(Self.max, energy + food.energy)
    }
}
