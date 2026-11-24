import SwiftUI
import ActivityKit

@main
struct PocketPalApp: App {
    var body: some Scene {
        WindowGroup { ContentView() }
    }
}

/// In-app preview that flips frames at the same pace as the Dynamic Island.
struct AnimatedPreview: View {
    let entry: SpriteEntry
    private let start = Date()

    var body: some View {
        if entry.isAnimated {
            TimelineView(.periodic(from: start, by: 1)) { timeline in
                let i = Sprites.frameIndex(at: timeline.date, since: start, count: entry.frames.count)
                SpriteImage(stem: entry.frames[i])
            }
        } else {
            SpriteImage(stem: entry.frames.first)
        }
    }
}

struct ContentView: View {
    @State private var entries = Sprites.all()
    @AppStorage("selectedSprite") private var selected = ""
    @AppStorage("nickname") private var nickname = ""
    @State private var status = ""

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    if entries.isEmpty {
                        Text("No sprites found. Add PNG files to the Sprites folder and rebuild.")
                            .multilineTextAlignment(.center)
                    }

                    LazyVGrid(columns: [GridItem(.adaptive(minimum: 84))], spacing: 12) {
                        ForEach(entries) { entry in
                            Button { selected = entry.name } label: {
                                VStack(spacing: 6) {
                                    AnimatedPreview(entry: entry).frame(width: 64, height: 64)
                                    HStack(spacing: 3) {
                                        Text(entry.name).font(.caption).lineLimit(1)
                                        if entry.isAnimated {
                                            Image(systemName: "sparkles").font(.caption2)
                                        }
                                    }
                                }
                                .padding(8)
                                .frame(maxWidth: .infinity)
                                .background(
                                    RoundedRectangle(cornerRadius: 12)
                                        .fill(selected == entry.name ? Color.accentColor.opacity(0.25)
                                                                     : Color.secondary.opacity(0.1))
                                )
                            }
                            .buttonStyle(.plain)
                        }
                    }

                    TextField("Nickname (optional)", text: $nickname)
                        .textFieldStyle(.roundedBorder)

                    Button("Show in Dynamic Island") { Task { await start() } }
                        .buttonStyle(.borderedProminent)
                        .disabled(selected.isEmpty)

                    Button("Put away", role: .destructive) { Task { await stopAll(); status = "Pal put away." } }

                    Text(status)
                        .font(.footnote)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
                .padding()
            }
            .navigationTitle("Pocket Pal")
        }
        .onAppear {
            if !entries.contains(where: { $0.name == selected }) { selected = entries.first?.name ?? "" }
        }
    }

    private func start() async {
        guard ActivityAuthorizationInfo().areActivitiesEnabled else {
            status = "Live Activities are turned off. Turn them on in Settings → Pocket Pal."
            return
        }
        await stopAll()
        let state = PetAttributes.ContentState(spriteName: selected, nickname: nickname, startDate: Date())
        do {
            _ = try Activity.request(
                attributes: PetAttributes(),
                content: .init(state: state, staleDate: nil),
                pushType: nil
            )
            status = "Your pal is out! Swipe home to see it in the Dynamic Island."
        } catch {
            status = "Couldn't start: \(error.localizedDescription)"
        }
    }

    private func stopAll() async {
        for activity in Activity<PetAttributes>.activities {
            await activity.end(nil, dismissalPolicy: .immediate)
        }
    }
}
