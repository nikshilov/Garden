import Foundation
import ExyteChat
import GardenCore

extension ChatMessage {
    /// Convert `ChatMessage` to Exyte `Message` for rendering in `ChatView`.
    /// Assumes two users: current user (id "user") and character (id "bot").
    func asExyte(characterName: String) -> ExyteChat.Message {
        let user = isUser ? ExyteChat.User(id: "user", name: "You") : ExyteChat.User(id: "bot", name: characterName)
        return ExyteChat.Message(
            id: id.uuidString,
            user: user,
            status: .sent,
            createdAt: timestamp,
            text: text,
            attachments: [],
            recording: nil,
            replyMessage: nil
        )
    }
}
