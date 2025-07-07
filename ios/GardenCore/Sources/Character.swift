import Foundation
import SwiftUI

/// Represents a chat character/persona displayed in the character list.
public struct Character: Identifiable, Codable, Hashable {
    public let id: String  // e.g. "eve"
    public var displayName: String
    public var avatarSystemName: String // SF Symbol name for placeholder avatar
    public var unreadCount: Int
    
    public init(id: String, displayName: String, avatarSystemName: String = "person.fill", unreadCount: Int = 0) {
        self.id = id
        self.displayName = displayName
        self.avatarSystemName = avatarSystemName
        self.unreadCount = unreadCount
    }
}
