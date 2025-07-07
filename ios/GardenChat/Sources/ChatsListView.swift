import SwiftUI
import GardenCore

/// Shows ongoing dialogs (one per character for now). Later can be group chats.
struct ChatsListView: View {
    @EnvironmentObject var store: CharactersStore
    
    var body: some View {
        NavigationStack {
            List(store.characters) { character in
                NavigationLink {
                    ContentView()
                        .environmentObject(ChatViewModel(character: character))
                } label: {
                    HStack {
                        Image(systemName: character.avatarSystemName)
                            .resizable()
                            .scaledToFit()
                            .frame(width: 28, height: 28)
                            .foregroundColor(.accentColor)
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
            .navigationTitle("Chats")
        }
    }
}

#Preview {
    ChatsListView()
        .environmentObject(CharactersStore())
}
