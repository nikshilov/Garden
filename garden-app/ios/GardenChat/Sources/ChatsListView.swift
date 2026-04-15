import SwiftUI
import GardenCore

/// Shows ongoing dialogs (one per character for now). Later can be group chats.
struct ChatsListView: View {
    @EnvironmentObject var store: ChatsStore
    @EnvironmentObject var charactersStore: CharactersStore
    @State private var showingNewChat = false
    @State private var chatViewModels: [String: ChatViewModel] = [:]

    var body: some View {
        NavigationStack {
            let sorted = store.chats.sorted(by: { $0.lastUpdated > $1.lastUpdated })
            List {
                ForEach(sorted) { chat in
                NavigationLink {
                    ContentView()
                        .environmentObject(viewModel(for: chat))
                        .environmentObject(charactersStore)
                        .onAppear { store.markRead(chatId: chat.id) }
                } label: {
                    HStack(spacing: 8) {
                        // Avatars of participants (first 3)
                        HStack(spacing: -6) {
                            ForEach(chat.participants.prefix(3), id: \.id) { p in
                                Image(systemName: p.avatarSystemName)
                                    .resizable()
                                    .scaledToFit()
                                    .frame(width: 20, height: 20)
                                    .clipShape(Circle())
                                    .overlay(Circle().stroke(Color.white, lineWidth: 1))
                            }
                        }
                        Text(chat.title).bold()
                        Spacer()
                        if chat.unreadCount > 0 {
                            Text("\(chat.unreadCount)")
                                .font(.footnote).bold()
                                .foregroundColor(.white)
                                .padding(6)
                                .background(Circle().fill(Color.red))
                        }
                    }
                }
                }
                .onDelete { indexSet in
                    for idx in indexSet {
                        let chat = sorted[idx]
                        store.deleteChat(chatId: chat.id)
                    }
                }
            }
            .navigationTitle("Chats")
            .sheet(isPresented: $showingNewChat) {
                NewChatView()
                    .environmentObject(store)
                    .environmentObject(charactersStore)
            }
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button {
                        showingNewChat = true
                    } label: {
                        Image(systemName: "plus")
                    }
                }
            }
        }
    }

    private func viewModel(for chat: ChatThread) -> ChatViewModel {
        if let existing = chatViewModels[chat.id] { return existing }
        // Extract characterId for 1-on-1 chats (format: "character_{id}")
        let characterId: String? = chat.id.hasPrefix("character_") ? String(chat.id.dropFirst("character_".count)) : nil
        let characterName = chat.participants.first?.displayName ?? chat.title
        let vm = ChatViewModel(store: store, chatId: chat.id, characterId: characterId, characterName: characterName)
        chatViewModels[chat.id] = vm
        return vm
    }
}

#Preview {
    ChatsListView()
        .environmentObject(ChatsStore())
        .environmentObject(CharactersStore())
}
