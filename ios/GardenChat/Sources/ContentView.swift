import SwiftUI
import GardenCore

struct ContentView: View {
    @EnvironmentObject var viewModel: ChatViewModel

    var body: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(viewModel.messages) { msg in
                            MessageBubble(message: msg)
                                .id(msg.id)
                        }
                    }
                    .padding()
                }
            }
            Divider()
            HStack {
                TextField("Message", text: $viewModel.inputText, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                Button("Send") { viewModel.send() }
                    .buttonStyle(.borderedProminent)
                    .disabled(viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding()
        }
    }
}

private struct MessageBubble: View {
    let message: ChatMessage
    var body: some View {
        HStack {
            if message.isUser { Spacer() }
            Text(message.text)
                .padding(10)
                .foregroundColor(.primary)
                .background(message.isUser ? Color.accentColor.opacity(0.2) : Color.gray.opacity(0.2))
                .clipShape(RoundedRectangle(cornerRadius: 10))
            if !message.isUser { Spacer() }
        }
        .frame(maxWidth: .infinity, alignment: message.isUser ? .trailing : .leading)
    }
}

#Preview {
    ContentView()
        .environmentObject(ChatViewModel())
}
