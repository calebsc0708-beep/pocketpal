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

/// Settings: who you are (boy or girl trainer), your pal, notifications and quiet hours.
struct SettingsView: View {
    @ObservedObject var care: PalCare = .shared
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

                // ---- you ----
                section("You")
                HStack(spacing: 12) {
                    ForEach(TrainerStyle.allCases) { style in
                        let selected = care.state.trainer == style
                        Button { withAnimation(.snappy) { care.chooseTrainer(style) } } label: {
                            PalCard(fill: selected ? PalTheme.pinkLight : PalTheme.cream) {
                                VStack(spacing: 6) {
                                    Image(style.image("idle"))
                                        .resizable()
                                        .interpolation(.none)
                                        .scaledToFit()
                                        .frame(height: 120)
                                        .clipped()
                                    Text(style.displayName)
                                        .font(PalTheme.font(20, bold: true))
                                }
                                .foregroundStyle(PalTheme.ink)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 12)
                            }
                        }
                        .buttonStyle(.plain)
                    }
                }

                // ---- pal ----
                section("Your pal")
                Button { showingPicker = true } label: {
                    PalCard {
                        HStack(spacing: 12) {
                            PalSpriteView(species: care.state.species, size: 64)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(care.state.name).font(PalTheme.font(20, bold: true))
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

                // ---- notifications ----
                section("Notifications")
                PalCard {
                    VStack(spacing: 14) {
                        Toggle(isOn: Binding(get: { care.state.notificationsOn },
                                             set: { care.setNotifications($0) })) {
                            Text("Hungry, sleepy & play alerts").font(PalTheme.font(18))
                        }
                        .tint(PalTheme.pink)

                        if care.state.notificationsOn {
                            HStack {
                                Text("Quiet from").font(PalTheme.font(18))
                                Spacer()
                                hourPicker(care.state.quietStartHour) { care.setQuietHours(start: $0, end: care.state.quietEndHour) }
                                Text("to").font(PalTheme.font(18))
                                hourPicker(care.state.quietEndHour) { care.setQuietHours(start: care.state.quietStartHour, end: $0) }
                            }
                        }
                    }
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

    private func hourPicker(_ hour: Int, _ set: @escaping (Int) -> Void) -> some View {
        Menu {
            ForEach(0..<24, id: \.self) { h in
                Button(Self.label(h)) { set(h) }
            }
        } label: {
            Text(Self.label(hour))
                .font(PalTheme.font(18, bold: true))
                .padding(.horizontal, 10).padding(.vertical, 6)
                .background(RoundedRectangle(cornerRadius: 8).fill(PalTheme.pinkLight))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(PalTheme.ink, lineWidth: 2))
        }
    }

    private static func label(_ h: Int) -> String {
        let suffix = h < 12 ? "am" : "pm"
        let h12 = h % 12 == 0 ? 12 : h % 12
        return "\(h12)\(suffix)"
    }
}

#Preview {
    SettingsView()
}
