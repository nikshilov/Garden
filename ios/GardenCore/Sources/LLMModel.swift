import Foundation

/// Supported language models selectable in the app settings.
public enum LLMModel: String, CaseIterable, Identifiable, Codable {
    case gpt4o = "gpt-4o"
    case sonnet = "sonnet-3.7"
    case phi3Mini = "phi3-mini"
    case llama70B = "llama-3-70b"

    public var id: String { rawValue }

    public var displayName: String {
        switch self {
        case .gpt4o: return "GPT-4o"
        case .sonnet: return "Sonnet 3.7"
        case .phi3Mini: return "Phi-3 Mini"
        case .llama70B: return "Llama-3 70B"
        }
    }
}
