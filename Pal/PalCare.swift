import Foundation
import SwiftUI

/// Everything about the pal that changes over time. Pure value type so the same rules
/// can run live in the app and be fast-forwarded to plan notifications.
struct PalState: Codable {
    var name = "Pal"
    var species: PalSpecies = .eevee
    var trainer: TrainerStyle = .male
    var notificationsOn = true
    var quietStartHour = 22
    var quietEndHour = 8
    var needs = Needs()
    var isAsleep = false
    var heldBerry: Food?
    var pantry: [Food: Int] = [.oran: 3, .sitrus: 1, .leppa: 1]
    var coins = 50
    var lastUpdate = Date()

    // Needs drop per hour (energy refills while asleep).
    static let hungerPerHour = 6.0
    static let happyPerHour = 4.0
    static let cleanPerHour = 3.0
    static let energyPerHourAwake = 5.0
    static let energyPerHourAsleep = 15.0

    /// Pal crawls into bed by itself at this energy, and wakes up at `wakeAt`.
    static let sleepyAt = 20.0
    static let wakeAt = 95.0

    /// Low-need thresholds that trigger the speech bubble and a notification.
    static let low = 30.0

    /// Advance time by `hours`, applying decay, falling asleep / waking up, and held berries.
    mutating func step(hours: Double) {
        needs.hunger = max(0, needs.hunger - Self.hungerPerHour * hours)
        needs.happy = max(0, needs.happy - Self.happyPerHour * hours)
        needs.clean = max(0, needs.clean - Self.cleanPerHour * hours)
        if isAsleep {
            needs.energy = min(Needs.max, needs.energy + Self.energyPerHourAsleep * hours)
            if needs.energy >= Self.wakeAt { isAsleep = false }
        } else {
            needs.energy = max(0, needs.energy - Self.energyPerHourAwake * hours)
            if needs.energy <= Self.sleepyAt { isAsleep = true }
        }
        // A held berry gets eaten on its own when its trigger hits (BW-style held items).
        if let berry = heldBerry, berry.heldTrigger(needs) {
            needs.eat(berry)
            heldBerry = nil
        }
    }

    /// Catch up from `lastUpdate` to `now` in small steps (works across days the app was closed).
    mutating func advance(to now: Date) {
        var remaining = now.timeIntervalSince(lastUpdate) / 3600
        while remaining > 0 {
            let dt = min(remaining, 5.0 / 60)   // 5-minute steps
            step(hours: dt)
            remaining -= dt
        }
        lastUpdate = now
    }

    var isHungry: Bool { needs.hunger <= Self.low }
    var wantsToPlay: Bool { needs.happy <= Self.low }
    var isDirty: Bool { needs.clean <= Self.low }
}

/// The live, saved pal the UI talks to.
@MainActor
final class PalCare: ObservableObject {
    static let shared = PalCare()

    @Published private(set) var state: PalState
    /// Set this to an App Group suite later so the widget can read the same pal.
    private let defaults = UserDefaults.standard
    private let key = "pal.state.v1"

    init() {
        if let data = UserDefaults.standard.data(forKey: key),
           let saved = try? JSONDecoder().decode(PalState.self, from: data) {
            state = saved
        } else {
            state = PalState()
        }
        refresh()
    }

    var needs: Needs { state.needs }
    var isAsleep: Bool { state.isAsleep }

    /// Call when the app opens, comes back to the foreground, goes to the background,
    /// and every so often while open (e.g. once a minute).
    func refresh(now: Date = Date()) {
        state.advance(to: now)
        save()
    }

    // MARK: actions

    /// Switch which pal you're raising (keeps its needs, coins and pantry).
    func choose(_ species: PalSpecies) {
        state.species = species
        if state.name == "Pal" || PalSpecies.allCases.map(\.displayName).contains(state.name) {
            state.name = species.displayName
        }
        save()
    }

    func chooseTrainer(_ trainer: TrainerStyle) {
        state.trainer = trainer
        save()
    }

    func setNotifications(_ on: Bool) {
        state.notificationsOn = on
        if on { PalNotifications.requestPermission() }
        save()
    }

    func setQuietHours(start: Int, end: Int) {
        state.quietStartHour = start
        state.quietEndHour = end
        save()
    }

    func rename(_ name: String) {
        let trimmed = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }
        state.name = String(trimmed.prefix(12))
        save()
    }

    @discardableResult
    func feed(_ food: Food) -> Bool {
        refresh()
        guard !state.isAsleep, (state.pantry[food] ?? 0) > 0 else { return false }
        state.pantry[food, default: 0] -= 1
        state.needs.eat(food)
        state.needs.happy = min(Needs.max, state.needs.happy + 2)
        save(); return true
    }

    /// Give the pal a berry to hold; it eats it by itself when the moment comes.
    @discardableResult
    func hold(_ food: Food) -> Bool {
        refresh()
        guard (state.pantry[food] ?? 0) > 0 else { return false }
        if let old = state.heldBerry { state.pantry[old, default: 0] += 1 }   // swap back into the pantry
        state.pantry[food, default: 0] -= 1
        state.heldBerry = food
        save(); return true
    }

    func play() {
        refresh()
        guard !state.isAsleep else { return }
        state.needs.happy = min(Needs.max, state.needs.happy + 20)
        state.needs.energy = max(0, state.needs.energy - 5)
        state.needs.hunger = max(0, state.needs.hunger - 3)
        state.coins += 5
        save()
    }

    func wash() {
        refresh()
        guard !state.isAsleep else { return }
        state.needs.clean = Needs.max
        save()
    }

    func pet() {
        refresh()
        state.needs.happy = min(Needs.max, state.needs.happy + 3)
        save()
    }

    /// Sleep button: tuck the pal in, or wake it up early.
    func toggleSleep() {
        refresh()
        state.isAsleep.toggle()
        save()
    }

    func buy(_ food: Food) -> Bool {
        guard state.coins >= food.price else { return false }
        state.coins -= food.price
        state.pantry[food, default: 0] += 1
        save(); return true
    }

    private func save() {
        if let data = try? JSONEncoder().encode(state) { defaults.set(data, forKey: key) }
        PalNotifications.reschedule(from: state)
    }
}
