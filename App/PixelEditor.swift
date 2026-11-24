import SwiftUI

struct PixelColor: Hashable {
    var r: Double, g: Double, b: Double

    init(_ color: Color) {
        var r: CGFloat = 0, g: CGFloat = 0, b: CGFloat = 0, a: CGFloat = 0
        UIColor(color).getRed(&r, green: &g, blue: &b, alpha: &a)
        self.r = Double(r); self.g = Double(g); self.b = Double(b)
    }

    var color: Color { Color(red: r, green: g, blue: b) }
    var uiColor: UIColor { UIColor(red: r, green: g, blue: b, alpha: 1) }
}

/// Draw your own sprite on a 16×16 or 32×32 grid, frame by frame.
struct PixelEditorView: View {
    @ObservedObject var store: CustomSpriteStore
    var onSaved: (String) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var gridSize = 16
    @State private var frames: [[PixelColor?]] = [Array(repeating: nil, count: 16 * 16)]
    @State private var current = 0
    @State private var color: Color = Color(red: 0.16, green: 0.12, blue: 0.24)
    @State private var erasing = false
    @State private var onion = true
    @State private var playing = false
    @State private var playFrame = 0
    @State private var name = "my sprite"
    @State private var shareItems: [URL] = []
    @State private var showShare = false

    private let palette: [Color] = [
        Color(red: 0.16, green: 0.12, blue: 0.24), .white, Color(white: 0.6),
        Color(red: 0.95, green: 0.3, blue: 0.3), Color(red: 1.0, green: 0.6, blue: 0.2),
        Color(red: 1.0, green: 0.85, blue: 0.3), Color(red: 0.45, green: 0.8, blue: 0.4),
        Color(red: 0.3, green: 0.75, blue: 0.95), Color(red: 0.4, green: 0.45, blue: 0.95),
        Color(red: 0.75, green: 0.55, blue: 0.95), Color(red: 1.0, green: 0.6, blue: 0.75),
        Color(red: 0.6, green: 0.4, blue: 0.25),
    ]

