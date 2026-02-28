import SwiftUI
import GardenCore

struct DashboardView: View {
    @EnvironmentObject var charactersStore: CharactersStore
    @EnvironmentObject var chatsStore: ChatsStore
    @Binding var navigateToCharIdFromNotification: String?
    let api = APIClient()

    @State private var gardenState: GardenWorldState?
    @State private var presences: [CharacterPresence] = []
    @State private var initiatives: [Initiative] = []
    @State private var artifacts: [Artifact] = []
    @State private var isLoading = true
    @State private var error: String?
    @State private var navigateToCharacterId: String?
    @State private var selectedArtifact: Artifact?
    @State private var appeared = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    if isLoading {
                        DashboardSkeletonView()
                    } else if let error {
                        errorView(error)
                    } else {
                        if let state = gardenState {
                            gardenHeader(state)
                                .transition(.opacity.combined(with: .move(edge: .bottom)))
                        }

                        if !initiatives.isEmpty {
                            initiativesSection
                                .transition(.opacity.combined(with: .move(edge: .bottom)))
                        }

                        if !presences.isEmpty {
                            presencesSection
                                .transition(.opacity.combined(with: .move(edge: .bottom)))
                        }

                        if !artifacts.isEmpty {
                            artifactsSection
                                .transition(.opacity.combined(with: .move(edge: .bottom)))
                        }
                    }
                }
                .padding()
            }
            .background(Color(.systemGroupedBackground))
            .navigationTitle("Garden")
            .refreshable {
                await loadAll()
                UIImpactFeedbackGenerator(style: .light).impactOccurred()
            }
            .task { await loadAll() }
            .onChange(of: navigateToCharIdFromNotification) { charId in
                if let charId {
                    navigateToCharacterId = charId
                    navigateToCharIdFromNotification = nil
                }
            }
            .onReceive(NotificationCenter.default.publisher(for: .initiativeNotificationTapped)) { notification in
                if let charId = notification.userInfo?["char_id"] as? String {
                    navigateToCharacterId = charId
                }
            }
            .navigationDestination(item: $navigateToCharacterId) { charId in
                let chatId = "character_\(charId)"
                let character = charactersStore.characters.first(where: { $0.id == charId })
                let viewModel = ChatViewModel(
                    store: chatsStore,
                    chatId: chatId,
                    characterId: charId,
                    characterName: character?.displayName ?? charId.capitalized
                )
                ContentView()
                    .environmentObject(viewModel)
                    .environmentObject(charactersStore)
                    .onAppear {
                        if !chatsStore.chats.contains(where: { $0.id == chatId }) {
                            let char = character ?? Character(id: charId, displayName: charId.capitalized)
                            let _ = chatsStore.createChat(title: char.displayName, participants: [char])
                        }
                    }
            }
            .sheet(item: $selectedArtifact) { artifact in
                let name = charactersStore.characters.first(where: { $0.id == artifact.creator_id })?.displayName ?? artifact.creator_id.capitalized
                ArtifactDetailView(artifact: artifact, creatorName: name)
            }
        }
    }

    // MARK: - Sections

    private func gardenHeader(_ state: GardenWorldState) -> some View {
        VStack(spacing: 12) {
            HStack(spacing: 12) {
                Label(state.season.capitalized, systemImage: seasonIcon(state.season))
                Label(formatTimeOfDay(state.time_of_day), systemImage: timeIcon(state.time_of_day))
                Label(state.weather.capitalized, systemImage: weatherIcon(state.weather))
            }
            .font(.subheadline.weight(.medium))
            .foregroundStyle(.secondary)

            Text(state.ambiance)
                .font(.body)
                .italic()
                .multilineTextAlignment(.center)
                .foregroundStyle(.primary.opacity(0.8))
        }
        .padding()
        .frame(maxWidth: .infinity)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16))
    }

    private var initiativesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Reaching Out")
                .font(.headline)

            ForEach(initiatives) { initiative in
                initiativeCard(initiative)
            }
        }
    }

    private func initiativeCard(_ initiative: Initiative) -> some View {
        let charName = charactersStore.characters.first(where: { $0.id == initiative.char_id })?.displayName ?? initiative.char_id.capitalized

        return HStack(spacing: 12) {
            Image(systemName: characterIcon(initiative.char_id))
                .font(.title2)
                .foregroundStyle(.blue)
                .frame(width: 40)

            VStack(alignment: .leading, spacing: 4) {
                Text("\(charName) has something on their mind")
                    .font(.subheadline.weight(.semibold))
                Text(initiative.message)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer()

            Button {
                Task {
                    try? await api.dismissInitiative(id: initiative.id)
                    UINotificationFeedbackGenerator().notificationOccurred(.success)
                    withAnimation(.easeInOut(duration: 0.3)) {
                        initiatives.removeAll { $0.id == initiative.id }
                    }
                }
            } label: {
                Image(systemName: "xmark")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .buttonStyle(.plain)
        }
        .padding()
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
        .contentShape(Rectangle())
        .onTapGesture {
            navigateToCharacterId = initiative.char_id
        }
    }

    private var presencesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Characters")
                .font(.headline)

            LazyVGrid(columns: [.init(.flexible()), .init(.flexible())], spacing: 12) {
                ForEach(Array(presences.enumerated()), id: \.element.id) { index, presence in
                    presenceCard(presence)
                        .opacity(appeared ? 1 : 0)
                        .offset(y: appeared ? 0 : 20)
                        .animation(
                            .easeOut(duration: 0.35).delay(Double(index) * 0.08),
                            value: appeared
                        )
                }
            }
        }
    }

    private func presenceCard(_ presence: CharacterPresence) -> some View {
        let charName = charactersStore.characters.first(where: { $0.id == presence.char_id })?.displayName ?? presence.char_id.capitalized

        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: characterIcon(presence.char_id))
                    .font(.title3)
                    .foregroundColor(.accentColor)
                Text(charName)
                    .font(.subheadline.weight(.semibold))
                Spacer()
                energyDots(presence.energy)
            }

            Label(formatLocation(presence.location), systemImage: "mappin")
                .font(.caption)
                .foregroundStyle(.secondary)

            Text(presence.activity)
                .font(.caption2)
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
        .contentShape(Rectangle())
        .onTapGesture {
            UIImpactFeedbackGenerator(style: .light).impactOccurred()
            navigateToCharacterId = presence.char_id
        }
    }

    private var artifactsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Recent Creations")
                .font(.headline)

            ForEach(artifacts) { artifact in
                artifactCard(artifact)
            }
        }
    }

    private func artifactCard(_ artifact: Artifact) -> some View {
        let creatorName = charactersStore.characters.first(where: { $0.id == artifact.creator_id })?.displayName ?? artifact.creator_id.capitalized

        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: artifactIcon(artifact.artifact_type))
                    .foregroundStyle(.purple)
                Text(artifact.title)
                    .font(.subheadline.weight(.semibold))
                Spacer()
                Text(creatorName)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Text(artifact.content)
                .font(.caption)
                .foregroundStyle(.secondary)
                .lineLimit(4)
        }
        .padding()
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
        .contentShape(Rectangle())
        .onTapGesture {
            selectedArtifact = artifact
        }
    }

    private func errorView(_ message: String) -> some View {
        VStack(spacing: 12) {
            Image(systemName: "wifi.slash")
                .font(.largeTitle)
                .foregroundStyle(.secondary)
            Text("Couldn't reach the garden")
                .font(.headline)
            Text(message)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            Button("Retry") { Task { await loadAll() } }
                .buttonStyle(.borderedProminent)
        }
        .frame(maxWidth: .infinity, minHeight: 200)
    }

    // MARK: - Data Loading

    private func loadAll() async {
        isLoading = gardenState == nil && presences.isEmpty
        error = nil
        appeared = false

        do {
            async let stateReq = api.fetchGardenState()
            async let initiativesReq = api.fetchPendingInitiatives()
            async let artifactsReq = api.fetchArtifacts(limit: 5)

            let stateResp = try await stateReq
            let fetchedInitiatives = (try? await initiativesReq) ?? []
            let fetchedArtifacts = (try? await artifactsReq) ?? []

            withAnimation(.easeInOut(duration: 0.3)) {
                gardenState = stateResp.state
                presences = stateResp.presences
                initiatives = fetchedInitiatives
                artifacts = fetchedArtifacts
                isLoading = false
            }

            withAnimation {
                appeared = true
            }
        } catch {
            withAnimation(.easeInOut(duration: 0.3)) {
                self.error = error.localizedDescription
                isLoading = false
            }
        }
    }

    // MARK: - Helpers

    private func energyDots(_ energy: Double) -> some View {
        let filled = Int(round(energy * 5))
        return HStack(spacing: 2) {
            ForEach(0..<5, id: \.self) { i in
                Circle()
                    .fill(i < filled ? Color.green : Color.gray.opacity(0.3))
                    .frame(width: 6, height: 6)
            }
        }
    }

    private func seasonIcon(_ season: String) -> String {
        switch season {
        case "spring": return "leaf.fill"
        case "summer": return "sun.max.fill"
        case "autumn": return "leaf.arrow.triangle.circlepath"
        case "winter": return "snowflake"
        default: return "leaf.fill"
        }
    }

    private func timeIcon(_ time: String) -> String {
        switch time {
        case "dawn": return "sunrise.fill"
        case "morning": return "sun.and.horizon.fill"
        case "afternoon": return "sun.max.fill"
        case "evening": return "sunset.fill"
        case "night", "late_night": return "moon.stars.fill"
        default: return "clock"
        }
    }

    private func weatherIcon(_ weather: String) -> String {
        switch weather {
        case "clear": return "sun.max.fill"
        case "cloudy": return "cloud.fill"
        case "rainy": return "cloud.rain.fill"
        case "misty": return "cloud.fog.fill"
        case "stormy": return "cloud.bolt.rain.fill"
        case "snowy": return "cloud.snow.fill"
        default: return "cloud.fill"
        }
    }

    private func characterIcon(_ charId: String) -> String {
        switch charId {
        case "eve": return "heart.fill"
        case "atlas": return "brain.head.profile"
        case "adam": return "person.fill"
        case "lilith": return "moon.stars.fill"
        case "sophia": return "sparkles"
        default: return "person.fill"
        }
    }

    private func artifactIcon(_ type: String) -> String {
        switch type {
        case "poem": return "text.quote"
        case "theory": return "lightbulb.fill"
        case "sketch": return "paintbrush.fill"
        case "song": return "music.note"
        case "letter": return "envelope.fill"
        default: return "doc.text.fill"
        }
    }

    private func formatLocation(_ location: String) -> String {
        location.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private func formatTimeOfDay(_ time: String) -> String {
        time.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

#Preview {
    DashboardView(navigateToCharIdFromNotification: .constant(nil))
        .environmentObject(CharactersStore())
        .environmentObject(ChatsStore())
}
