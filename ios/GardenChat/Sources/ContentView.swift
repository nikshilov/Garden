import SwiftUI
import ExyteChat
import GardenCore

struct ContentView: View {
    @EnvironmentObject var viewModel: ChatViewModel
    @AppStorage("showCostMeta") private var showCostMeta = true
    @State private var exyteMessages: [ExyteChat.Message] = []

    var body: some View {
        ZStack {
            Color(.systemBackground).ignoresSafeArea()
            VStack(spacing: 0) {
                ChatHeader(viewModel: viewModel)
                Divider()
                ChatView(messages: exyteMessages) { draft in
                    viewModel.send(draft: draft)
                } messageBuilder: { message, _, _, _, _, _, _ in
                    ChatBubble(message: message,
                               showCostMeta: showCostMeta,
                               metaProvider: { messageId in viewModel.meta(for: messageId) ?? (cost: nil, time: nil) })
                } inputViewBuilder: { textBinding, _, _, _, action, _ in
                    HStack {
                        TextField("Message", text: textBinding, axis: .vertical)
                            .textFieldStyle(.roundedBorder)
                            .submitLabel(.send)
                        Button("Send") { action(.send) }
                            .buttonStyle(.borderedProminent)
                            .disabled(textBinding.wrappedValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 8)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .chatTheme(ChatTheme())
                .onAppear {
                    exyteMessages = viewModel.exyteMessages
                }
                .id(exyteMessages.last?.id ?? "root")
                .onReceive(viewModel.$messages) { _ in
                    exyteMessages = viewModel.exyteMessages
                }
                .toolbar {
                    ToolbarItem(placement: .navigationBarTrailing) {
                        Button {
                            viewModel.resetSession()
                        } label: {
                            Image(systemName: "arrow.counterclockwise")
                        }
                        .help("Reset chat session")
                    }
                }
            }
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

#Preview {
    ContentView()
        .environmentObject(ChatViewModel())
}