    private var shown: [PixelColor?] { playing ? frames[playFrame % frames.count] : frames[current] }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 14) {
                    canvas

                    // Frames
                    HStack {
                        Button { current = max(0, current - 1) } label: { Image(systemName: "chevron.left") }
                            .disabled(current == 0 || playing)
                        Text("Frame \(current + 1) of \(frames.count)").monospacedDigit()
                        Button { current = min(frames.count - 1, current + 1) } label: { Image(systemName: "chevron.right") }
                            .disabled(current == frames.count - 1 || playing)
                        Spacer()
                        Button { addFrame() } label: { Image(systemName: "plus.square.on.square") }
                            .disabled(playing || frames.count >= 10)
                        Button(role: .destructive) { deleteFrame() } label: { Image(systemName: "trash") }
                            .disabled(playing || frames.count == 1)
                        Button { playing.toggle(); playFrame = current } label: {
                            Image(systemName: playing ? "stop.fill" : "play.fill")
                        }
                        .disabled(frames.count == 1)
                    }
                    .buttonStyle(.bordered)

                    // Colors
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible()), count: 7), spacing: 8) {
                        ForEach(palette.indices, id: \.self) { i in
                            Circle().fill(palette[i])
                                .frame(width: 32, height: 32)
                                .overlay(Circle().stroke(.primary, lineWidth: !erasing && PixelColor(palette[i]) == PixelColor(color) ? 3 : 0.5))
                                .onTapGesture { color = palette[i]; erasing = false }
                        }
                        ColorPicker("", selection: $color, supportsOpacity: false)
                            .labelsHidden()
                            .onChange(of: color) { _, _ in erasing = false }
                        Image(systemName: "eraser.fill")
                            .frame(width: 32, height: 32)
                            .background(Circle().fill(erasing ? Color.accentColor.opacity(0.3) : Color.secondary.opacity(0.15)))
                            .onTapGesture { erasing = true }
                    }

                    Toggle("Show previous frame faintly", isOn: $onion)

                    TextField("Name", text: $name).textFieldStyle(.roundedBorder)

                    Button {
                        if let saved = store.save(render(frames[current]), name: name) {
                            onSaved(saved)
                            dismiss()
                        }
                    } label: {
                        Label("Use this frame as a sprite", systemImage: "checkmark.circle").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.borderedProminent)

                    Button { exportFrames() } label: {
                        Label("Export frames for animation", systemImage: "square.and.arrow.up").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(.bordered)

                    Text("Sprites made here appear in the island right away as a still image. To animate them, export the frames, add them to the Sprites folder on GitHub and rebuild. 2, 5 or 10 frames loop perfectly.")
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                }
                .padding()
            }
            .navigationTitle("Draw a Sprite")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
                ToolbarItem(placement: .primaryAction) {
                    Menu {
                        Button("New 16×16 canvas") { newCanvas(16) }
                        Button("New 32×32 canvas") { newCanvas(32) }
                    } label: { Image(systemName: "square.grid.3x3") }
                }
            }
            .task(id: playing) {
                while playing {
                    try? await Task.sleep(for: .seconds(1))
                    if playing { playFrame = (playFrame + 1) % frames.count }
                }
            }
            .sheet(isPresented: $showShare) { ActivityView(items: shareItems) }
        }
    }

    private var canvas: some View {
        GeometryReader { geo in
            let side = min(geo.size.width, geo.size.height)
            let cell = side / CGFloat(gridSize)
            Canvas { ctx, _ in
                for y in 0..<gridSize {
                    for x in 0..<gridSize {
                        let rect = CGRect(x: CGFloat(x) * cell, y: CGFloat(y) * cell, width: cell, height: cell)
                        let i = y * gridSize + x
                        ctx.fill(Path(rect), with: .color((x + y) % 2 == 0 ? Color(white: 0.82) : Color(white: 0.92)))
                        if onion, !playing, current > 0, let c = frames[current - 1][i] {
                            ctx.fill(Path(rect), with: .color(c.color.opacity(0.3)))
                        }
                        if let c = shown[i] {
                            ctx.fill(Path(rect), with: .color(c.color))
                        }
                    }
                }
            }
            .frame(width: side, height: side)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { value in
                guard !playing else { return }
                let x = Int(value.location.x / cell), y = Int(value.location.y / cell)
                guard (0..<gridSize).contains(x), (0..<gridSize).contains(y) else { return }
                frames[current][y * gridSize + x] = erasing ? nil : PixelColor(color)
            })
        }
        .aspectRatio(1, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func newCanvas(_ size: Int) {
        gridSize = size
        frames = [Array(repeating: nil, count: size * size)]
        current = 0
        playing = false
    }

    private func addFrame() {
        frames.insert(frames[current], at: current + 1)  // start from a copy of this frame
        current += 1
    }

    private func deleteFrame() {
        frames.remove(at: current)
        current = min(current, frames.count - 1)
    }

    private func render(_ pixels: [PixelColor?]) -> UIImage {
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = false
        let size = CGSize(width: gridSize, height: gridSize)
        return UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            for y in 0..<gridSize {
                for x in 0..<gridSize {
                    if let c = pixels[y * gridSize + x] {
                        c.uiColor.setFill()
                        ctx.fill(CGRect(x: x, y: y, width: 1, height: 1))
                    }
                }
            }
        }
    }

    private func exportFrames() {
        let base = String(name.filter { $0.isASCII && ($0.isLetter || $0.isNumber) }).lowercased()
        let fileBase = base.isEmpty ? "sprite" : base
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("Export-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        var urls: [URL] = []
        for (i, frame) in frames.enumerated() {
            // Upscale 4x with hard edges so the files look right in any viewer
            let big = ImageTools.resize(render(frame), side: gridSize * 4, smooth: false)
            let file = frames.count == 1 ? "\(fileBase).png" : "\(fileBase)_\(i + 1).png"
            let url = dir.appendingPathComponent(file)
            if let data = big.pngData(), (try? data.write(to: url)) != nil { urls.append(url) }
        }
        shareItems = urls
        showShare = !urls.isEmpty
    }
}
