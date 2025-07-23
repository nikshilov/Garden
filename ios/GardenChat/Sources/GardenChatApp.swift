import SwiftUI
import GardenCore

@main
struct GardenChatApp: App {
    @StateObject private var charactersStore = CharactersStore()
    @StateObject private var chatsStore = ChatsStore()
    
    var body: some Scene {
        WindowGroup {
            TabView {
                DashboardView()
                    .tabItem { Label("Home", systemImage: "house") }
                ChatsListView()
                    .environmentObject(chatsStore)
                    .environmentObject(charactersStore)
                    .tabItem { Label("Chats", systemImage: "bubble.left.and.bubble.right") }
                    .badge(chatsStore.totalUnread)
                CharactersListView()
                    .environmentObject(charactersStore)
                    .environmentObject(chatsStore)
                    .tabItem { Label("Characters", systemImage: "person.2") }
                SettingsView()
                    .tabItem { Label("Settings", systemImage: "gear") }
            }
        }
    }
}
