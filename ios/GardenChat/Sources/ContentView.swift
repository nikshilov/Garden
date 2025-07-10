import SwiftUI
import ExyteChat
import GardenCore

struct ContentView: View {
    @EnvironmentObject var viewModel: ChatViewModel
    @AppStorage("showCostMeta") private var showCostMeta: Bool = true

    var body: some View {
        ZStack {
        Color(.systemBackground).ignoresSafeArea()
        VStack(spacing: 0) {
            ChatHeader(viewModel: viewModel)
            Divider()
            ChatView(messages: viewModel.exyteMessages) { draft in
                viewModel.send(draft: draft)
            } messageBuilder: { message, _, _, _, _, _, _ in
                // Custom bubble with optional meta
                HStack(alignment: .bottom, spacing: 8) {
                    let isCurrent = message.user.isCurrentUser
                    if isCurrent {
                        Spacer(minLength: 40)
                    }
                    VStack(alignment: isCurrent ? .trailing : .leading, spacing: 2) {
                        // Bubble
                        Text(message.text)
                            .padding(.vertical, 10)
                            .padding(.horizontal, 14)
                            .background(isCurrent ? Color.accentColor : Color(uiColor: .secondarySystemBackground))
                            .foregroundColor(isCurrent ? .white : .primary)
                            .font(.body)
                            .clipShape(RoundedRectangle(cornerRadius: 18))
                            .frame(maxWidth: UIScreen.main.bounds.width * 0.7, alignment: isCurrent ? .trailing : .leading)
                        // Meta (bot messages only)
                        if showCostMeta,
                           !isCurrent,
                           let meta = viewModel.meta(for: message.id),
                           let cost = meta.cost,
                           let time = meta.time {
                            Text(String(format: "$%.4f · %.2fs", cost, time))
                                .font(.caption2)
                                .foregroundStyle(Color.secondary)
                                .padding(.top, 1)
                        }
                    }
                    if !isCurrent {
                        Spacer(minLength: 40)
                    }
                }
                } inputViewBuilder: { textBinding, _, _, _, action, _ in
                    HStack {
                        TextField("Message", text: textBinding, axis: .vertical)
                            .textFieldStyle(.roundedBorder)
                            .submitLabel(.send)
                        Button("Send") { action(.send) }
                            .buttonStyle(.borderedProminent)
                            .disabled(textBinding.wrappedValue.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    }
                    .padding(.horizontal, 12).padding(.vertical, 8)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .chatTheme(ChatTheme())
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



    


// Legacy preview
#Preview {
    ContentView()
        .environmentObject(ChatViewModel())
}
