import SwiftUI

/// You, the trainer who throws the berries. Picked in Settings.
enum TrainerStyle: String, CaseIterable, Codable, Identifiable {
    case male, female
    var id: String { rawValue }
    var displayName: String { self == .male ? "Boy" : "Girl" }

    /// Asset name for a pose: idle, windup or throw.
    func image(_ pose: String) -> String { "trainer_\(self == .male ? "m" : "f")_\(pose)" }

    /// Each sheet has its own canvas; poses are lined up on the hips.
    var canvas: CGSize { self == .male ? CGSize(width: 82, height: 126) : CGSize(width: 90, height: 128) }
    var hipX: CGFloat { self == .male ? 54 : 55 }
    /// Where the berry sits in the windup frame (the spot the ball was in the original art).
    var handInWindup: CGPoint { self == .male ? CGPoint(x: 41.5, y: 12.5) : CGPoint(x: 40.5, y: 19) }
}

/// One berry throw. Start it when the player feeds the pal.
struct FeedingEvent: Identifiable, Equatable {
    let id = UUID()
    let food: Food
    let trainer: TrainerStyle
    let start = Date()

    // Timeline in seconds (matches the preview GIF).
    static let inEnd = 0.30, windEnd = 0.55, land = 1.25, eatEnd = 1.85, outStart = 1.6, outEnd = 1.9
    static let duration = 2.2

    func elapsed(_ now: Date) -> Double { now.timeIntervalSince(start) }
    func isFinished(_ now: Date) -> Bool { elapsed(now) >= Self.duration }

    /// How high the pal hops when the berry lands (room px).
    func palHop(_ now: Date) -> CGFloat {
        let t = elapsed(now)
        guard t >= Self.land, t < Self.land + 0.25 else { return 0 }
        return sin((t - Self.land) / 0.25 * .pi) * 4
    }
}

/// Draws the trainer sliding in half out of frame on the right, winding up, throwing the berry
/// in an arc to the pal, the pal eating it in three bites, and little hearts. Room-pixel coordinates.
struct PalFeedingLayer: View {
    let event: FeedingEvent
    let now: Date
    let time: RoomTime
    let weather: RoomWeather
    let scale: CGFloat
    /// Pal's feet position and drawn size in room px (from the wanderer).
    let palPosition: CGPoint
    let palSide: CGFloat

    static let trainerScale: CGFloat = 1.4        // trainer sprite px -> room px: fills the frame top to bottom
    static let standX: CGFloat = 262              // where the hips sit: about half the trainer is off-screen
    static let bottom: CGFloat = 172              // bottom of the art runs off the frame
    static let slide: CGFloat = 90                // how far he slides in from off-screen
    static let arc: CGFloat = 14                  // berry arc height
    static let berryInHand: CGFloat = 0.55, berryAtPal: CGFloat = 0.4

    private struct FeedLayout {
        var t: Double
        var tint: Color
        var pose: String
        var left: CGFloat, top: CGFloat, trainerW: CGFloat, trainerH: CGFloat
        var berryPos: CGPoint?, berrySize: CGFloat, berrySpin: Double
    }

