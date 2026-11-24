import ActivityKit
import SwiftUI
import UIKit
import CoreText

// MARK: - Live Activity data

struct PetAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var spriteName: String
        var nickname: String
        var startDate: Date
        var animate: Bool
        var trailing: String   // "none", "name", "timer", or an SF Symbol name
        var motion: String     // "none", "hop", "wiggle", "wander"
        var zoom: Double       // 1 = normal size
        var offsetX: Double    // fraction of the sprite box, - left / + right
        var offsetY: Double    // fraction of the sprite box, - up / + down
    }

    /// Tiny PNG for sprites added inside the app (Photos import / pixel editor).
    /// Live Activities can only carry about 4 KB of data, so this is kept very small.
    var customPNG: Data?
}

// MARK: - Bundled sprites (built by tools/build_sprites.py)

/// One selectable bundled sprite: a single image or numbered animation frames.
struct SpriteEntry: Identifiable, Hashable {
    let name: String
    let frames: [String]          // file stems, in order
    var id: String { name }
    var isAnimated: Bool { frames.count > 1 }
}

/// Optional per-sprite defaults from Sprites/sprites.json.
struct SpriteSettings: Codable, Hashable {
    var nickname: String?
    var motion: String?
    var icon: String?
}

enum Sprites {
    private static var folder: URL? {
        Bundle.main.resourceURL?.appendingPathComponent("Sprites", isDirectory: true)
    }

    static let all: [SpriteEntry] = {
        guard let folder,
              let files = try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
        else { return [] }

        var singles: [String] = []
        var animated: [String: [(Int, String)]] = [:]
        for url in files where url.pathExtension.lowercased() == "png" {
            let stem = url.deletingPathExtension().lastPathComponent
            if let underscore = stem.lastIndex(of: "_"),
               underscore != stem.startIndex,
               let number = Int(stem[stem.index(after: underscore)...]) {
                animated[String(stem[..<underscore]), default: []].append((number, stem))
            } else {
                singles.append(stem)
            }
        }
        var entries = singles.map { SpriteEntry(name: $0, frames: [$0]) }
        for (name, frames) in animated {
            entries.append(SpriteEntry(name: name, frames: frames.sorted { $0.0 < $1.0 }.map(\.1)))
        }
        return entries.sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }()

    static let settings: [String: SpriteSettings] = {
        guard let url = folder?.appendingPathComponent("sprites.json"),
              let data = try? Data(contentsOf: url),
              let decoded = try? JSONDecoder().decode([String: SpriteSettings].self, from: data)
        else { return [:] }
        return decoded
    }()

    static func entry(named name: String) -> SpriteEntry? {
        all.first { $0.name == name }
    }

    static func image(_ stem: String) -> UIImage? {
        guard let url = folder?.appendingPathComponent("\(stem).png") else { return nil }
        return UIImage(contentsOfFile: url.path)
    }

    // MARK: Frame fonts

    /// Must match safe() in tools/build_sprites.py
    static func fontID(_ name: String) -> String {
        let s = String(name.filter { $0.isASCII && ($0.isLetter || $0.isNumber) })
        return s.isEmpty ? "sprite" : s
    }

    static func animatedFont(_ name: String) -> String {
        "PocketPal-" + fontID(name)
    }

    static func motionFont(_ name: String, motion: String, stillFrame: Bool) -> String {
        "PocketPal-" + fontID(name) + "-" + motion + (stillFrame ? "-still" : "")
    }

    static let motions: [(label: String, value: String)] = [
        ("Stay still", "none"), ("Hop", "hop"), ("Wiggle", "wiggle"), ("Wander", "wander"),
    ]

    /// Registers the bundled frame fonts with this process (backup for UIAppFonts).
    static let fontsRegistered: Bool = {
        guard let dir = Bundle.main.resourceURL?.appendingPathComponent("Fonts", isDirectory: true),
              let files = try? FileManager.default.contentsOfDirectory(at: dir, includingPropertiesForKeys: nil)
        else { return false }
        for url in files where url.pathExtension.lowercased() == "ttf" {
            CTFontManagerRegisterFontsForURL(url as CFURL, .process, nil)
        }
        return true
    }()

    static func hasFont(_ fontName: String, size: CGFloat) -> Bool {
        _ = fontsRegistered
        return UIFont(name: fontName, size: size) != nil
    }
}

