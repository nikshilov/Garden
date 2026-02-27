import Foundation
import GardenCore

@MainActor
final class CharactersStore: ObservableObject {
    @Published var characters: [Character]
    
    /// Full catalog of available characters (placeholder, will be fetched from backend later).
    private let catalog: [Character] = [
        Character(id: "eve", displayName: "Eve", avatarSystemName: "heart.fill"),
        Character(id: "atlas", displayName: "Atlas", avatarSystemName: "brain.head.profile"),
        Character(id: "adam", displayName: "Adam", avatarSystemName: "person.fill"),
        Character(id: "lilith", displayName: "Lilith", avatarSystemName: "moon.stars.fill"),
        Character(id: "sophia", displayName: "Sophia", avatarSystemName: "sparkles"),
    ]
    
    init() {
        // Default characters: Eve and Atlas (per PRD MVP)
        self.characters = [catalog[0], catalog[1]]  // Eve, Atlas
    }
    
    /// Characters not yet added to the user's list.
    var availableToAdd: [Character] {
        catalog.filter { c in !characters.contains(where: { $0.id == c.id }) }
    }
    
    func add(_ character: Character) {
        guard !characters.contains(where: { $0.id == character.id }) else { return }
        characters.append(character)
    }
}
