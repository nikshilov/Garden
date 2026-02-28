import SwiftUI
import GardenCore
import UserNotifications

@main
struct GardenChatApp: App {
    @StateObject private var charactersStore = CharactersStore()
    @StateObject private var chatsStore = ChatsStore()
    @StateObject private var notificationManager = NotificationManager.shared
    @State private var pendingInitiativeCount = 0
    @State private var selectedTab = 0
    @State private var notificationCharId: String?

    @AppStorage("localNotificationsEnabled") private var localNotificationsEnabled = true
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false

    private let api = APIClient()

    var body: some Scene {
        WindowGroup {
            TabView(selection: $selectedTab) {
                DashboardView(navigateToCharIdFromNotification: $notificationCharId)
                    .environmentObject(charactersStore)
                    .environmentObject(chatsStore)
                    .tabItem { Label("Home", systemImage: "house") }
                    .badge(pendingInitiativeCount)
                    .tag(0)
                ChatsListView()
                    .environmentObject(chatsStore)
                    .environmentObject(charactersStore)
                    .tabItem { Label("Chats", systemImage: "bubble.left.and.bubble.right") }
                    .badge(chatsStore.totalUnread)
                    .tag(1)
                CharactersListView()
                    .environmentObject(charactersStore)
                    .environmentObject(chatsStore)
                    .tabItem { Label("Characters", systemImage: "person.2") }
                    .tag(2)
                SettingsView()
                    .environmentObject(charactersStore)
                    .tabItem { Label("Settings", systemImage: "gear") }
                    .tag(3)
            }
            .fullScreenCover(isPresented: Binding(
                get: { !hasCompletedOnboarding },
                set: { if !$0 { hasCompletedOnboarding = true } }
            )) {
                OnboardingView(hasCompletedOnboarding: $hasCompletedOnboarding)
            }
            .task {
                await notificationManager.requestAuthorization()
                UNUserNotificationCenter.current().delegate = notificationManager
                await pollInitiatives()
            }
        }
    }

    private func pollInitiatives() async {
        while !Task.isCancelled {
            do {
                let initiatives = try await api.fetchPendingInitiatives()
                await MainActor.run { pendingInitiativeCount = initiatives.count }

                if localNotificationsEnabled {
                    for initiative in initiatives {
                        if !notificationManager.hasNotified(initiative.id) {
                            let name = charactersStore.characters
                                .first(where: { $0.id == initiative.char_id })?
                                .displayName ?? initiative.char_id.capitalized
                            notificationManager.scheduleInitiativeNotification(
                                initiative: initiative,
                                characterName: name
                            )
                        }
                    }
                }
            } catch is CancellationError {
                return
            } catch {
                // Silently fail — backend may be offline
            }
            do {
                try await Task.sleep(for: .seconds(60))
            } catch {
                return // Cancelled during sleep
            }
        }
    }
}

// MARK: - UNUserNotificationCenterDelegate

extension NotificationManager: UNUserNotificationCenterDelegate {
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .sound]
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let userInfo = response.notification.request.content.userInfo
        guard let charId = userInfo["char_id"] as? String else { return }
        let actionId = response.actionIdentifier
        guard actionId == "OPEN_CHAT" || actionId == UNNotificationDefaultActionIdentifier else { return }
        NotificationCenter.default.post(
            name: .initiativeNotificationTapped,
            object: nil,
            userInfo: ["char_id": charId]
        )
    }
}

extension Notification.Name {
    static let initiativeNotificationTapped = Notification.Name("initiativeNotificationTapped")
}
