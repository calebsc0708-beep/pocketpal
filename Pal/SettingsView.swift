import SwiftUI

/// Round gear button for the top of the home screen. Opens Settings.
struct SettingsButton: View {
    @State private var showing = false

    var body: some View {
        Button { showing = true } label: {
            Image(systemName: "gearshape.fill")
                .font(.system(size: 20, weight: .bold))
                .foregroundStyle(PalTheme.ink)
                .frame(width: 44, height: 44)
                .background(Circle().fill(PalTheme.cream))
                .overlay(Circle().strokeBorder(PalTheme.ink, lineWidth: 3))
                .background(Circle().fill(PalTheme.shadow).offset(y: 3))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("Settings")
        .sheet(isPresented: $showing) { SettingsView() }
    }
}

/// Settings: your pal and its name, plus how to add the room widget.
struct SettingsView: View {
    @ObservedObject var settings: PalSettings = .shared
    @Environment(\.dismiss) private var dismiss
    @State private var showingPicker = false

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                HStack {
                    Text("Settings")
                        .font(PalTheme.font(30, bold: true))
                    Spacer()
                    Button { dismiss() } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 16, weight: .heavy))
                            .frame(width: 36, height: 36)
                            .background(Circle().fill(PalTheme.cream))
                            .overlay(Circle().strokeBorder(PalTheme.ink, lineWidth: 3))
                    }
                    .buttonStyle(.plain)
                }
                .foregroundStyle(PalTheme.ink)

                section("Your pal")
                Button { showingPicker = true } label: {
                    PalCard {
                        HStack(spacing: 12) {
                            PalSpriteView(species: settings.species, size: 64)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(settings.name).font(PalTheme.font(20, bold: true))
                                Text("Change pal or name").font(PalTheme.font(15)).opacity(0.7)
                            }
                            Spacer()
                            Image(systemName: "chevron.right").font(.system(size: 16, weight: .bold))
                        }
                        .foregroundStyle(PalTheme.ink)
                        .padding(12)
                    }
                }
                .buttonStyle(.plain)

                section("Room widget")
                PalCard {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Long-press your Home Screen, tap Edit, then Add Widget and pick PokePal. Long-press the widget and choose Edit Widget to pick its pal and motion:")
                        Text("• Still: a new spot every refresh")
                        Text("• Idle: animates in place once a second")
                        Text("• Hop: hops around the room once a second")
                    }
                    .font(PalTheme.font(15))
                    .foregroundStyle(PalTheme.ink)
                    .padding(14)
                }
            }
            .padding(20)
        }
        .background(PalTheme.paper.ignoresSafeArea())
        .sheet(isPresented: $showingPicker) { PalPickerView() }
    }

    private func section(_ title: String) -> some View {
        Text(title)
            .font(PalTheme.font(20, bold: true))
            .foregroundStyle(PalTheme.ink)
            .padding(.top, 4)
    }
}

#Preview {
    SettingsView()
}
