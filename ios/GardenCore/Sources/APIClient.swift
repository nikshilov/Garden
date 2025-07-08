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
        let url = Config.backendBaseURL.appendingPathComponent("chat")
        #if DEBUG
        print("APIClient: POST \(url)")
        #endif
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["text": text])

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
