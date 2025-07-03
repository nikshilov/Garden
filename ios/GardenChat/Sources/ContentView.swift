import SwiftUI
import GardenCore

struct ContentView: View {
    @EnvironmentObject var viewModel: ChatViewModel

    var body: some View {
        VStack(spacing: 0) {
            ChatHeader(viewModel: viewModel)
            Divider()
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(alignment: .leading, spacing: 8) {
                        ForEach(viewModel.messages) { msg in
                            MessageBubble(message: msg)
                                .id(msg.id)
                        }
                    }
                    .padding()
                    if viewModel.isTyping {
                        HStack {
                            Text("\(viewModel.characterName) is typing…")
                                .font(.footnote)
                                .foregroundColor(.secondary)
                            Spacer()
                        }.padding(.horizontal)
                    }
                }
                .onChange(of: viewModel.messages) { _ in
                    proxy.scrollTo(viewModel.messages.last?.id)
                }
            }
            Divider()
            HStack {
                TextField("Message", text: $viewModel.inputText, axis: .vertical)
                    .textFieldStyle(.roundedBorder)
                    .submitLabel(.send)
                    .onSubmit { viewModel.send() }
                Button("Send") { viewModel.send() }
                    .buttonStyle(.borderedProminent)
                    .disabled(viewModel.inputText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding()
        }
    }
}

private struct ChatHeader: View {
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

private struct MessageBubble: View {
    let message: ChatMessage
    var characterName: String = "Eve"
    var body: some View {
        HStack(alignment: .bottom) {
            if message.isUser { Spacer() }
            VStack(alignment: .leading, spacing: 4) {
                if !message.isUser {
                    Text(characterName)
                        .font(.caption)
                        .bold()
                        .foregroundColor(.secondary)
                }
                Text(message.text)
                    .foregroundColor(.primary)
            }
            .padding(12)
            .background(message.isUser ? Color.accentColor.opacity(0.25) : Color.gray.opacity(0.15))
            .clipShape(RoundedRectangle(cornerRadius: 14))
            if !message.isUser { Spacer() }
        }
        .frame(maxWidth: .infinity, alignment: message.isUser ? .trailing : .leading)
        .padding(.horizontal, 2)
    }
}

#Preview {
    ContentView()
        .environmentObject(ChatViewModel())
}
