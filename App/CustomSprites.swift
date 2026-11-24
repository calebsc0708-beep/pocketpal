import SwiftUI
import PhotosUI
import Vision
import CoreImage
import ImageIO

// MARK: - Image helpers

enum ImageTools {
    private static var format: UIGraphicsImageRendererFormat {
        let f = UIGraphicsImageRendererFormat()
        f.scale = 1
        f.opaque = false
        return f
    }

    /// Redraws upright (fixes photo rotation) and shrinks big photos.
    static func normalized(_ image: UIImage, maxSide: CGFloat = 1024) -> UIImage {
        let k = min(1, maxSide / max(image.size.width, image.size.height))
        let size = CGSize(width: max(1, (image.size.width * k).rounded()),
                          height: max(1, (image.size.height * k).rounded()))
        return UIGraphicsImageRenderer(size: size, format: format).image { _ in
            image.draw(in: CGRect(origin: .zero, size: size))
        }
    }

    /// iOS's built-in subject cutout (same as long-pressing a photo). Returns nil if no subject is found.
    static func liftSubject(_ image: UIImage) -> UIImage? {
        guard let cg = image.cgImage else { return nil }
        let request = VNGenerateForegroundInstanceMaskRequest()
        let handler = VNImageRequestHandler(cgImage: cg, options: [:])
        do {
            try handler.perform([request])
            guard let observation = request.results?.first else { return nil }
            let buffer = try observation.generateMaskedImage(
                ofInstances: observation.allInstances, from: handler, croppedToInstancesExtent: true)
            let ci = CIImage(cvPixelBuffer: buffer)
            guard let out = CIContext().createCGImage(ci, from: ci.extent) else { return nil }
            return UIImage(cgImage: out)
        } catch {
            return nil
        }
    }

    /// Trims transparent edges, then centers on a square canvas (sitting on the bottom edge).
    static func trimAndSquare(_ image: UIImage) -> UIImage {
        guard let cg = image.cgImage else { return image }
        let w = cg.width, h = cg.height
        var minX = w, minY = h, maxX = -1, maxY = -1
        var pixels = [UInt8](repeating: 0, count: w * h * 4)
        pixels.withUnsafeMutableBytes { buffer in
            guard let ctx = CGContext(data: buffer.baseAddress, width: w, height: h, bitsPerComponent: 8,
                                      bytesPerRow: w * 4, space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return }
            ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
        }
        for y in 0..<h {
            for x in 0..<w where pixels[(y * w + x) * 4 + 3] > 16 {
                minX = min(minX, x); maxX = max(maxX, x)
                minY = min(minY, y); maxY = max(maxY, y)
            }
        }
        guard maxX >= minX, maxY >= minY,
              let cropped = cg.cropping(to: CGRect(x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1))
        else { return image }
        let cw = CGFloat(cropped.width), ch = CGFloat(cropped.height)
        let side = max(cw, ch)
        return UIGraphicsImageRenderer(size: CGSize(width: side, height: side), format: format).image { _ in
            UIImage(cgImage: cropped).draw(in: CGRect(x: (side - cw) / 2, y: side - ch, width: cw, height: ch))
        }
    }

    /// Bounding box of non-transparent pixels (top-left origin), or nil if fully transparent.
    static func alphaBox(_ cg: CGImage) -> CGRect? {
        let w = cg.width, h = cg.height
        var pixels = [UInt8](repeating: 0, count: w * h * 4)
        pixels.withUnsafeMutableBytes { buffer in
            guard let ctx = CGContext(data: buffer.baseAddress, width: w, height: h, bitsPerComponent: 8,
                                      bytesPerRow: w * 4, space: CGColorSpaceCreateDeviceRGB(),
                                      bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue) else { return }
            ctx.draw(cg, in: CGRect(x: 0, y: 0, width: w, height: h))
        }
        var minX = w, minY = h, maxX = -1, maxY = -1
        for y in 0..<h {
            for x in 0..<w where pixels[(y * w + x) * 4 + 3] > 16 {
                minX = min(minX, x); maxX = max(maxX, x)
                minY = min(minY, y); maxY = max(maxY, y)
            }
        }
        guard maxX >= minX, maxY >= minY else { return nil }
        return CGRect(x: minX, y: minY, width: maxX - minX + 1, height: maxY - minY + 1)
    }

