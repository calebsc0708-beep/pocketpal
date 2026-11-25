import SwiftUI

/// Cozy pixel-style colors and font shared by the app's screens.
enum PalTheme {
    static let ink = Color(red: 92 / 255, green: 62 / 255, blue: 66 / 255)
    static let cream = Color(red: 1, green: 250 / 255, blue: 240 / 255)
    static let paper = Color(red: 252 / 255, green: 243 / 255, blue: 230 / 255)
    static let shadow = Color(red: 232 / 255, green: 212 / 255, blue: 196 / 255)
    static let pink = Color(red: 246 / 255, green: 150 / 255, blue: 170 / 255)
    static let pinkLight = Color(red: 1, green: 210 / 255, blue: 218 / 255)

    /// Pixelify Sans (bundled; add the .ttf files to the target and list them under
    /// "Fonts provided by application" in Info.plist). Falls back to the system font.
    static func font(_ size: CGFloat, bold: Bool = false) -> Font {
        .custom(bold ? "PixelifySans-Bold" : "PixelifySans-Regular", size: size)
    }
}

/// A rounded card with a brown pixel-style border and a soft drop shadow.
struct PalCard<Content: View>: View {
    var fill: Color = PalTheme.cream
    @ViewBuilder var content: Content

    var body: some View {
        content
            .background(RoundedRectangle(cornerRadius: 14).fill(fill))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(PalTheme.ink, lineWidth: 3))
            .background(RoundedRectangle(cornerRadius: 14).fill(PalTheme.shadow).offset(y: 4))
    }
}

/// One animated pal sprite (front view), crisp at any size.
struct PalSpriteView: View {
    let species: PalSpecies
    var size: CGFloat = 96

    var body: some View {
        TimelineView(.animation) { context in
            let frame = species.front.frame(at: context.date.timeIntervalSinceReferenceDate)
            Image(frame.image)
                .resizable()
                .interpolation(.none)
                .frame(width: size, height: size)
        }
    }
}

/// "Choose your pal" screen: animated cards, tap one to pick it.
struct PalPickerView: View {
    @ObservedObject var settings: PalSettings = .shared
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                Text("Choose your pal")
                    .font(PalTheme.font(30, bold: true))
                    .foregroundStyle(PalTheme.ink)

                ForEach(PalSpecies.allCases) { species in
                    let selected = settings.species == species
                    Button {
                        withAnimation(.snappy) { settings.choose(species) }
                    } label: {
                        PalCard(fill: selected ? PalTheme.pinkLight : PalTheme.cream) {
                            HStack(spacing: 16) {
                                PalSpriteView(species: species, size: 110)
                                    .padding(.leading, 6)
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(species.displayName)
                                        .font(PalTheme.font(24, bold: true))
                                    Text(selected ? "Your pal" : "Tap to choose")
                                        .font(PalTheme.font(16))
                                        .opacity(0.7)
                                }
                                .foregroundStyle(PalTheme.ink)
                                Spacer()
                                if selected {
                                    Image(systemName: "heart.fill")
                                        .font(.title2)
                                        .foregroundStyle(PalTheme.pink)
                                        .padding(.trailing, 16)
                                }
                            }
                            .padding(.vertical, 6)
                        }
                    }
                    .buttonStyle(.plain)
                }

                Text("Name")
                    .font(PalTheme.font(20, bold: true))
                    .foregroundStyle(PalTheme.ink)
                PalCard {
                    TextField(settings.species.displayName, text: $name)
                        .font(PalTheme.font(20))
                        .foregroundStyle(PalTheme.ink)
                        .padding(14)
                        .onSubmit { settings.rename(name) }
                }

                Button {
                    settings.rename(name)
                    dismiss()
                } label: {
                    PalCard(fill: PalTheme.pink) {
                        Text("Done")
                            .font(PalTheme.font(22, bold: true))
                            .foregroundStyle(PalTheme.ink)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                    }
                }
                .buttonStyle(.plain)
            }
            .padding(20)
        }
        .background(PalTheme.paper.ignoresSafeArea())
        .onAppear { name = settings.name }
    }
}

#Preview {
    PalPickerView()
}
