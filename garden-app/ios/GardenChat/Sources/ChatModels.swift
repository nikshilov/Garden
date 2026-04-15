import Foundation
import SwiftUI
import GardenCore

/// Represents a dialog (could be group chat) in the app UI.
public struct ChatThread: Identifiable, Hashable {
    public let id: String          // e.g. "world" or some uuid
    public var title: String       // Display title in list (e.g. "World Chat")
    public var participants: [Character]   // Characters that may speak here
    public var unreadCount: Int = 0
    public var lastMessagePreview: String = ""
    public var lastUpdated: Date = .init()
}

@MainActor
final class ChatsStore: ObservableObject {
    @Published var chats: [ChatThread]

    init() {
        // Initial single world chat with Eve & Atlas
        let eve = Character(id: "eve", displayName: "Eve")
        let atlas = Character(id: "atlas", displayName: "Atlas")
        self.chats = [ChatThread(id: "world", title: "World Chat", participants: [eve, atlas])]
    }

    // Total unread messages across all chats
    var totalUnread: Int {
        chats.reduce(0) { $0 + $1.unreadCount }
    }

    func markRead(chatId: String) {
        if let idx = chats.firstIndex(where: { $0.id == chatId }) {
            chats[idx].unreadCount = 0
        }
    }

    func incrementUnread(chatId: String) {
        if let idx = chats.firstIndex(where: { $0.id == chatId }) {
            chats[idx].unreadCount += 1
        }
    }

    func updateLastMessage(chatId: String, text: String) {
        if let idx = chats.firstIndex(where: { $0.id == chatId }) {
            chats[idx].lastMessagePreview = text
            chats[idx].lastUpdated = Date()
        }
    }
    
    // Create a new chat thread
    func createChat(title: String, participants: [Character]) -> ChatThread {
        let thread = ChatThread(id: UUID().uuidString, title: title, participants: participants)
        chats.append(thread)
        return thread
    }
    
    // Delete chat by id
    func deleteChat(chatId: String) {
        chats.removeAll { $0.id == chatId }
    }
}
