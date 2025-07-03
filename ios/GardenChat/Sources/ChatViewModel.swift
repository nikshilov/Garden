import Foundation
import Combine
import GardenCore

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var inputText: String = ""
    @Published var isTyping: Bool = false
    @Published var totalCostUSD: Double = 0.0
    
    let characterName: String = "Eve" // Placeholder until backend returns persona info

    private let api = APIClient()
    private var cancellables = Set<AnyCancellable>()

    func send() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        let userMsg = ChatMessage(text: text, isUser: true)
        messages.append(userMsg)

        Task {
            isTyping = true
            defer { isTyping = false }
            do {
                let response = try await api.sendMessage(text: text)
                let botMsg = ChatMessage(text: response.text, isUser: false)
                messages.append(botMsg)
                totalCostUSD = response.cost_total_usd
            } catch {
                let errMsg = ChatMessage(text: "Error: Could not connect to the server.", isUser: false)
                messages.append(errMsg)
            }
        }
    }
}
