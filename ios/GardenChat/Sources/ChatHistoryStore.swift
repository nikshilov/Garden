import Foundation
import GardenCore

/// Simple JSON-based local persistence for chat messages.
/// Stores each chat's messages as `<chatId>.json` under Application Support.
@MainActor
final class ChatHistoryStore {
    static let shared = ChatHistoryStore()

    private let directory: URL
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    private init() {
        encoder = JSONEncoder()
        decoder = JSONDecoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        // Directory: <AppSupport>/Chats
        let base = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        directory = base.appendingPathComponent("Chats", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
    }

    func loadMessages(chatId: String) -> [ChatMessage] {
        let url = fileURL(for: chatId)
        guard let data = try? Data(contentsOf: url) else { return [] }
        return (try? decoder.decode([ChatMessage].self, from: data)) ?? []
    }

    func saveMessages(_ messages: [ChatMessage], chatId: String) {
        let url = fileURL(for: chatId)
        guard let data = try? encoder.encode(messages) else { return }
        do {
            try data.write(to: url, options: .atomic)
        } catch {
            #if DEBUG
            print("ChatHistoryStore: failed to save messages for \(chatId): \(error)")
            #endif
        }
    }

    func deleteHistory(chatId: String) {
        let url = fileURL(for: chatId)
        try? FileManager.default.removeItem(at: url)
    }

    private func fileURL(for chatId: String) -> URL {
        directory.appendingPathComponent("\(chatId).json", isDirectory: false)
    }
}
