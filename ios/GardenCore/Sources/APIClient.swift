import Foundation

public enum APIError: Error {
    case invalidURL
    case requestFailed
    case decodingFailed
}

public final class APIClient {
    private let session: URLSession

    public init(session: URLSession = .shared) {
        self.session = session
    }

    public struct ChatResponse: Codable {
        public let text: String
        public let cost_total_usd: Double
    }

    /// Sends a chat message to the backend and returns the assistant reply and cost.
    /// For PoC we call POST /chat with JSON {"text": "..."} and expect {"text": "...", "cost_total_usd": 0.0001}.
    public func sendMessage(text: String, characterId: String?) async throws -> ChatResponse {
        let url = Config.backendBaseURL.appendingPathComponent("chat")
        #if DEBUG
        print("APIClient: POST \(url)")
        #endif
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        var payload: [String: Any] = ["text": text]
        if let cid = characterId { payload["character_id"] = cid }
        if let model = UserDefaults.standard.string(forKey: "selectedModel") {
#if DEBUG
            print("APIClient: selectedModel = \(model)")
#endif
            // Fallback to default if saved value is not in supported list
            if model == LLMModel.phi3Mini.rawValue {
#if DEBUG
                print("APIClient: model phi3-mini unsupported, overriding to \(LLMModel.gpt4o.rawValue)")
#endif
                payload["model"] = LLMModel.gpt4o.rawValue
            } else if LLMModel(rawValue: model) == nil {
#if DEBUG
                print("APIClient: unknown model value, fallback to \(LLMModel.gpt4o.rawValue)")
#endif
                payload["model"] = LLMModel.gpt4o.rawValue
            } else {
                payload["model"] = model
            }
        } else {
#if DEBUG
            print("APIClient: no selectedModel, using default \(LLMModel.gpt4o.rawValue)")
#endif
            payload["model"] = LLMModel.gpt4o.rawValue
        }
        let bodyData = try JSONSerialization.data(withJSONObject: payload)
#if DEBUG
        if let bodyStr = String(data: bodyData, encoding: .utf8) {
            print("APIClient: request body = \(bodyStr)")
        }
#endif
        req.httpBody = bodyData

        let (data, resp) = try await session.data(for: req)
        #if DEBUG
        if let http = resp as? HTTPURLResponse {
            print("APIClient: status = \(http.statusCode)")
        }
        if let body = String(data: data, encoding: .utf8) {
            print("APIClient: body = \(body)")
        }
        #endif
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        return try JSONDecoder().decode(ChatResponse.self, from: data)
    }
}
