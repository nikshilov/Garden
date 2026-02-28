import Foundation
import UserNotifications
import GardenCore

@MainActor
final class NotificationManager: NSObject, ObservableObject {
    static let shared = NotificationManager()

    private let center = UNUserNotificationCenter.current()
    private let notifiedKey = "notifiedInitiativeIDs"

    @Published var isAuthorized = false

    /// Initiative IDs that have already triggered a notification.
    private var notifiedIDs: Set<String> {
        get { Set(UserDefaults.standard.stringArray(forKey: notifiedKey) ?? []) }
        set {
            let trimmed = Array(newValue.suffix(500))
            UserDefaults.standard.set(trimmed, forKey: notifiedKey)
        }
    }

    private override init() {
        super.init()
        registerCategories()
    }

    // MARK: - Permissions

    func requestAuthorization() async {
        do {
            let granted = try await center.requestAuthorization(options: [.alert, .sound, .badge])
            isAuthorized = granted
        } catch {
            isAuthorized = false
        }
    }

    // MARK: - Categories

    private func registerCategories() {
        let openAction = UNNotificationAction(
            identifier: "OPEN_CHAT",
            title: "Open Chat",
            options: [.foreground]
        )
        let dismissAction = UNNotificationAction(
            identifier: "DISMISS",
            title: "Dismiss",
            options: [.destructive]
        )
        let category = UNNotificationCategory(
            identifier: "INITIATIVE",
            actions: [openAction, dismissAction],
            intentIdentifiers: []
        )
        center.setNotificationCategories([category])
    }

    // MARK: - Schedule

    func scheduleInitiativeNotification(initiative: Initiative, characterName: String) {
        guard isAuthorized else { return }
        guard !notifiedIDs.contains(initiative.id) else { return }

        let content = UNMutableNotificationContent()
        content.title = "\(characterName) has something on their mind"
        content.body = initiative.message
        content.sound = .default
        content.categoryIdentifier = "INITIATIVE"
        content.userInfo = [
            "char_id": initiative.char_id,
            "initiative_id": initiative.id
        ]

        // Deliver after 1 second (local notification requires a trigger)
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: 1, repeats: false)
        let request = UNNotificationRequest(
            identifier: "initiative-\(initiative.id)",
            content: content,
            trigger: trigger
        )

        center.add(request)
        notifiedIDs.insert(initiative.id)
    }

    // MARK: - Response Handling

    /// Returns the char_id from a notification response, or nil if not an initiative notification.
    func handleNotificationResponse(_ response: UNNotificationResponse) -> String? {
        let userInfo = response.notification.request.content.userInfo
        guard let charId = userInfo["char_id"] as? String else { return nil }

        switch response.actionIdentifier {
        case "OPEN_CHAT", UNNotificationDefaultActionIdentifier:
            return charId
        default:
            return nil
        }
    }

    /// Check if an initiative has already been notified.
    func hasNotified(_ initiativeId: String) -> Bool {
        notifiedIDs.contains(initiativeId)
    }
}
