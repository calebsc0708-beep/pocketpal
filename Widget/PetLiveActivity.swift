import WidgetKit
import SwiftUI
import ActivityKit

@main
struct PocketPalWidgetBundle: WidgetBundle {
    var body: some Widget {
        PetLiveActivity()
    }
}

/// Shows the sprite. Animated sprites use the "frame font" trick:
/// a live-ticking timer drawn in a font whose digits are animation frames,
/// clipped so only the last digit (seconds) is visible.
struct IslandSprite: View {
    let state: PetAttributes.ContentState
    let size: CGFloat

    var body: some View {
        let entry = Sprites.entry(named: state.spriteName)
        let fontName = Sprites.fontName(for: state.spriteName)

        if let entry, entry.isAnimated, UIFont(name: fontName, size: size) != nil {
            Text(state.startDate, style: .timer)
                .font(.custom(fontName, fixedSize: size))
                .multilineTextAlignment(.trailing)
                .lineLimit(1)
                .fixedSize()
                .frame(width: size, height: size, alignment: .trailing)
                .clipped()
        } else {
            SpriteImage(stem: entry?.frames.first)
                .frame(width: size, height: size)
        }
    }
}

struct PetLiveActivity: Widget {
    var body: some WidgetConfiguration {
        ActivityConfiguration(for: PetAttributes.self) { context in
            // Lock Screen banner
            HStack(spacing: 12) {
                IslandSprite(state: context.state, size: 48)
                Text(displayName(context.state))
                    .font(.headline)
                    .foregroundStyle(.white)
                Spacer()
            }
            .padding()
            .activityBackgroundTint(Color.black.opacity(0.6))
            .activitySystemActionForegroundColor(.white)
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    IslandSprite(state: context.state, size: 56)
                }
                DynamicIslandExpandedRegion(.center) {
                    Text(displayName(context.state))
                        .font(.headline)
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Image(systemName: "heart.fill")
                        .foregroundStyle(.pink)
                }
            } compactLeading: {
                IslandSprite(state: context.state, size: 26)
            } compactTrailing: {
                Image(systemName: "heart.fill")
                    .foregroundStyle(.pink)
            } minimal: {
                IslandSprite(state: context.state, size: 22)
            }
        }
    }

    private func displayName(_ state: PetAttributes.ContentState) -> String {
        state.nickname.isEmpty ? state.spriteName.capitalized : state.nickname
    }
}
