import SwiftUI
import GardenCore

struct CharactersListView: View {
    @EnvironmentObject var store: CharactersStore
    @EnvironmentObject var chatsStore: ChatsStore
    @State private var showingCatalog = false
    @State private var characterViewModels: [String: ChatViewModel] = [:]
    @State private var selectedCharacter: Character?

    var body: some View {
        NavigationStack {
            List(store.characters) { character in
                NavigationLink {
                    let chatId = "character_\(character.id)"
                    let viewModel = characterViewModels[character.id] ?? ChatViewModel(store: chatsStore, chatId: chatId, characterId: character.id, characterName: character.displayName)
                    ContentView()
                        .environmentObject(viewModel)
                        .environmentObject(store)
                        .onAppear {
                            if characterViewModels[character.id] == nil {
                                characterViewModels[character.id] = viewModel
                                // Create chat if doesn't exist
                                if !chatsStore.chats.contains(where: { $0.id == chatId }) {
                                    let _ = chatsStore.createChat(title: character.displayName, participants: [character])
                                }
                            }
                        }
                } label: {
                    HStack {
                        Image(systemName: character.avatarSystemName)
                            .resizable()
                            .scaledToFit()
                            .frame(width: 32, height: 32)
                            .foregroundColor(.accentColor)
                            .padding(.trailing, 4)

                        VStack(alignment: .leading, spacing: 2) {
                            Text(character.displayName)
                            if let location = character.location {
                                Text(formatLocation(location))
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                        }

                        Spacer()

                        Button {
                            selectedCharacter = character
                        } label: {
                            Image(systemName: "info.circle")
                                .foregroundStyle(.secondary)
                        }
                        .buttonStyle(.plain)

                        if character.unreadCount > 0 {
                            Text("\(character.unreadCount)")
                                .font(.footnote).bold()
                                .foregroundColor(.white)
                                .padding(6)
                                .background(Circle().fill(Color.red))
                        }
                    }
                }
            }
            .navigationTitle("Characters")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showingCatalog = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
            .sheet(isPresented: $showingCatalog) {
                CharactersCatalogView()
                    .environmentObject(store)
            }
            .sheet(item: $selectedCharacter) { character in
                NavigationStack {
                    CharacterDetailView(character: character) {
                        selectedCharacter = nil
                        // Navigate to chat handled by NavigationLink above
                    }
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Done") { selectedCharacter = nil }
                        }
                    }
                }
            }
            .task { await loadPresences() }
        }
    }

    private func loadPresences() async {
        let api = APIClient()
        do {
            let resp = try await api.fetchGardenState()
            store.updatePresences(resp.presences)
        } catch {
            // Silently fail — presences are optional enrichment
        }
    }

    private func formatLocation(_ location: String) -> String {
        location.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

#Preview {
    CharactersListView()
        .environmentObject(CharactersStore())
        .environmentObject(ChatsStore())
}
