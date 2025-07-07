import SwiftUI
import GardenCore

@main
struct GardenChatApp: App {
    @StateObject private var store = CharactersStore()
    
    var body: some Scene {
        WindowGroup {
            TabView {
                DashboardView()
                    .tabItem { Label("Home", systemImage: "house") }
                ChatsListView()
                    .environmentObject(store)
                    .tabItem { Label("Chats", systemImage: "bubble.left.and.bubble.right") }
                CharactersListView()
                    .environmentObject(store)
                    .tabItem { Label("Characters", systemImage: "person.2") }
                SettingsView()
                    .tabItem { Label("Settings", systemImage: "gear") }
            }
        }
    }
}
