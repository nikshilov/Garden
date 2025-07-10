import Foundation
import Combine
import ExyteChat
import GardenCore

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var inputText: String = ""
    @Published var isTyping: Bool = false
    @Published var totalCostUSD: Double = 0.0
    
    let characterName: String

    private let api = APIClient()
    // Map ChatMessage to ExyteChat.Message for ChatView
    var exyteMessages: [ExyteChat.Message] {
        messages.map { msg in
            let user = msg.isUser ? ExyteChat.User(id: "user", name: "You", avatarURL: nil, isCurrentUser: true) : ExyteChat.User(id: "bot", name: characterName, avatarURL: nil, isCurrentUser: false)
            return ExyteChat.Message(
                id: msg.id.uuidString,
                user: user,
                status: .sent,
                createdAt: msg.timestamp,
                text: msg.text,
                attachments: [],
                recording: nil,
                replyMessage: nil
            )
        }
    }
    private var cancellables = Set<AnyCancellable>()
    
    init(character: Character) {
        self.characterName = character.displayName
    }
    
    convenience init() {
        self.init(character: Character(id: "eve", displayName: "Eve"))
    }

    func send() {
        send(text: inputText)
    }
    
    func send(draft: DraftMessage) {
        // Draft may contain attachments, but we only handle plain text for now
        send(text: draft.text)
    }
    
    func send(text: String) {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
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
