import SwiftUI
import GardenCore

struct CharactersListView: View {
    @EnvironmentObject var store: CharactersStore
    @EnvironmentObject var chatsStore: ChatsStore
    @State private var showingCatalog = false
    @State private var characterViewModels: [String: ChatViewModel] = [:]
    
    var body: some View {
        NavigationStack {
            List(store.characters) { character in
                NavigationLink {
                    let chatId = "character_\(character.id)"
                    let viewModel = characterViewModels[character.id] ?? ChatViewModel(store: chatsStore, chatId: chatId)
                    ContentView()
                        .environmentObject(viewModel)
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
                        Text(character.displayName)
                        Spacer()
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
        }
    }
}

#Preview {
    CharactersListView()
        .environmentObject(CharactersStore())
}
