import SwiftUI
import GardenCore

/// Sheet used to create a new group chat, choosing a title and participants.
struct NewChatView: View {
    @EnvironmentObject var chatsStore: ChatsStore
    @EnvironmentObject var charactersStore: CharactersStore
    @Environment(\.dismiss) private var dismiss

    @State private var title: String = ""
    @State private var selectedIds: Set<String> = []

    var body: some View {
        NavigationStack {
            Form {
                Section("Chat Title") {
                    TextField("Garden", text: $title)
                }

                Section("Participants") {
                    ForEach(charactersStore.characters, id: \.id) { character in
                        Button {
                            if selectedIds.contains(character.id) {
                                selectedIds.remove(character.id)
                            } else {
                                selectedIds.insert(character.id)
                            }
                        } label: {
                            HStack {
                                Image(systemName: character.avatarSystemName)
                                    .resizable()
                                    .scaledToFit()
                                    .frame(width: 24, height: 24)
                                    .foregroundColor(.accentColor)
                                Text(character.displayName)
                                Spacer()
                                if selectedIds.contains(character.id) {
                                    Image(systemName: "checkmark")
                                        .foregroundColor(.accentColor)
                                }
                            }
                        }
                    }
                    .environment(\.editMode, .constant(.active)) // enable multiselect
                    .frame(height: 200)
                }
            }
            .navigationTitle("New Chat")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Create") {
                        createChat()
                    }
                    .disabled(selectedIds.isEmpty)
                }
            }
        }
    }

    private func createChat() {
        let participants = charactersStore.characters.filter { selectedIds.contains($0.id) }
        let chatTitle = title.isEmpty ? participants.map(\.displayName).joined(separator: ", ") : title
        let thread = chatsStore.createChat(title: chatTitle, participants: participants)
        #if DEBUG
        print("NewChatView: created chat \(thread.id) with participants \(participants.map(\.id))")
        #endif
        dismiss()
    }
}

#Preview {
    NewChatView()
        .environmentObject(ChatsStore())
        .environmentObject(CharactersStore())
}
