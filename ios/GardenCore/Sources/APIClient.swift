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
    public func sendMessage(text: String) async throws -> ChatResponse {
        guard let url = URL(string: "/chat", relativeTo: Config.backendBaseURL) else {
            throw APIError.invalidURL
        }
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["text": text])

        let (data, resp) = try await session.data(for: req)
        guard let http = resp as? HTTPURLResponse, http.statusCode == 200 else {
            throw APIError.requestFailed
        }
        return try JSONDecoder().decode(ChatResponse.self, from: data)
    }
}
