import Foundation

/// The pal you picked in the app, shared with the widgets through an App Group.
///
/// SideStore/AltStore rename app groups when they install the app (they add your team ID),
/// and write the real names into the `ALTAppGroups` Info.plist key. So we read that key
/// (from this bundle, then from the app that contains the widget) and only fall back to
/// the plain name if it isn't there.
enum SharedPal {
    static let defaultGroup = "group.com.yourname.pocketpal"
    private static let key = "pal.species"

    static var groupID: String {
        if let g = altGroups(Bundle.main.infoDictionary)?.first { return g }
        // inside the widget: PocketPal.app/PlugIns/PocketPalWidget.appex -> PocketPal.app/Info.plist
        let appURL = Bundle.main.bundleURL.deletingLastPathComponent().deletingLastPathComponent()
        if appURL.pathExtension == "app",
           let info = NSDictionary(contentsOf: appURL.appendingPathComponent("Info.plist")) as? [String: Any],
           let g = altGroups(info)?.first {
            return g
        }
        return defaultGroup
    }

    private static func altGroups(_ info: [String: Any]?) -> [String]? {
        guard let groups = info?["ALTAppGroups"] as? [String], !groups.isEmpty else { return nil }
        return groups
    }

    static var defaults: UserDefaults? { UserDefaults(suiteName: groupID) }

    /// Raw value of the picked pal (e.g. "eevee"), or nil if the app hasn't saved one.
    static var species: String? { defaults?.string(forKey: key) }

    static func save(_ rawValue: String) {
        defaults?.set(rawValue, forKey: key)
    }
}
