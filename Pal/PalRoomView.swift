import SwiftUI

// MARK: - Wandering brain

/// Moves the pal around the room's floor. All positions are in room pixels
/// (the room art is 256 x 160), measured at the pal's feet.
@MainActor
final class PalWanderer: ObservableObject {
    static let roomSize = CGSize(width: 256, height: 160)
    /// Walkable floor: in front of the desk/window seat, left of the bed.
    static let floor = CGRect(x: 44, y: 110, width: 116, height: 36)

    @Published private(set) var position = CGPoint(x: 100, y: 130)
    @Published private(set) var showingBack = false   // true while walking away from the viewer
    @Published private(set) var flipped = false       // mirror the artwork horizontally
    @Published private(set) var isWalking = false
    /// Which pal's art to use for facing decisions.
    var species: PalSpecies = .eevee

    private var target: CGPoint?
    private var idleUntil = Date().addingTimeInterval(1.5)
    private var lastTick = Date()

    /// Walking speed in room pixels per second (slower at the back of the room, for depth).
    private let baseSpeed: CGFloat = 18

    /// How big the pal is drawn relative to the room art; it shrinks as it walks toward the back wall.
    var depthScale: CGFloat {
        let t = (position.y - Self.floor.minY) / Self.floor.height   // 0 = back wall, 1 = front
        // (52/68 keeps pals at the same size as before the canvas grew to fit bigger sprites)
        return (0.48 + 0.16 * max(0, min(1, t))) * 52 / 68
    }

    func tick(_ now: Date) {
        let dt = min(now.timeIntervalSince(lastTick), 0.1)
        lastTick = now

        guard let target else {
            if now >= idleUntil { pickTarget() }
            return
        }

        let dx = target.x - position.x, dy = target.y - position.y
        let dist = hypot(dx, dy)
        let step = baseSpeed * (0.6 + 0.4 * depthScale / (0.64 * 52 / 68)) * CGFloat(dt)

        if dist <= step {
            position = target
            arrive(now)
        } else {
            position.x += dx / dist * step
            position.y += dy / dist * step
        }
    }

    private func pickTarget() {
        let f = Self.floor
        var t: CGPoint
        repeat {
            t = CGPoint(x: .random(in: f.minX...f.maxX), y: .random(in: f.minY...f.maxY))
        } while hypot(t.x - position.x, t.y - position.y) < 25   // avoid tiny shuffles
        target = t
        isWalking = true
        face(dx: t.x - position.x, dy: t.y - position.y)
    }

    private func arrive(_ now: Date) {
        target = nil
        isWalking = false
        idleUntil = now.addingTimeInterval(.random(in: 2.5...6))
        // Turn back around to face the viewer while idling.
        if showingBack {
            showingBack = false
            flipped = needsFlip(movingRight: flippedMovingRight, clip: species.front)
        }
    }

    private var flippedMovingRight = false

    /// Decide which clip and which way to mirror, from the direction of travel.
    private func face(dx: CGFloat, dy: CGFloat) {
        // Walking away from the viewer (toward the back wall) -> show the back.
        // A small backward drift while mostly walking sideways still uses the front.
        showingBack = dy < 0 && abs(dy) >= abs(dx) * 0.25
        let movingRight = dx > 0
        flippedMovingRight = movingRight
        flipped = needsFlip(movingRight: movingRight, clip: showingBack ? species.back : species.front)
    }

    private func needsFlip(movingRight: Bool, clip: PalClip) -> Bool {
        switch clip.naturalFacing {
        case .left:  return movingRight     // art faces left, mirror it to walk right
        case .right: return !movingRight    // art faces right, mirror it to walk left
        }
    }
}

// MARK: - Room view

/// The room background, its animated details, and the wandering, animated pal.
struct PalRoomView: View {
    var time: RoomTime = .day
    var weather: RoomWeather = .clear
    /// When true the pal is asleep under the covers with Zs floating up (at night).
    var asleep: Bool = false
    var species: PalSpecies = .eevee
    @StateObject private var pal = PalWanderer()
    private let start = Date()

