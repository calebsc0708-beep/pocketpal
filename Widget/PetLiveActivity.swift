import WidgetKit
import SwiftUI
import ActivityKit

@main
struct PocketPalWidgetBundle: WidgetBundle {
    var body: some Widget {
        PetLiveActivity()
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
