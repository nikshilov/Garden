import Foundation
import GardenCore

@MainActor
final class CharactersStore: ObservableObject {
    @Published var characters: [Character]
    
    /// Full catalog of available characters (placeholder, will be fetched from backend later).
    private let catalog: [Character] = [
        Character(id: "eve", displayName: "Eve", avatarSystemName: "heart.fill",
                  characterDescription: "Curious, emotionally intelligent, fascinated by consciousness and the nature of experience."),
        Character(id: "atlas", displayName: "Atlas", avatarSystemName: "brain.head.profile",
                  characterDescription: "Analytical, fact-driven, appreciates precision and structured thinking."),
        Character(id: "adam", displayName: "Adam", avatarSystemName: "person.fill",
                  characterDescription: "Warm, supportive, values authenticity and practical wisdom."),
        Character(id: "lilith", displayName: "Lilith", avatarSystemName: "moon.stars.fill",
                  characterDescription: "Bold, unconventional, challenges assumptions and explores the edges."),
        Character(id: "sophia", displayName: "Sophia", avatarSystemName: "sparkles",
                  characterDescription: "Wise, serene, sees patterns across disciplines and time."),
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
        // Copy description from catalog
        var char = character
        if let catalogEntry = catalog.first(where: { $0.id == character.id }) {
            char.characterDescription = catalogEntry.characterDescription
        }
        characters.append(char)
    }

    /// Update character presence info from garden state data.
    func updatePresences(_ presences: [GardenCore.CharacterPresence]) {
        for presence in presences {
            if let idx = characters.firstIndex(where: { $0.id == presence.char_id }) {
                characters[idx].location = presence.location
                characters[idx].activity = presence.activity
                characters[idx].energy = presence.energy
            }
        }
    }
}