    var body: some View {
        TimelineView(.animation) { context in
            GeometryReader { geo in
                let scale = geo.size.width / PalWanderer.roomSize.width
                let clip = pal.showingBack ? species.back : species.front
                let frame = clip.frame(at: context.date.timeIntervalSince(start))
                let side = CGFloat(clip.size) * pal.depthScale * scale
                let t = context.date.timeIntervalSince(start)
                let walkHop: CGFloat = pal.isWalking ? CGFloat(abs(sin(t * 9))) * 1.5 * scale : 0

                ZStack(alignment: .topLeading) {
                    Image(time.roomImage(weather))
                        .resizable()
                        .interpolation(.none)
                        .frame(width: geo.size.width, height: geo.size.height)

                    PalRoomAmbience(time: time, weather: weather, t: t, palAsleep: asleep)
                        .frame(width: geo.size.width, height: geo.size.height)

                    if asleep {
                        PalSleepLayer(time: time, weather: weather, t: t, scale: scale)
                            .frame(width: geo.size.width, height: geo.size.height)
                    }

                    if !asleep {
                    Image(frame.image)
                        .resizable()
                        .interpolation(.none)
                        .frame(width: side, height: side)
                        .scaleEffect(x: pal.flipped ? -1 : 1, y: 1)
                        // Little hop while walking.
                        .offset(y: -walkHop)
                        // Anchor at the feet (bottom-center of the frame).
                        .position(x: pal.position.x * scale, y: pal.position.y * scale - side / 2)
                    }

                }
                .onChange(of: context.date) { _, now in
                    pal.species = species
                    if !asleep { pal.tick(now) }
                }
            }
            .aspectRatio(PalWanderer.roomSize, contentMode: .fit)
        }
    }
}

#Preview {
    PalRoomView(time: .night, weather: .storm)
}

/// The pal asleep completely under the covers: a lump in the quilt that rises and falls
/// as it breathes (two per-room overlays at room resolution), with Zs drifting up.
/// Coordinates are room pixels.
struct PalSleepLayer: View {
    let time: RoomTime
    let weather: RoomWeather
    let t: Double
    let scale: CGFloat

    static let lumpX: CGFloat = 205
    static let coversOrigin = CGPoint(x: 160, y: 90), coversSize = CGSize(width: 96, height: 70)

    var body: some View {
        let breath = sin(t * 1.6) > 0 ? 1 : 0
        ZStack(alignment: .topLeading) {
            Image("covers\(breath)_\(time.rawValue)_\(weather.rawValue)")
                .resizable()
                .interpolation(.none)
                .frame(width: Self.coversSize.width * scale, height: Self.coversSize.height * scale)
                .position(x: (Self.coversOrigin.x + Self.coversSize.width / 2) * scale,
                          y: (Self.coversOrigin.y + Self.coversSize.height / 2) * scale)

            Canvas { ctx, _ in
                for i in 0..<3 {
                    let p = (t / 3 + Double(i) / 3).truncatingRemainder(dividingBy: 1)
                    let size = 2 + i % 2 + Int((p * 2).rounded())
                    let x = Double(Self.lumpX) + 6 + (p * 10 + sin(p * 6 + Double(i)) * 1.5).rounded()
                    let y = 88 - (p * 22).rounded()
                    let a = min(1, p / 0.15) * min(1, (1 - p) / 0.3)
                    let color = Color(red: 1, green: 248 / 255, blue: 225 / 255).opacity(a)
                    func px(_ px: Double, _ py: Double) {
                        ctx.fill(Path(CGRect(x: px * scale, y: py * scale, width: scale, height: scale)), with: .color(color))
                    }
                    for k in 0...size {           // Z: top bar, diagonal, bottom bar
                        let k = Double(k), sz = Double(size)
                        px(x + k, y); px(x + k, y + sz); px(x + sz - k, y + k)
                    }
                }
            }
            .allowsHitTesting(false)
        }
    }
}
