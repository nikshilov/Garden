import SwiftUI
import ExyteChat
import GardenCore

struct ContentView: View {
    @EnvironmentObject var viewModel: ChatViewModel
    @EnvironmentObject var charactersStore: CharactersStore
    @AppStorage("showCostMeta") private var showCostMeta = true
    @State private var exyteMessages: [ExyteChat.Message] = []

    var body: some View {
        ZStack {
            // Background gradient
            LinearGradient(colors: [Color(.systemBackground), Color(.secondarySystemBackground)], startPoint: .top, endPoint: .bottom).ignoresSafeArea()

            VStack(spacing: 0) {
                ChatHeader(viewModel: viewModel)

                ChatView(messages: exyteMessages) { draft in
                    viewModel.send(draft: draft)
                } messageBuilder: { message, _, _, _, _, _, _ in
                    ChatBubble(message: message,
                               showCostMeta: showCostMeta,
                               metaProvider: { messageId in viewModel.meta(for: messageId) ?? (cost: nil, time: nil) })
                } inputViewBuilder: { textBinding, _, _, _, action, _ in
                    ChatInputView(text: textBinding, action: action, characters: charactersStore.characters)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .chatTheme(ChatTheme())
                .onAppear {
                    exyteMessages = viewModel.exyteMessages
                }
                .id(exyteMessages.last?.id ?? "root")
                .onReceive(viewModel.$messages) { _ in
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.8)) {
                        exyteMessages = viewModel.exyteMessages
                    }
                }
            }
        }
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    viewModel.resetSession()
                } label: {
                    Image(systemName: "trash")
                        .font(.system(size: 14, weight: .medium))
                        .foregroundColor(.red.opacity(0.8))
                }
            }
        }
    }
}

struct ChatInputView: View {
    @Binding var text: String
    let action: (ExyteChat.InputViewAction) -> Void
    var characters: [Character] = []

    var body: some View {
        VStack(spacing: 0) {
            Divider()

            // Quick mention buttons
            if !characters.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(characters, id: \.id) { character in
                            Button {
                                let mention = "@\(character.id) "
                                if !text.contains("@\(character.id)") {
                                    text = mention + text
                                }
                            } label: {
                                Label(character.displayName, systemImage: character.avatarSystemName)
                                    .font(.caption)
                                    .padding(.horizontal, 10)
                                    .padding(.vertical, 6)
                                    .background(
                                        Capsule()
                                            .fill(Color.secondary.opacity(0.15))
                                    )
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(.horizontal, 12)
                }
                .padding(.top, 8)
            }

            HStack(alignment: .bottom, spacing: 12) {
                TextField("Message (use @name to mention)", text: $text, axis: .vertical)
                    .font(.system(size: 16, design: .rounded))
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Color(.secondarySystemBackground))
                    .clipShape(RoundedRectangle(cornerRadius: 20))
                    .overlay(
                        RoundedRectangle(cornerRadius: 20)
                            .stroke(Color.primary.opacity(0.05), lineWidth: 1)
                    )

                Button {
                    action(.send)
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 32))
                        .foregroundColor(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? .gray.opacity(0.3) : .blue)
                }
                .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                .padding(.bottom, 2)
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
            .background(.ultraThinMaterial)
        }
    }
}

struct ChatHeader: View {
    @ObservedObject var viewModel: ChatViewModel

    private var messageCount: Int {
        viewModel.messages.filter { !$0.isUser }.count
    }

    private var avgResponseTime: Double? {
        let times = viewModel.messages.compactMap { $0.responseTime }
        guard !times.isEmpty else { return nil }
        return times.reduce(0, +) / Double(times.count)
    }

    var body: some View {
        VStack(spacing: 0) {
            // Budget warning banner
            if viewModel.budgetExceeded {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.white)
                    Text("Budget limit exceeded!")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundColor(.white)
                    Spacer()
                    Text(String(format: "$%.2f / $%.2f", viewModel.totalCostUSD, viewModel.budgetLimit))
                        .font(.system(size: 11, weight: .medium, design: .monospaced))
                        .foregroundColor(.white.opacity(0.9))
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 8)
                .background(Color.red.opacity(0.9))
            }

            HStack(spacing: 16) {
                VStack(alignment: .leading, spacing: 2) {
                    Text(viewModel.characterName)
                        .font(.system(size: 20, weight: .bold, design: .rounded))

                    HStack(spacing: 8) {
                        Circle()
                            .fill(Color.green)
                            .frame(width: 6, height: 6)
                        Text("Active Now")
                            .font(.system(size: 12, weight: .medium, design: .rounded))
                            .foregroundColor(.secondary)
                    }
                }

                Spacer()

                HStack(spacing: 16) {
                    StatBadge(value: "\(messageCount)", icon: "bubble.left.and.bubble.right.fill", color: .blue)
                    if let avgTime = avgResponseTime {
                        StatBadge(value: String(format: "%.1fs", avgTime), icon: "timer", color: .orange)
                    }
                    StatBadge(
                        value: String(format: "$%.4f", viewModel.totalCostUSD),
                        icon: viewModel.budgetExceeded ? "exclamationmark.circle.fill" : "sparkles",
                        color: viewModel.budgetExceeded ? .red : .green
                    )
                }
            }
            .padding(.horizontal, 20)
            .padding(.vertical, 16)
            .background(.ultraThinMaterial)

            Divider().opacity(0.5)
        }
    }
}

struct StatBadge: View {
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(spacing: 2) {
            Image(systemName: icon)
                .font(.system(size: 12))
                .foregroundColor(color)
            Text(value)
                .font(.system(size: 10, weight: .bold, design: .monospaced))
                .foregroundColor(.primary.opacity(0.7))
        }
    }
}

#Preview {
    ContentView()
        .environmentObject(ChatViewModel())
        .environmentObject(CharactersStore())
}