    /// Trims all frames with ONE shared box (so they don't jitter), then squares them.
    static func trimTogether(_ images: [UIImage]) -> [UIImage] {
        let cgs = images.compactMap(\.cgImage)
        let boxes = cgs.compactMap(alphaBox)
        guard let first = boxes.first else { return images }
        let box = boxes.dropFirst().reduce(first) { $0.union($1) }
        return cgs.compactMap { $0.cropping(to: box) }.map { cropped in
            let cw = CGFloat(cropped.width), ch = CGFloat(cropped.height)
            let side = max(cw, ch)
            return UIGraphicsImageRenderer(size: CGSize(width: side, height: side), format: format).image { _ in
                UIImage(cgImage: cropped).draw(in: CGRect(x: (side - cw) / 2, y: side - ch, width: cw, height: ch))
            }
        }
    }

    /// Splits an animated GIF into 2, 5 or 10 evenly spaced frames (whichever loops cleanly).
    /// Returns nil if the data isn't an animated image.
    static func gifFrames(_ data: Data) -> [UIImage]? {
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else { return nil }
        let count = CGImageSourceGetCount(source)
        guard count > 1 else { return nil }
        let keep = count >= 10 ? 10 : (count >= 5 ? 5 : 2)
        let frames = (0..<keep).compactMap { i -> UIImage? in
            guard let cg = CGImageSourceCreateImageAtIndex(source, i * count / keep, nil) else { return nil }
            return normalized(UIImage(cgImage: cg), maxSide: 512)
        }
        return frames.count > 1 ? trimTogether(frames) : nil
    }

    static func resize(_ image: UIImage, side: Int, smooth: Bool) -> UIImage {
        let size = CGSize(width: side, height: side)
        return UIGraphicsImageRenderer(size: size, format: format).image { ctx in
            ctx.cgContext.interpolationQuality = smooth ? .high : .none
            image.draw(in: CGRect(origin: .zero, size: size))
        }
    }

    /// Shrinks to a small grid so it looks like pixel art (shown crisp, not blurry).
    static func pixelate(_ image: UIImage, grid: Int) -> UIImage {
        resize(image, side: grid, smooth: true)
    }

    /// A PNG small enough to ride along inside the Live Activity (about 4 KB limit in total).
    static func islandPNG(_ image: UIImage) -> Data? {
        let pixelArt = image.size.width <= 64
        for side in [64, 56, 48, 40, 32, 24] {
            let img = Int(image.size.width) <= side ? image : resize(image, side: side, smooth: !pixelArt)
            if let data = img.pngData(), data.count <= 2400 { return data }
        }
        return nil
    }
}

// MARK: - Sprites added in the app (saved on the phone)

struct CustomSprite: Identifiable, Hashable {
    let name: String
    let url: URL
    var id: String { name }
}

@MainActor
final class CustomSpriteStore: ObservableObject {
    @Published private(set) var sprites: [CustomSprite] = []
    private let folder: URL

    init() {
        folder = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("CustomSprites", isDirectory: true)
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        reload()
    }

    func reload() {
        let files = (try? FileManager.default.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? []
        sprites = files
            .filter { $0.pathExtension.lowercased() == "png" }
            .map { CustomSprite(name: $0.deletingPathExtension().lastPathComponent, url: $0) }
            .sorted { $0.name.localizedCaseInsensitiveCompare($1.name) == .orderedAscending }
    }

    func sprite(named name: String) -> CustomSprite? {
        sprites.first { $0.name == name }
    }

    func image(_ sprite: CustomSprite) -> UIImage? {
        UIImage(contentsOfFile: sprite.url.path)
    }

    @discardableResult
    func save(_ image: UIImage, name: String) -> String? {
        var base = String(name.filter { $0.isLetter || $0.isNumber || $0 == " " || $0 == "-" })
            .trimmingCharacters(in: .whitespaces)
        if base.isEmpty { base = "sprite" }
        var final = base, n = 2
        while sprites.contains(where: { $0.name == final }) { final = "\(base) \(n)"; n += 1 }
        guard let data = image.pngData() else { return nil }
        do {
            try data.write(to: folder.appendingPathComponent("\(final).png"))
            reload()
            return final
        } catch {
            return nil
        }
    }

    func delete(_ sprite: CustomSprite) {
        try? FileManager.default.removeItem(at: sprite.url)
        reload()
    }
}

// MARK: - Import from Photos

struct ImportSpriteView: View {
    @ObservedObject var store: CustomSpriteStore
    var onSaved: (String) -> Void
    @Environment(\.dismiss) private var dismiss

    @State private var item: PhotosPickerItem?
    @State private var original: UIImage?
    @State private var cutout: UIImage?
    @State private var cutoutFailed = false
    @State private var working = false
    @State private var removeBackground = true
    @State private var pixelate = false
    @State private var grid = 32.0
    @State private var name = ""
    @State private var gif: [UIImage] = []
    @State private var shareItems: [URL] = []
    @State private var showShare = false

