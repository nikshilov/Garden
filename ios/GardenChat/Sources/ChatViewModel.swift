import Foundation
import Combine
import ExyteChat
import GardenCore

@MainActor
final class ChatViewModel: ObservableObject {
    private let chatsStore: ChatsStore
    private let chatId: String
    @Published var messages: [ChatMessage] = []
    @Published var inputText: String = ""
    @Published var isTyping: Bool = false
    private var typingPlaceholderId: UUID?
    @Published var totalCostUSD: Double = 0.0
    @Published var budgetLimit: Double = 0.0
    @Published var budgetExceeded: Bool = false
    @Published var budgetRemaining: Double = 0.0
    
    var characterName: String = "Garden"
    var characterId: String? = nil

    private let api = APIClient()
    // Map ChatMessage to ExyteChat.Message for ChatView
    var exyteMessages: [ExyteChat.Message] {
        let mapped = messages.map { msg in
            let botName = msg.speaker ?? characterName
            let user: ExyteChat.User
            if msg.isUser {
                user = ExyteChat.User(id: "user", name: "You", avatarURL: nil, isCurrentUser: true)
            } else {
                // Use speaker name as unique id so different characters render separate bubbles
                user = ExyteChat.User(id: botName.lowercased(), name: botName, avatarURL: nil, isCurrentUser: false)
            }
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

        return mapped
    }
    
    // Retrieve cost & time for Exyte message id
    func meta(for exyteId: String) -> (cost: Double?, time: TimeInterval?)? {
        guard let chatMsg = messages.first(where: { $0.id.uuidString == exyteId }) else { return nil }
        return (chatMsg.costUSD, chatMsg.responseTime)
    }

    private var cancellables = Set<AnyCancellable>()
    
    // MARK: - Persistence
    private func setupPersistence() {
        // Load history
        messages = ChatHistoryStore.shared.loadMessages(chatId: chatId)
        // Save on each change
        $messages
            .debounce(for: .milliseconds(100), scheduler: DispatchQueue.main)
            .sink { msgs in
                ChatHistoryStore.shared.saveMessages(msgs, chatId: self.chatId)
            }
            .store(in: &cancellables)
    }
    
    private static func parseMultiSpeakerResponse(_ text: String, totalCost: Double?, totalDuration: TimeInterval?) -> [ChatMessage] {
        let pattern = #"\*\*(.*?)\*\*:\s*(.*?(?=\n\*\*|$))"#
        let regex = try! NSRegularExpression(pattern: pattern, options: [.dotMatchesLineSeparators])
        let nsString = text as NSString
        let matches = regex.matches(in: text, options: [], range: NSRange(location: 0, length: nsString.length))

        if matches.isEmpty {
            // Fallback for single, non-formatted message
            let (speaker, cleanText) = parseSpeakerAndText(text)
            return [ChatMessage(text: cleanText, isUser: false, speaker: speaker, costUSD: totalCost, responseTime: totalDuration)]
        }

        let messageCount = matches.count
        let costPerMessage = messageCount > 0 ? (totalCost ?? 0) / Double(messageCount) : totalCost
        let timePerMessage = messageCount > 0 ? (totalDuration ?? 0) / Double(messageCount) : totalDuration

        return matches.map { match in
            let speaker = nsString.substring(with: match.range(at: 1))
            let content = nsString.substring(with: match.range(at: 2)).trimmingCharacters(in: .whitespacesAndNewlines)
            return ChatMessage(text: content, isUser: false, speaker: speaker, costUSD: costPerMessage, responseTime: timePerMessage)
        }
    }

    private static func parseSpeakerAndText(_ raw: String) -> (String?, String) {
        let regex = try? NSRegularExpression(pattern: "^\\*\\*([^*]+)\\*\\*: ?", options: [])
        if let match = regex?.firstMatch(in: raw, options: [], range: NSRange(location: 0, length: raw.utf16.count)),
           let nameRange = Range(match.range(at: 1), in: raw) {
            let name = String(raw[nameRange])
            let clean = regex!.stringByReplacingMatches(in: raw, options: [], range: NSRange(location: 0, length: raw.utf16.count), withTemplate: "")
            return (name, clean.trimmingCharacters(in: .whitespacesAndNewlines))
        }
        return (nil, raw)
    }
    
    

    // MARK: - Init
    init(store: ChatsStore, chatId: String = "world", characterId: String? = nil, characterName: String = "Garden") {
        self.chatsStore = store
        self.chatId = chatId
        self.characterId = characterId
        self.characterName = characterName
        // Load history and observe changes
        setupPersistence()
    }
    
    convenience init() {
        self.init(store: ChatsStore(), chatId: "world")
    }

    // MARK: - Actions
    func send() {
        send(text: inputText)
    }
    
    func send(draft: DraftMessage) {
        // Draft may contain attachments, but we only handle plain text for now
        send(text: draft.text)
    }
    
    // Reset chat by clearing messages & cost
    func resetSession() {
        ChatHistoryStore.shared.deleteHistory(chatId: chatId)
        messages.removeAll()
        totalCostUSD = 0
        typingPlaceholderId = nil
#if DEBUG
        print("ChatViewModel: session reset")
#endif
    }

    func send(text: String) {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        inputText = ""

        let userMsg = ChatMessage(text: text, isUser: true)
        messages.append(userMsg)
#if DEBUG
        print("ChatViewModel: sent user message: \(text)")
#endif
        chatsStore.updateLastMessage(chatId: chatId, text: text)

        let startTime = Date()
        Task { @MainActor in
            isTyping = true
            let placeholderId = UUID()
            typingPlaceholderId = placeholderId
            let placeholder = ChatMessage(id: placeholderId, text: "…", isUser: false)
            messages.append(placeholder)
            defer { isTyping = false }
            do {
                let response = try await api.sendMessage(text: text, characterId: characterId)
                let duration = Date().timeIntervalSince(startTime)
                let botMessages = ChatViewModel.parseMultiSpeakerResponse(response.text, totalCost: response.cost_total_usd, totalDuration: duration)

                if let pid = typingPlaceholderId, let idx = messages.firstIndex(where: { $0.id == pid }) {
                    messages.remove(at: idx)
                }

                messages.append(contentsOf: botMessages)
                typingPlaceholderId = nil
                totalCostUSD = response.cost_total_usd
                budgetLimit = response.budget_limit ?? 0.0
                budgetExceeded = response.budget_exceeded ?? false
                budgetRemaining = response.budget_remaining ?? 0.0
                chatsStore.incrementUnread(chatId: chatId)
                let lastMessageText = botMessages.map { "\($0.speaker ?? characterName): \($0.text)" }.joined(separator: "\n")
                chatsStore.updateLastMessage(chatId: chatId, text: lastMessageText)
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
