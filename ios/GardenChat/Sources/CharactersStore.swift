import Foundation
import GardenCore

@MainActor
final class CharactersStore: ObservableObject {
    @Published var characters: [Character]
    
    /// Full catalog of available characters (placeholder, will be fetched from backend later).
    private let catalog: [Character] = [
        Character(id: "eve", displayName: "Eve", avatarSystemName: "person.fill"),
        Character(id: "adam", displayName: "Adam", avatarSystemName: "person.fill"),
        Character(id: "lilith", displayName: "Lilith", avatarSystemName: "person.fill"),
        Character(id: "sophia", displayName: "Sophia", avatarSystemName: "person.fill"),
    ]
    
    init() {
        // For demo include first two.
        self.characters = [catalog[0], catalog[1]]
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