    private var result: UIImage? {
        guard let base = (removeBackground ? cutout : nil) ?? original else { return nil }
        let squared = ImageTools.trimAndSquare(base)
        return pixelate ? ImageTools.pixelate(squared, grid: Int(grid)) : squared
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    PhotosPicker(selection: $item, matching: .images) {
                        Label(original == nil ? "Choose a photo" : "Choose a different photo", systemImage: "photo")
                    }
                }

                if gif.count > 1 {
                    Section {
                        ScrollView(.horizontal, showsIndicators: false) {
                            HStack(spacing: 8) {
                                ForEach(gif.indices, id: \.self) { i in
                                    VStack(spacing: 4) {
                                        SpriteImage(image: gif[i])
                                            .padding(6)
                                            .frame(width: 72, height: 72)
                                            .background(RoundedRectangle(cornerRadius: 10).fill(.black))
                                        Text("\(i + 1)").font(.caption2).foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                        Button { exportGIF() } label: {
                            Label("Export \(gif.count) frames for GitHub", systemImage: "square.and.arrow.up")
                        }
                    } header: {
                        Text("GIF: \(gif.count) frames")
                    } footer: {
                        Text("Save these to Files, then upload them to the Sprites folder on GitHub to animate in the island. Solid backgrounds are removed during the build. Below, you can also save frame 1 as a still sprite right now.")
                    }
                }

                if original != nil {
                    Section("Preview") {
                        HStack {
                            Spacer()
                            ZStack {
                                RoundedRectangle(cornerRadius: 16).fill(.black)
                                if working {
                                    ProgressView().tint(.white)
                                } else {
                                    SpriteImage(image: result).padding(10)
                                }
                            }
                            .frame(width: 160, height: 160)
                            Spacer()
                        }
                    }

                    Section {
                        Toggle("Remove background", isOn: $removeBackground)
                        if removeBackground && cutoutFailed {
                            Text("Couldn't find a subject in this photo, so the background stays.")
                                .font(.footnote).foregroundStyle(.secondary)
                        }
                        Toggle("Pixelate", isOn: $pixelate)
                        if pixelate {
                            VStack(alignment: .leading) {
                                Text("Pixel size: \(Int(grid))×\(Int(grid))")
                                Slider(value: $grid, in: 12...48, step: 4)
                            }
                        }
                        TextField("Name", text: $name)
                    } footer: {
                        Text("Empty space is trimmed automatically. Use “Fit in island” on the main screen to zoom or nudge it.")
                    }
                }
            }
            .navigationTitle("Import Sprite")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        if let img = result, let saved = store.save(img, name: name) {
                            onSaved(saved)
                            dismiss()
                        }
                    }
                    .disabled(result == nil || working)
                }
            }
            .onChange(of: item) { _, newItem in
                Task { await load(newItem) }
            }
            .sheet(isPresented: $showShare) { ActivityView(items: shareItems) }
        }
    }

    private func load(_ newItem: PhotosPickerItem?) async {
        guard let newItem,
              let data = try? await newItem.loadTransferable(type: Data.self),
              let raw = UIImage(data: data) else { return }
        gif = ImageTools.gifFrames(data) ?? []
        let image = ImageTools.normalized(gif.first ?? raw)
        original = image
        cutout = nil
        cutoutFailed = false
        if name.isEmpty { name = "sprite" }
        working = true
        let lifted = await Task.detached(priority: .userInitiated) { ImageTools.liftSubject(image) }.value
        cutout = lifted
        cutoutFailed = lifted == nil
        working = false
    }

    private func exportGIF() {
        let cleaned = String(name.filter { $0.isASCII && ($0.isLetter || $0.isNumber) }).lowercased()
        let base = cleaned.isEmpty || cleaned == "sprite" ? "gifpal" : cleaned
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("GIF-\(UUID().uuidString)")
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        var urls: [URL] = []
        for (i, frame) in gif.enumerated() {
            let url = dir.appendingPathComponent("\(base)_\(i + 1).png")
            if let data = frame.pngData(), (try? data.write(to: url)) != nil { urls.append(url) }
        }
        shareItems = urls
        showShare = !urls.isEmpty
    }
}

// MARK: - Share sheet

struct ActivityView: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: items, applicationActivities: nil)
    }

    func updateUIViewController(_ controller: UIActivityViewController, context: Context) {}
}
