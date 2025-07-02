import Foundation
import Combine
import GardenCore

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var inputText: String = ""

    private let api = APIClient()
    private var cancellables = Set<AnyCancellable>()

    func send() {
        let text = inputText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""
        let userMsg = ChatMessage(text: text, isUser: true)
        messages.append(userMsg)

        Task {
            do {
                let reply = try await api.sendMessage(text: text)
                let botMsg = ChatMessage(text: reply, isUser: false)
                messages.append(botMsg)
            } catch {
                let errMsg = ChatMessage(text: "Error: \(error.localizedDescription)", isUser: false)
                messages.append(errMsg)
            }
        }
    }
}
