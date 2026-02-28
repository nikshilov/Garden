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
        public let budget_limit: Double?
        public let budget_exceeded: Bool?
        public let budget_remaining: Double?
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

    // MARK: - Garden State

    public func fetchGardenState() async throws -> GardenStateResponse {
        let url = Config.backendBaseURL.appendingPathComponent("garden/state")
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        return try JSONDecoder().decode(GardenStateResponse.self, from: data)
    }

    // MARK: - Initiatives

    public func fetchPendingInitiatives() async throws -> [Initiative] {
        let url = Config.backendBaseURL.appendingPathComponent("initiatives/pending")
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        return try JSONDecoder().decode(InitiativesResponse.self, from: data).initiatives
    }

    public func dismissInitiative(id: String) async throws {
        let url = Config.backendBaseURL.appendingPathComponent("initiatives/dismiss/\(id)")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        let (_, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
    }

    // MARK: - Artifacts

    public func fetchArtifacts(creatorId: String? = nil, limit: Int = 10) async throws -> [Artifact] {
        var components = URLComponents(url: Config.backendBaseURL.appendingPathComponent("garden/artifacts"), resolvingAgainstBaseURL: false)!
        var queryItems: [URLQueryItem] = []
        if let creatorId { queryItems.append(.init(name: "creator_id", value: creatorId)) }
        queryItems.append(.init(name: "limit", value: "\(limit)"))
        components.queryItems = queryItems
        guard let url = components.url else { throw APIError.invalidURL }
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        return try JSONDecoder().decode(ArtifactsResponse.self, from: data).artifacts
    }

    // MARK: - Conversations

    public func fetchConversations(limit: Int = 10) async throws -> [CharacterConversation] {
        var components = URLComponents(url: Config.backendBaseURL.appendingPathComponent("garden/conversations"), resolvingAgainstBaseURL: false)!
        components.queryItems = [.init(name: "limit", value: "\(limit)")]
        guard let url = components.url else { throw APIError.invalidURL }
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        return try JSONDecoder().decode(ConversationsResponse.self, from: data).conversations
    }

    // MARK: - Health Diagnostics

    public func fetchDiagnostics(charId: String? = nil) async throws -> DiagnosticsResponse {
        var components = URLComponents(url: Config.backendBaseURL.appendingPathComponent("health/diagnostics"), resolvingAgainstBaseURL: false)!
        if let charId {
            components.queryItems = [.init(name: "char_id", value: charId)]
        }
        guard let url = components.url else { throw APIError.invalidURL }
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        return try JSONDecoder().decode(DiagnosticsResponse.self, from: data)
    }

    // MARK: - Initiative Settings

    public func fetchInitiativeSettings() async throws -> InitiativeSettingsResponse {
        let url = Config.backendBaseURL.appendingPathComponent("initiatives/settings")
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        return try JSONDecoder().decode(InitiativeSettingsResponse.self, from: data)
    }

    public func updateInitiativeSettings(_ update: [String: Any]) async throws -> InitiativeSettings {
        let url = Config.backendBaseURL.appendingPathComponent("initiatives/settings")
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONSerialization.data(withJSONObject: update)
        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        struct SettingsUpdateResponse: Codable {
            let ok: Bool
            let settings: InitiativeSettings
        }
        return try JSONDecoder().decode(SettingsUpdateResponse.self, from: data).settings
    }

    // MARK: - Connection Test

    public func testConnection() async throws -> Bool {
        let url = Config.backendBaseURL.appendingPathComponent("health")
        let (data, resp) = try await session.data(from: url)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            return false
        }
        struct HealthResponse: Codable { let status: String }
        let health = try JSONDecoder().decode(HealthResponse.self, from: data)
        return health.status == "ok"
    }
}
