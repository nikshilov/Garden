import Foundation

public struct ChatMessage: Identifiable, Codable, Equatable {
    public let id: UUID
    public let text: String
    public let isUser: Bool
    public let timestamp: Date
    public let costUSD: Double?
    public let responseTime: TimeInterval?

    public init(id: UUID = .init(), text: String, isUser: Bool, timestamp: Date = .init(), costUSD: Double? = nil, responseTime: TimeInterval? = nil) {
        self.id = id
        self.text = text
        self.isUser = isUser
        self.timestamp = timestamp
        self.costUSD = costUSD
        self.responseTime = responseTime
    }
}
