import SwiftUI
import GardenCore

struct CharactersCatalogView: View {
    @EnvironmentObject var store: CharactersStore
    @Environment(\.dismiss) private var dismiss
    
    var body: some View {
        NavigationStack {
            List(store.availableToAdd) { character in
                HStack {
                    Image(systemName: character.avatarSystemName)
                        .resizable()
                        .scaledToFit()
                        .frame(width: 28, height: 28)
                        .foregroundColor(.accentColor)
                    Text(character.displayName)
                    Spacer()
                    Button {
                        store.add(character)
                    } label: {
                        Image(systemName: "plus.circle.fill")
                            .imageScale(.large)
                            .foregroundColor(.green)
                    }
                    .buttonStyle(.plain)
                }
            }
            .navigationTitle("Add Character")
            .toolbar {
                ToolbarItem(placement: .navigationBarTrailing) {
                    Button("Done") { dismiss() }
                }
            }
        }
    }
}

#Preview {
    CharactersCatalogView()
        .environmentObject(CharactersStore())
}
