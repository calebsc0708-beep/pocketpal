import Foundation
import UserNotifications

/// Local notifications for the pal's needs. They're planned ahead by fast-forwarding the
/// pal's state, because the app isn't running when they're due. Local notifications
/// don't need a paid developer account, so they work when sideloaded.
enum PalNotifications {

    static func requestPermission() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in }
    }

    private enum Kind: String, CaseIterable {
        case hungry, sleepy, woke, play, bath

        func message(_ name: String) -> (String, String) {
            switch self {
            case .hungry: ("\(name) is hungry!", "Their tummy is rumbling. Time for a berry?")
            case .sleepy: ("\(name) is sleepy 💤", "They crawled under the covers for a nap.")
            case .woke:   ("\(name) woke up ☀️", "All rested and ready to hang out.")
            case .play:   ("\(name) wants to play!", "They keep looking at you with big eyes.")
            case .bath:   ("\(name) needs a bath 🫧", "Things are getting a little messy.")
            }
        }
    }

    /// Fast-forward a copy of the state for up to 2 days and schedule the first time each thing happens.
    static func reschedule(from current: PalState) {
        var sim = current
        let start = current.lastUpdate
        var found: [Kind: Date] = [:]
        var wasAsleep = sim.isAsleep
        var minutes = 0
        while minutes < 48 * 60 && found.count < Kind.allCases.count {
            sim.step(hours: 5.0 / 60)
            minutes += 5
            let at = start.addingTimeInterval(Double(minutes) * 60)
            func mark(_ k: Kind, _ cond: Bool) { if cond && found[k] == nil { found[k] = at } }
            mark(.hungry, sim.isHungry && !current.isHungry)
            mark(.play, sim.wantsToPlay && !current.wantsToPlay && !sim.isAsleep)
            mark(.bath, sim.isDirty && !current.isDirty)
            mark(.sleepy, sim.isAsleep && !wasAsleep)
            mark(.woke, !sim.isAsleep && wasAsleep)
            wasAsleep = sim.isAsleep
        }

        let center = UNUserNotificationCenter.current()
        center.removePendingNotificationRequests(withIdentifiers: Kind.allCases.map { "pal.\($0.rawValue)" })
        guard current.notificationsOn else { return }
        for (kind, date) in found {
            let fire = outsideQuietHours(date, start: current.quietStartHour, end: current.quietEndHour)
            let interval = fire.timeIntervalSinceNow
            guard interval > 1 else { continue }
            let (title, body) = kind.message(current.name)
            let content = UNMutableNotificationContent()
            content.title = title
            content.body = body
            content.sound = .default
            let trigger = UNTimeIntervalNotificationTrigger(timeInterval: interval, repeats: false)
            center.add(UNNotificationRequest(identifier: "pal.\(kind.rawValue)", content: content, trigger: trigger))
        }
    }

    /// Push a time that lands in quiet hours to when they end (handles windows that cross midnight).
    private static func outsideQuietHours(_ date: Date, start: Int, end: Int) -> Date {
        guard start != end else { return date }
        let cal = Calendar.current
        let hour = cal.component(.hour, from: date)
        let quiet = start < end ? (hour >= start && hour < end) : (hour >= start || hour < end)
        guard quiet else { return date }
        var day = cal.startOfDay(for: date)
        if start > end && hour >= start { day = cal.date(byAdding: .day, value: 1, to: day)! }
        return cal.date(bySettingHour: end, minute: 0, second: 0, of: day)!
    }
}
