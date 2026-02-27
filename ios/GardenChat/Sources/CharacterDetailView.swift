import SwiftUI
import GardenCore

struct CharacterDetailView: View {
    let character: Character
    @State private var healthStatus: String?
    @State private var checks: [DiagnosticCheck] = []
    @State private var isLoadingHealth = true
    var onChat: () -> Void

    private let api = APIClient()

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Avatar & Name
                VStack(spacing: 12) {
                    Image(systemName: character.avatarSystemName)
                        .resizable()
                        .scaledToFit()
                        .frame(width: 60, height: 60)
                        .foregroundColor(.accentColor)
                        .padding(20)
                        .background(Circle().fill(Color.accentColor.opacity(0.12)))

                    Text(character.displayName)
                        .font(.title.bold())

                    if let desc = character.characterDescription {
                        Text(desc)
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                }
                .padding(.top)

                // Location & Activity
                if character.location != nil || character.activity != nil {
                    VStack(spacing: 12) {
                        if let location = character.location {
                            HStack {
                                Image(systemName: "mappin.circle.fill")
                                    .foregroundColor(.orange)
                                Text(formatLocation(location))
                                    .font(.subheadline)
                                Spacer()
                            }
                        }
                        if let activity = character.activity {
                            HStack {
                                Image(systemName: "figure.walk")
                                    .foregroundColor(.blue)
                                Text(activity)
                                    .font(.subheadline)
                                Spacer()
                            }
                        }
                        if let energy = character.energy {
                            HStack {
                                Image(systemName: "bolt.fill")
                                    .foregroundColor(.green)
                                Text("Energy")
                                    .font(.subheadline)
                                Spacer()
                                energyBar(energy)
                            }
                        }
                    }
                    .padding()
                    .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                }

                // Health Status
                VStack(alignment: .leading, spacing: 12) {
                    HStack {
                        Text("Health")
                            .font(.headline)
                        Spacer()
                        if isLoadingHealth {
                            ProgressView()
                        } else if let status = healthStatus {
                            healthBadge(status)
                        }
                    }

                    if !checks.isEmpty {
                        ForEach(checks) { check in
                            HStack(spacing: 8) {
                                Circle()
                                    .fill(statusColor(check.status))
                                    .frame(width: 8, height: 8)
                                Text(check.category.capitalized)
                                    .font(.caption.weight(.medium))
                                Spacer()
                                Text(check.message)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                        }
                    }
                }
                .padding()
                .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))

                // Chat button
                Button(action: onChat) {
                    Label("Start Chat", systemImage: "bubble.left.fill")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding()
                        .background(Color.accentColor, in: RoundedRectangle(cornerRadius: 12))
                        .foregroundColor(.white)
                }
            }
            .padding()
        }
        .background(Color(.systemGroupedBackground))
        .navigationTitle(character.displayName)
        .navigationBarTitleDisplayMode(.inline)
        .task { await loadHealth() }
    }

    private func loadHealth() async {
        defer { isLoadingHealth = false }
        do {
            let diag = try await api.fetchDiagnostics(charId: character.id)
            healthStatus = diag.status
            checks = diag.checks ?? []
        } catch {
            healthStatus = nil
        }
    }

    private func healthBadge(_ status: String) -> some View {
        Text(status.uppercased())
            .font(.caption2.bold())
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(statusColor(status).opacity(0.2), in: Capsule())
            .foregroundColor(statusColor(status))
    }

    private func statusColor(_ status: String) -> Color {
        switch status.lowercased() {
        case "green": return .green
        case "yellow": return .orange
        case "red": return .red
        default: return .gray
        }
    }

    private func energyBar(_ energy: Double) -> some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                RoundedRectangle(cornerRadius: 4)
                    .fill(Color.gray.opacity(0.2))
                RoundedRectangle(cornerRadius: 4)
                    .fill(energy > 0.5 ? Color.green : energy > 0.25 ? Color.orange : Color.red)
                    .frame(width: geo.size.width * energy)
            }
        }
        .frame(width: 60, height: 8)
    }

    private func formatLocation(_ location: String) -> String {
        location.replacingOccurrences(of: "_", with: " ").capitalized
    }
}

#Preview {
    NavigationStack {
        CharacterDetailView(
            character: Character(id: "eve", displayName: "Eve", avatarSystemName: "heart.fill",
                                 characterDescription: "Curious and emotionally intelligent.",
                                 location: "rose_garden", activity: "Contemplating the sunset", energy: 0.75),
            onChat: {}
        )
    }
}