    private var layout: FeedLayout {
        let t = event.elapsed(now)
        let look = RoomLook.of(time, weather)
        let tint = Color(red: look.trainerTint.0, green: look.trainerTint.1, blue: look.trainerTint.2)

        // trainer placement (room px)
        let style = event.trainer
        let ts = Self.trainerScale
        var slide: CGFloat = 0
        if t < FeedingEvent.inEnd {
            let k = CGFloat(1 - t / FeedingEvent.inEnd)
            slide = k * k * Self.slide
        } else if t > FeedingEvent.outStart {
            let k = CGFloat((t - FeedingEvent.outStart) / (FeedingEvent.outEnd - FeedingEvent.outStart))
            slide = k * k * Self.slide
        }
        let left: CGFloat = Self.standX + slide - style.hipX * ts
        let top: CGFloat = Self.bottom - style.canvas.height * ts
        let pose: String
        if t >= FeedingEvent.inEnd && t < FeedingEvent.windEnd { pose = "windup" }
        else if t >= FeedingEvent.windEnd && t < 1.0 { pose = "throw" }
        else { pose = "idle" }
        let trainerW: CGFloat = style.canvas.width * ts
        let trainerH: CGFloat = style.canvas.height * ts

        // berry: in hand, flying in an arc, then eaten in three bites
        let hand = CGPoint(x: left + style.handInWindup.x * ts, y: top + style.handInWindup.y * ts)
        let mouth = CGPoint(x: palPosition.x + 4, y: palPosition.y - palSide * 0.45)
        var berryPos: CGPoint? = nil
        var berrySize: CGFloat = Self.berryAtPal
        var berrySpin: Double = 0
        if t >= FeedingEvent.inEnd && t < FeedingEvent.windEnd {
            berryPos = hand
            berrySize = Self.berryInHand
        } else if t >= FeedingEvent.windEnd && t < FeedingEvent.land {
            let p = CGFloat((t - FeedingEvent.windEnd) / (FeedingEvent.land - FeedingEvent.windEnd))
            let lift: CGFloat = CGFloat(sin(Double(p) * .pi)) * Self.arc
            berryPos = CGPoint(x: hand.x + (mouth.x - hand.x) * p, y: hand.y + (mouth.y - hand.y) * p - lift)
            berrySize = Self.berryInHand + (Self.berryAtPal - Self.berryInHand) * p
            berrySpin = -t * 720
        } else if t >= FeedingEvent.land && t < FeedingEvent.eatEnd {
            let bites = CGFloat(floor((t - FeedingEvent.land) / (FeedingEvent.eatEnd - FeedingEvent.land) * 3))
            berryPos = CGPoint(x: mouth.x, y: mouth.y + 2)
            berrySize = Self.berryAtPal * (1 - bites / 3.2)
        }

        return FeedLayout(t: t, tint: tint, pose: pose, left: left, top: top, trainerW: trainerW, trainerH: trainerH,
                      berryPos: berryPos, berrySize: berrySize, berrySpin: berrySpin)
    }

    var body: some View {
        let L = layout
        let t = L.t
        ZStack(alignment: .topLeading) {
            if t < FeedingEvent.outEnd {
                Image(event.trainer.image(L.pose))
                    .resizable()
                    .interpolation(.none)
                    .colorMultiply(L.tint)
                    .frame(width: L.trainerW * scale, height: L.trainerH * scale)
                    .position(x: (L.left + L.trainerW / 2) * scale, y: (L.top + L.trainerH / 2) * scale)
            }
            if let pos = L.berryPos {
                Image(event.food.imageName)
                    .resizable()
                    .interpolation(.none)
                    .frame(width: 36 * L.berrySize * scale, height: 36 * L.berrySize * scale)
                    .rotationEffect(.degrees(L.berrySpin))
                    .position(x: pos.x * scale, y: pos.y * scale)
            }
            // hearts floating up while it eats
            if t >= FeedingEvent.land + 0.1 && t < FeedingEvent.eatEnd + 0.3 {
                let p = (t - FeedingEvent.land - 0.1) / 0.8
                Canvas { ctx, _ in
                    let heart: [(Double, Double)] = [(0, 0), (2, 0), (-1, 1), (0, 1), (1, 1), (2, 1), (3, 1), (0, 2), (1, 2), (2, 2), (1, 3)]
                    for (i, ox) in [-6.0, 4.0].enumerated() {
                        let hx = Double(palPosition.x) + ox
                        let hy = Double(palPosition.y - palSide) - 2 - p * 12 - Double(i) * 3
                        for (dx, dy) in heart {
                            ctx.fill(Path(CGRect(x: (hx + dx) * scale, y: (hy + dy) * scale, width: scale, height: scale)),
                                     with: .color(Color(red: 246 / 255, green: 120 / 255, blue: 150 / 255)))
                        }
                    }
                }
                .allowsHitTesting(false)
            }
        }
    }
}
