import SwiftUI
import GardenCore

@main
struct GardenChatApp: App {
    @StateObject private var charactersStore = CharactersStore()
    @StateObject private var chatsStore = ChatsStore()
    @State private var pendingInitiativeCount = 0

    private let api = APIClient()

    var body: some Scene {
        WindowGroup {
            NavigationView {
                TabView {
                DashboardView()
                    .environmentObject(charactersStore)
                    .environmentObject(chatsStore)
                    .tabItem { Label("Home", systemImage: "house") }
                    .badge(pendingInitiativeCount)
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
                    .environmentObject(charactersStore)
                    .tabItem { Label("Settings", systemImage: "gear") }
                }
                .navigationBarHidden(true)
            }
            .task {
                await pollInitiatives()
            }
        }
    }

    private func pollInitiatives() async {
        while !Task.isCancelled {
            do {
                let initiatives = try await api.fetchPendingInitiatives()
                await MainActor.run { pendingInitiativeCount = initiatives.count }
            } catch {
                // Silently fail — backend may be offline
            }
            try? await Task.sleep(for: .seconds(60))
        }
    }
}