// MARK: - Drawing

/// Draws one PNG. Small (pixel-art) images stay crisp; larger ones scale smoothly.
struct SpriteImage: View {
    let image: UIImage?

    init(stem: String?) {
        image = stem.flatMap { Sprites.image($0) }
    }

    init(image: UIImage?) {
        self.image = image
    }

    var body: some View {
        if let image {
            Image(uiImage: image)
                .resizable()
                .interpolation(image.size.width <= 128 ? .none : .high)
                .scaledToFit()
        } else {
            Image(systemName: "questionmark.circle")
                .resizable()
                .scaledToFit()
                .foregroundStyle(.white)
        }
    }
}

/// The sprite as shown in the island, on the Lock Screen and in the in-app previews.
/// Animation and movement use the "frame font" trick: a live-ticking timer drawn in a font
/// whose digits are frames. The font hides every character except the last digit, so the
/// timer renders as one sprite that changes every second.
struct IslandSprite: View {
    let customPNG: Data?
    let state: PetAttributes.ContentState
    let size: CGFloat

    var body: some View {
        content
            .frame(width: size, height: size)
            .scaleEffect(CGFloat(state.zoom))
            .offset(x: CGFloat(state.offsetX) * size, y: CGFloat(state.offsetY) * size)
            .frame(width: size, height: size)
            .clipped()
    }

    @ViewBuilder private var content: some View {
        if let customPNG, let img = UIImage(data: customPNG) {
            SpriteImage(image: img)
        } else if let font = fontToUse() {
            Text(state.startDate, style: .timer)
                .font(.custom(font, fixedSize: size))
                .lineLimit(1)
                .multilineTextAlignment(.center)
        } else {
            SpriteImage(stem: Sprites.entry(named: state.spriteName)?.frames.first)
        }
    }

    private func fontToUse() -> String? {
        guard let entry = Sprites.entry(named: state.spriteName) else { return nil }
        let moving = state.motion != "none"
        var candidates: [String] = []
        if entry.isAnimated && state.animate {
            if moving { candidates.append(Sprites.motionFont(entry.name, motion: state.motion, stillFrame: false)) }
            candidates.append(Sprites.animatedFont(entry.name))
        } else if moving {
            candidates.append(Sprites.motionFont(entry.name, motion: state.motion, stillFrame: entry.isAnimated))
        }
        return candidates.first { Sprites.hasFont($0, size: size) }
    }
}

// MARK: - Right side of the island

enum TrailingOption {
    static let all: [(label: String, value: String)] = [
        ("Nothing", "none"),
        ("Pal's name", "name"),
        ("Time out together", "timer"),
        ("Sparkles", "sparkles"),
        ("Star", "star.fill"),
        ("Moon", "moon.fill"),
        ("Bolt", "bolt.fill"),
        ("Music", "music.note"),
        ("Paw", "pawprint.fill"),
        ("Flame", "flame.fill"),
        ("Leaf", "leaf.fill"),
        ("Crown", "crown.fill"),
        ("Gamepad", "gamecontroller.fill"),
        ("Heart", "heart.fill"),
    ]

    static func color(for symbol: String) -> Color {
        switch symbol {
        case "sparkles", "star.fill", "crown.fill", "bolt.fill": return .yellow
        case "moon.fill": return Color(red: 0.75, green: 0.75, blue: 1.0)
        case "music.note": return .cyan
        case "pawprint.fill", "flame.fill": return .orange
        case "leaf.fill": return .green
        case "gamecontroller.fill": return .purple
        case "heart.fill": return .pink
        default: return .white
        }
    }
}

struct TrailingView: View {
    let state: PetAttributes.ContentState

    var body: some View {
        switch state.trailing {
        case "none":
            EmptyView()
        case "name":
            Text(state.nickname.isEmpty ? state.spriteName.capitalized : state.nickname)
                .font(.caption2.bold())
                .lineLimit(1)
                .frame(maxWidth: 64)
        case "timer":
            Text(state.startDate, style: .timer)
                .font(.caption2.monospacedDigit().bold())
                .multilineTextAlignment(.center)
                .frame(maxWidth: 44)
        default:
            Image(systemName: state.trailing)
                .foregroundStyle(TrailingOption.color(for: state.trailing))
        }
    }
}
