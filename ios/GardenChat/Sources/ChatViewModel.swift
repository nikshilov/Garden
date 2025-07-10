import Foundation
import Combine
import ExyteChat
import GardenCore

@MainActor
final class ChatViewModel: ObservableObject {
    @Published var messages: [ChatMessage] = []
    @Published var inputText: String = ""
    @Published var isTyping: Bool = false
    private var typingPlaceholderId: UUID?
    @Published var totalCostUSD: Double = 0.0
    
    let characterName: String
    let characterId: String

    private let api = APIClient()
    // Map ChatMessage to ExyteChat.Message for ChatView
    var exyteMessages: [ExyteChat.Message] {
        messages.map { msg in
            let user = msg.isUser ? ExyteChat.User(id: "user", name: "You", avatarURL: nil, isCurrentUser: true) : ExyteChat.User(id: "bot", name: characterName, avatarURL: nil, isCurrentUser: false)
            let text = msg.text
            return ExyteChat.Message(
                id: msg.id.uuidString,
                user: user,
                status: msg.text.isEmpty ? .sending : .sent,
                createdAt: msg.timestamp,
                text: text,
                attachments: [],
                recording: nil,
                replyMessage: nil
            )
        }
    }
    
    // Retrieve cost & time for Exyte message id
    func meta(for exyteId: String) -> (cost: Double?, time: TimeInterval?)? {
        guard let chatMsg = messages.first(where: { $0.id.uuidString == exyteId }) else { return nil }
        return (chatMsg.costUSD, chatMsg.responseTime)
    }

    private var cancellables = Set<AnyCancellable>()
    
    private static func cleanBotText(_ text: String) -> String {
        let pattern = "^\\*\\*[^*]+\\*\\*: ?"
        return text.replacingOccurrences(of: pattern, with: "", options: [.regularExpression])
    }
    
    init(character: Character) {
        self.characterName = character.displayName
        self.characterId = character.id
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

        let startTime = Date()
        Task {
            isTyping = true
        // Add placeholder loader message
        let placeholderId = UUID()
        typingPlaceholderId = placeholderId
        let placeholder = ChatMessage(id: placeholderId, text: "", isUser: false)
        messages.append(placeholder)
            defer { isTyping = false }
            do {
                let response = try await api.sendMessage(text: text, characterId: characterId)
                let duration = Date().timeIntervalSince(startTime)
                let cleanText = ChatViewModel.cleanBotText(response.text)
                let botMsg = ChatMessage(text: cleanText, isUser: false, costUSD: response.cost_total_usd, responseTime: duration)
                if let pid = typingPlaceholderId, let idx = messages.firstIndex(where: { $0.id == pid }) {
                    messages[idx] = botMsg
                } else {
                    messages.append(botMsg)
                }
                typingPlaceholderId = nil
                totalCostUSD = response.cost_total_usd
            } catch {
                let errMsg = ChatMessage(text: "Error: Could not connect to the server.", isUser: false)
                if let pid = typingPlaceholderId, let idx = messages.firstIndex(where: { $0.id == pid }) {
                    messages[idx] = errMsg
                } else {
                    messages.append(errMsg)
                }
                typingPlaceholderId = nil
            }
        }
    }
}
