import Foundation

/// Supported language models selectable in the app settings.
public enum LLMModel: String, CaseIterable, Identifiable, Codable {
    case gpt4o = "gpt-4o"
    case gpt4oMini = "gpt-4o-mini"
    case sonnet = "claude-3-sonnet"
    case llama70B = "llama3-70b"

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .gpt4o: return "GPT-4o"
        case .gpt4oMini: return "GPT-4o Mini"
        case .sonnet: return "Claude 3 Sonnet"
        case .llama70B: return "Llama-3 70B"
        }
    }
}
