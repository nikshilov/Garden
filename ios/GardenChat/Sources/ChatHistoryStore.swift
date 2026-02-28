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

    // MARK: - Export/Import

    /// Export all chats to a single JSON file
    func exportAllChats() -> Data? {
        var allChats: [String: [ChatMessage]] = [:]

        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil) else {
            return nil
        }

        for file in files where file.pathExtension == "json" {
            let chatId = file.deletingPathExtension().lastPathComponent
            let messages = loadMessages(chatId: chatId)
            allChats[chatId] = messages
        }

        let exportData = ChatExportData(
            version: "1.0",
            exportDate: ISO8601DateFormatter().string(from: Date()),
            chats: allChats
        )

        return try? encoder.encode(exportData)
    }

    /// Import chats from exported JSON data
    func importChats(from data: Data) -> ImportResult {
        guard let exportData = try? decoder.decode(ChatExportData.self, from: data) else {
            return ImportResult(success: false, chatsImported: 0, error: "Invalid export format")
        }

        var importedCount = 0
        for (chatId, messages) in exportData.chats {
            saveMessages(messages, chatId: chatId)
            importedCount += 1
        }

        return ImportResult(success: true, chatsImported: importedCount, error: nil)
    }

    /// List all available chat IDs
    func listAllChatIds() -> [String] {
        let fm = FileManager.default
        guard let files = try? fm.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil) else {
            return []
        }
        return files.compactMap { file -> String? in
            guard file.pathExtension == "json" else { return nil }
            return file.deletingPathExtension().lastPathComponent
        }
    }
}

// MARK: - Export Data Models

struct ChatExportData: Codable {
    let version: String
    let exportDate: String
    let chats: [String: [ChatMessage]]
}

struct ImportResult {
    let success: Bool
    let chatsImported: Int
    let error: String?
}
