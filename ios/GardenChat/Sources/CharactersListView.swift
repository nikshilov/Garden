import SwiftUI
import GardenCore

struct CharactersListView: View {
    @EnvironmentObject var store: CharactersStore
    @State private var showingCatalog = false
    
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
