import Foundation

public struct ChatMessage: Identifiable, Codable, Equatable {
    public let id: UUID
    public let text: String
    public let isUser: Bool
    public let timestamp: Date

    public init(id: UUID = .init(), text: String, isUser: Bool, timestamp: Date = .init()) {
        self.id = id
        self.text = text
        self.isUser = isUser
        self.timestamp = timestamp
    }
}
