import ActivityKit
import SwiftUI
import UIKit

/// Data the Live Activity carries. Shared by the app and the widget extension.
struct PetAttributes: ActivityAttributes {
    public struct ContentState: Codable, Hashable {
        var spriteName: String
        var nickname: String
        var startDate: Date
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
