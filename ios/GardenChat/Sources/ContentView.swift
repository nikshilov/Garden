import SwiftUI
import ExyteChat
import GardenCore

struct ContentView: View {
    @EnvironmentObject var viewModel: ChatViewModel

    var body: some View {
        VStack(spacing: 0) {
            ChatHeader(viewModel: viewModel)
            Divider()
            ChatView(messages: viewModel.exyteMessages) { draft in
                viewModel.send(draft: draft)
            } inputViewBuilder: { textBinding, _, _, _, action, _ in
                HStack {
                    TextField("Message", text: textBinding, axis: .vertical)
                        .textFieldStyle(.roundedBorder)
                        .submitLabel(.send)
                    Button("Send") { action(.send) }
                        .buttonStyle(.borderedProminent)
                        .disabled(textBinding.wrappedValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                .padding()
            }
            .chatTheme(ChatTheme())
        }
    }
}

struct ChatHeader: View {
    @ObservedObject var viewModel: ChatViewModel
    var body: some View {
        HStack {
            Spacer()
            Text(viewModel.characterName)
                .font(.headline)
                .bold()
            Spacer()
            Text(String(format: "$%.4f", viewModel.totalCostUSD))
                .font(.subheadline)
                .foregroundColor(.secondary)
        }
        .padding([.horizontal, .top])
    }
}



    


// Legacy preview
#Preview {
    ContentView()
        .environmentObject(ChatViewModel())
}
