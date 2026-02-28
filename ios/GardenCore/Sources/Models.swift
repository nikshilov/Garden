import Foundation

public struct ChatMessage: Identifiable, Codable, Equatable {
    public let id: UUID
    public let text: String
    public let isUser: Bool
    public let timestamp: Date
    public let costUSD: Double?
    public let responseTime: TimeInterval?
    public let speaker: String?

    public init(id: UUID = .init(), text: String, isUser: Bool, speaker: String? = nil, timestamp: Date = .init(), costUSD: Double? = nil, responseTime: TimeInterval? = nil) {
        self.id = id
        self.text = text
        self.isUser = isUser
        self.timestamp = timestamp
        self.speaker = speaker
        self.costUSD = costUSD
        self.responseTime = responseTime
    }
}

// MARK: - Garden State

public struct GardenStateResponse: Codable {
    public let state: GardenWorldState
    public let presences: [CharacterPresence]
}

public struct GardenWorldState: Codable {
    public let season: String
    public let time_of_day: String
    public let weather: String
    public let ambiance: String
    public let last_updated: String
}

public struct CharacterPresence: Codable, Identifiable {
    public let char_id: String
    public let location: String
    public let activity: String
    public let energy: Double

    public var id: String { char_id }
}

// MARK: - Initiatives

public struct InitiativesResponse: Codable {
    public let initiatives: [Initiative]
}

public struct Initiative: Codable, Identifiable {
    public let id: String
    public let char_id: String
    public let trigger: String
    public let message: String
    public let created_at: String
}

// MARK: - Artifacts

public struct ArtifactsResponse: Codable {
    public let artifacts: [Artifact]
}

public struct Artifact: Codable, Identifiable {
    public let id: String
    public let creator_id: String
    public let artifact_type: String
    public let title: String
    public let content: String
    public let created_at: String

    public init(id: String, creator_id: String, artifact_type: String, title: String, content: String, created_at: String) {
        self.id = id
        self.creator_id = creator_id
        self.artifact_type = artifact_type
        self.title = title
        self.content = content
        self.created_at = created_at
    }
}

// MARK: - Character Conversations

public struct ConversationsResponse: Codable {
    public let conversations: [CharacterConversation]
}

public struct CharacterConversation: Codable, Identifiable {
    public let id: String
    public let participants: [String]
    public let messages: [ConversationMessage]
    public let location: String?
    public let created_at: String
}

public struct ConversationMessage: Codable {
    public let speaker: String
    public let text: String
}

// MARK: - Health Diagnostics

public struct DiagnosticsResponse: Codable {
    public let character: String?
    public let status: String?
    public let checks: [DiagnosticCheck]?
    public let diagnostics: [String: CharacterDiagnostics]?
}

public struct CharacterDiagnostics: Codable {
    public let status: String
    public let checks: [DiagnosticCheck]
}

public struct DiagnosticCheck: Codable, Identifiable {
    public let category: String
    public let status: String
    public let message: String
    public let auto_fixable: Bool?

    public var id: String { "\(category)-\(message)" }
}

// MARK: - Initiative Settings

public struct InitiativeSettingsResponse: Codable {
    public let settings: InitiativeSettings
    public let available: Bool
}

public struct InitiativeSettings: Codable {
    public let enabled: Bool
    public let check_interval_seconds: Int
    public let quiet_hours_start: Int?
    public let quiet_hours_end: Int?
    public let disabled_characters: [String]
}
