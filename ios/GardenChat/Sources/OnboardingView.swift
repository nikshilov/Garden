import SwiftUI
import GardenCore

struct OnboardingView: View {
    @Binding var hasCompletedOnboarding: Bool
    @AppStorage("backendBaseURL") private var backendURL: String = "http://127.0.0.1:5050"
    @State private var currentPage = 0

    var body: some View {
        ZStack {
            LinearGradient(
                colors: [Color.blue.opacity(0.15), Color.purple.opacity(0.15)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()

            TabView(selection: $currentPage) {
                welcomePage.tag(0)
                charactersPage.tag(1)
                connectPage.tag(2)
                readyPage.tag(3)
            }
            .tabViewStyle(.page(indexDisplayMode: .always))
        }
    }

    // MARK: - Page 1: Welcome

    private var welcomePage: some View {
        WelcomePage()
    }

    // MARK: - Page 2: Meet the Characters

    private var charactersPage: some View {
        CharactersPage()
    }

    // MARK: - Page 3: Connect

    private var connectPage: some View {
        ConnectPage(backendURL: $backendURL)
    }

    // MARK: - Page 4: Ready

    private var readyPage: some View {
        ReadyPage {
            hasCompletedOnboarding = true
        }
    }
}

// MARK: - Welcome Page

private struct WelcomePage: View {
    @State private var appeared = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "leaf.fill")
                .font(.system(size: 80))
                .foregroundStyle(
                    LinearGradient(colors: [.green, .mint], startPoint: .top, endPoint: .bottom)
                )
                .scaleEffect(appeared ? 1 : 0.5)
                .opacity(appeared ? 1 : 0)

            Text("Welcome to Garden")
                .font(.largeTitle.bold())
                .opacity(appeared ? 1 : 0)

            Text("A place where AI characters live,\nremember, grow, and reach out.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .opacity(appeared ? 1 : 0)

            Spacer()
            Spacer()
        }
        .padding()
        .onAppear {
            withAnimation(.easeOut(duration: 0.8)) {
                appeared = true
            }
        }
    }
}

// MARK: - Characters Page

private struct CharactersPage: View {
    private struct CharacterInfo: Identifiable {
        let id: String
        let name: String
        let icon: String
        let color: Color
        let description: String
    }

    private let characters: [CharacterInfo] = [
        .init(id: "eve", name: "Eve", icon: "heart.fill", color: .pink,
              description: "Curious, emotionally intelligent"),
        .init(id: "atlas", name: "Atlas", icon: "brain.head.profile", color: .blue,
              description: "Analytical, fact-driven"),
        .init(id: "adam", name: "Adam", icon: "person.fill", color: .orange,
              description: "Warm, supportive, authentic"),
        .init(id: "lilith", name: "Lilith", icon: "moon.stars.fill", color: .purple,
              description: "Bold, unconventional"),
        .init(id: "sophia", name: "Sophia", icon: "sparkles", color: .yellow,
              description: "Wise, sees patterns everywhere"),
    ]

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Text("Meet the Garden")
                .font(.largeTitle.bold())

            Text("Five characters, each with their own perspective.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 16) {
                    ForEach(characters) { character in
                        CharacterCard(character: character)
                    }
                }
                .padding(.horizontal, 24)
            }

            Spacer()
            Spacer()
        }
        .padding(.vertical)
    }

    private struct CharacterCard: View {
        let character: CharacterInfo
        @State private var floating = false

        var body: some View {
            VStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(character.color.opacity(0.2))
                        .frame(width: 64, height: 64)

                    Image(systemName: character.icon)
                        .font(.system(size: 28))
                        .foregroundStyle(character.color)
                }
                .offset(y: floating ? -4 : 4)

                Text(character.name)
                    .font(.headline)

                Text(character.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(width: 120)
            }
            .padding()
            .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 16))
            .onAppear {
                withAnimation(
                    .easeInOut(duration: 2)
                    .repeatForever(autoreverses: true)
                    .delay(Double.random(in: 0...0.5))
                ) {
                    floating = true
                }
            }
        }
    }
}

// MARK: - Connect Page

private struct ConnectPage: View {
    @Binding var backendURL: String
    @State private var connectionStatus: ConnectionStatus = .idle
    @FocusState private var urlFieldFocused: Bool

    private enum ConnectionStatus {
        case idle, testing, success, failed
    }

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "network")
                .font(.system(size: 50))
                .foregroundStyle(.blue)

            Text("Connect Your Garden")
                .font(.largeTitle.bold())

            Text("Enter the URL of your Garden backend.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            VStack(spacing: 16) {
                TextField("Backend URL", text: $backendURL)
                    .textFieldStyle(.roundedBorder)
                    .autocorrectionDisabled()
                    .textInputAutocapitalization(.never)
                    .keyboardType(.URL)
                    .focused($urlFieldFocused)
                    .padding(.horizontal)

                Button {
                    urlFieldFocused = false
                    testConnection()
                } label: {
                    HStack {
                        if connectionStatus == .testing {
                            ProgressView()
                                .tint(.white)
                        }
                        Text("Test Connection")
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                    .background(Color.blue, in: RoundedRectangle(cornerRadius: 10))
                    .foregroundStyle(.white)
                    .font(.headline)
                }
                .disabled(connectionStatus == .testing)
                .padding(.horizontal)

                HStack(spacing: 8) {
                    switch connectionStatus {
                    case .idle:
                        EmptyView()
                    case .testing:
                        EmptyView()
                    case .success:
                        Image(systemName: "checkmark.circle.fill")
                            .foregroundStyle(.green)
                        Text("Connected")
                            .foregroundStyle(.green)
                    case .failed:
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(.red)
                        Text("Connection failed")
                            .foregroundStyle(.red)
                    }
                }
                .font(.subheadline.weight(.medium))

                Text("You can change this later in Settings.")
                    .font(.caption)
                    .foregroundStyle(.tertiary)
            }

            Spacer()
            Spacer()
        }
        .padding()
    }

    private func testConnection() {
        connectionStatus = .testing
        Task {
            do {
                let ok = try await APIClient().testConnection()
                await MainActor.run {
                    connectionStatus = ok ? .success : .failed
                }
            } catch {
                await MainActor.run {
                    connectionStatus = .failed
                }
            }
        }
    }
}

// MARK: - Ready Page

private struct ReadyPage: View {
    let onGetStarted: () -> Void
    @State private var appeared = false

    var body: some View {
        VStack(spacing: 24) {
            Spacer()

            Image(systemName: "checkmark.circle.fill")
                .font(.system(size: 80))
                .foregroundStyle(.green)
                .scaleEffect(appeared ? 1 : 0.3)
                .opacity(appeared ? 1 : 0)

            Text("Your Garden Awaits")
                .font(.largeTitle.bold())
                .opacity(appeared ? 1 : 0)

            Text("Start chatting with characters who remember,\ngrow, and think between conversations.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .opacity(appeared ? 1 : 0)

            Spacer()

            Button {
                onGetStarted()
            } label: {
                Text("Get Started")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(
                        LinearGradient(colors: [.blue, .purple], startPoint: .leading, endPoint: .trailing),
                        in: RoundedRectangle(cornerRadius: 12)
                    )
                    .foregroundStyle(.white)
                    .font(.headline)
            }
            .padding(.horizontal, 32)
            .opacity(appeared ? 1 : 0)

            Spacer()
        }
        .padding()
        .onAppear {
            withAnimation(.spring(response: 0.6, dampingFraction: 0.7).delay(0.2)) {
                appeared = true
            }
        }
    }
}

#Preview {
    OnboardingView(hasCompletedOnboarding: .constant(false))
}
