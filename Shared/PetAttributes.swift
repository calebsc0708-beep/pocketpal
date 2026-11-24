import ActivityKit
import SwiftUI
import UIKit
import CoreText

/// Data the Live Activity carries. Shared by the app and the widget extension.
struct PetAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var spriteName: String
        var nickname: String
        var startDate: Date
        var animate: Bool
    }
}

/// One selectable sprite: either a single PNG ("mochi.png") or an animation
/// made of numbered frames ("mochi_1.png", "mochi_2.png", ...).
struct SpriteEntry: Identifiable, Hashable {
    let name: String
    let frames: [String]          // file stems, in order
    var id: String { name }
    var isAnimated: Bool { frames.count > 1 }
}

enum Sprites {
    private static var folder: URL? {
        Bundle.main.resourceURL?.appendingPathComponent("Sprites", isDirectory: true)
    }

    static func all() -> [SpriteEntry] {
        guard let folder,
              let files = try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)
        else { return [] }

        var singles: [String] = []
        var animated: [String: [(Int, String)]] = [:]
        for url in files where url.pathExtension.lowercased() == "png" {
            let stem = url.deletingPathExtension().lastPathComponent
            if let underscore = stem.lastIndex(of: "_"),
               let number = Int(stem[stem.index(after: underscore)...]),
               underscore != stem.startIndex {
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
    }

    static func entry(named name: String) -> SpriteEntry? {
        all().first { $0.name == name }
    }

    static func image(_ stem: String) -> UIImage? {
        guard let url = folder?.appendingPathComponent("\(stem).png") else { return nil }
        return UIImage(contentsOfFile: url.path)
    }

    /// Must match safe() in tools/make_fonts.py
    static func fontName(for name: String) -> String {
        let s = String(name.filter { $0.isASCII && ($0.isLetter || $0.isNumber) })
        return "PocketPal-" + (s.isEmpty ? "sprite" : s)
    }

    /// Which frame is showing at a given moment. Matches the font: digit d → frame d % count.
    static func frameIndex(at date: Date, since start: Date, count: Int) -> Int {
        let seconds = max(0, Int(date.timeIntervalSince(start)))
        return (seconds % 10) % max(count, 1)
    }
}

/// Draws one PNG with crisp (non-blurry) pixel scaling.
struct SpriteImage: View {
    let stem: String?

    var body: some View {
        if let stem, let img = Sprites.image(stem) {
            Image(uiImage: img)
                .resizable()
                .interpolation(.none)
                .scaledToFit()
        } else {
            Image(systemName: "questionmark.circle")
                .resizable()
                .scaledToFit()
        }
    }
}

extension Sprites {
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

    static func hasFont(for name: String, size: CGFloat) -> Bool {
        _ = fontsRegistered
        return UIFont(name: fontName(for: name), size: size) != nil
    }
}

/// Shows the sprite in the island / Lock Screen / in-app preview.
/// Animated sprites use the "frame font" trick: a live-ticking timer drawn in a
/// font whose digits are animation frames. The font hides every character except
/// the last digit, so the timer renders as a single sprite that changes each second.
struct IslandSprite: View {
    let state: PetAttributes.ContentState
    let size: CGFloat

    var body: some View {
        let entry = Sprites.entry(named: state.spriteName)

        if state.animate, let entry, entry.isAnimated, Sprites.hasFont(for: entry.name, size: size) {
            Text(state.startDate, style: .timer)
                .font(.custom(Sprites.fontName(for: entry.name), fixedSize: size))
                .lineLimit(1)
                .multilineTextAlignment(.center)
                .frame(width: size, height: size)
        } else {
            SpriteImage(stem: entry?.frames.first)
                .frame(width: size, height: size)
        }
    }
}
