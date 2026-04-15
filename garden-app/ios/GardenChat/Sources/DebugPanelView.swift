import SwiftUI
import GardenCore

/// Floating debug panel that shows session diagnostics.
/// Toggle via Settings > Debug Mode, or triple-tap the chat header.
struct DebugPanelView: View {
    @ObservedObject var viewModel: ChatViewModel
    @AppStorage("backendBaseURL") private var backendURL: String = "http://127.0.0.1:5050"
    @AppStorage("selectedModel") private var selectedModelRaw: String = LLMModel.gpt4o.rawValue
    @State private var isExpanded = false
    @State private var connectionOk: Bool?

    private var totalTokens: Int {
        viewModel.totalPromptTokens + viewModel.totalCompletionTokens
    }

    private var messageCount: Int {
        viewModel.messages.count
    }

    private var botMessageCount: Int {
        viewModel.messages.filter { !$0.isUser }.count
    }

    private var avgResponseTime: Double? {
        let times = viewModel.messages.compactMap(\.responseTime)
        guard !times.isEmpty else { return nil }
        return times.reduce(0, +) / Double(times.count)
    }

    var body: some View {
        VStack(spacing: 0) {
            // Collapsed: compact badge
            Button {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.8)) {
                    isExpanded.toggle()
                }
            } label: {
                HStack(spacing: 6) {
                    Circle()
                        .fill(connectionOk == true ? Color.green : (connectionOk == nil ? Color.gray : Color.red))
                        .frame(width: 8, height: 8)
                    Text("DEBUG")
                        .font(.system(size: 10, weight: .black, design: .monospaced))
                        .foregroundColor(.white)
                    if !isExpanded {
                        Text(viewModel.lastModel ?? selectedModelRaw)
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .foregroundColor(.white.opacity(0.7))
                        Text("$\(String(format: "%.4f", viewModel.totalCostUSD))")
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .foregroundColor(.green)
                    }
                    Image(systemName: isExpanded ? "chevron.up" : "chevron.down")
                        .font(.system(size: 8, weight: .bold))
                        .foregroundColor(.white.opacity(0.5))
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)
                .background(.black.opacity(0.85), in: Capsule())
            }
            .buttonStyle(.plain)

            if isExpanded {
                expandedPanel
                    .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .task {
            do {
                connectionOk = try await APIClient().testConnection()
            } catch {
                connectionOk = false
            }
        }
    }

    private var expandedPanel: some View {
        VStack(alignment: .leading, spacing: 8) {
            debugSection("Connection") {
                debugRow("Backend", backendURL)
                debugRow("Status", connectionOk == true ? "Connected" : (connectionOk == nil ? "Unknown" : "Failed"),
                         color: connectionOk == true ? .green : .red)
            }

            debugSection("Model") {
                debugRow("Configured", selectedModelRaw)
                if let actual = viewModel.lastModel {
                    debugRow("Actual (last)", actual)
                }
            }

            debugSection("Session") {
                if let sid = viewModel.sessionId {
                    debugRow("ID", String(sid.prefix(12)) + "...")
                }
                debugRow("Messages", "\(messageCount) (\(botMessageCount) bot)")
                if let avg = avgResponseTime {
                    debugRow("Avg latency", String(format: "%.1fs", avg))
                }
            }

            debugSection("Tokens") {
                debugRow("Prompt", "\(viewModel.totalPromptTokens)")
                debugRow("Completion", "\(viewModel.totalCompletionTokens)")
                debugRow("Total", "\(totalTokens)")
            }

            debugSection("Cost") {
                debugRow("Session total", String(format: "$%.4f", viewModel.totalCostUSD), color: .green)
                if viewModel.budgetLimit > 0 {
                    debugRow("Budget", String(format: "$%.2f", viewModel.budgetLimit))
                    debugRow("Remaining", String(format: "$%.2f", viewModel.budgetRemaining),
                             color: viewModel.budgetExceeded ? .red : .green)
                }
            }

            debugSection("App") {
                debugRow("Version", Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "dev")
                debugRow("Build", Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "-")
                debugRow("iOS", UIDevice.current.systemVersion)
            }
        }
        .padding(12)
        .background(.black.opacity(0.85), in: RoundedRectangle(cornerRadius: 12))
        .padding(.top, 4)
    }

    private func debugSection(_ title: String, @ViewBuilder content: () -> some View) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title.uppercased())
                .font(.system(size: 9, weight: .bold, design: .monospaced))
                .foregroundColor(.white.opacity(0.4))
            content()
        }
    }

    private func debugRow(_ label: String, _ value: String, color: Color = .white) -> some View {
        HStack {
            Text(label)
                .font(.system(size: 10, weight: .medium, design: .monospaced))
                .foregroundColor(.white.opacity(0.6))
            Spacer()
            Text(value)
                .font(.system(size: 10, weight: .semibold, design: .monospaced))
                .foregroundColor(color.opacity(0.9))
                .lineLimit(1)
        }
    }
}
