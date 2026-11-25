import CoreGraphics

/// Things the pal does around the room. Shared by the app (it walks there) and the widget
/// (it shows one, switching every 5 minutes). Coordinates are room pixels at the pal's feet.
struct PalActivity: Equatable {
    let name: String
    /// Back view (facing away from you) or front view.
    let back: Bool
    /// Mirror the art. Front art faces left and back art faces right, so flip to face the other way.
    let flip: Bool
    /// Where it stands or sits while doing the activity.
    let perch: CGPoint
    /// Floor point it walks to first; it hops up from here when the perch is up on furniture.
    let floor: CGPoint
    /// Size of the pal's 68 px canvas in room px (smaller further from you).
    let size: CGFloat

    var isUp: Bool { perch != floor }

    static let window = PalActivity(name: "Looking out the window", back: true, flip: false,
                                    perch: CGPoint(x: 86, y: 79), floor: CGPoint(x: 86, y: 112), size: 30)
    static let music = PalActivity(name: "Listening to music", back: false, flip: true,
                                   perch: CGPoint(x: 113, y: 113), floor: CGPoint(x: 113, y: 113), size: 33)
    static let fish = PalActivity(name: "Watching the fish", back: true, flip: false,
                                  perch: CGPoint(x: 205, y: 99), floor: CGPoint(x: 158, y: 124), size: 30)
    /// Hanging out on the rug: a few spots so it doesn't always sit in the same place.
    static let rug = [
        PalActivity(name: "Hanging out on the rug", back: false, flip: false,
                    perch: CGPoint(x: 96, y: 132), floor: CGPoint(x: 96, y: 132), size: 34),
        PalActivity(name: "Hanging out on the rug", back: false, flip: true,
                    perch: CGPoint(x: 122, y: 128), floor: CGPoint(x: 122, y: 128), size: 34),
        PalActivity(name: "Hanging out on the rug", back: false, flip: false,
                    perch: CGPoint(x: 78, y: 126), floor: CGPoint(x: 78, y: 126), size: 34),
    ]

    /// The activity for a 5-minute slot. Neighbouring slots always differ.
    static func forSlot(_ slot: Int) -> PalActivity {
        let order: [PalActivity?] = [.window, nil, .music, .fish]   // nil = the rug
        let pick = order[((slot % order.count) + order.count) % order.count]
        return pick ?? rug[((slot / order.count) % rug.count + rug.count) % rug.count]
    }
}
