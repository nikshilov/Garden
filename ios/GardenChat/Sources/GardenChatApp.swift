import SwiftUI
import GardenCore

@main
struct GardenChatApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(ChatViewModel())
        }
    }
}
