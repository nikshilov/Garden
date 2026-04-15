import SwiftUI
import GardenCore

struct ArtifactDetailView: View {
    let artifact: Artifact
    let creatorName: String

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    // Type icon
                    Image(systemName: artifactIcon(artifact.artifact_type))
                        .font(.system(size: 40))
                        .foregroundStyle(.purple)
                        .padding(.top, 24)

                    // Title
                    Text(artifact.title)
                        .font(.title)
                        .fontWeight(.bold)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal)

                    // Creator + date subtitle
                    Text("\(creatorName) · \(formattedDate)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Divider()
                        .padding(.horizontal)

                    // Full content
                    Text(artifact.content)
                        .font(.body)
                        .lineSpacing(6)
                        .padding(.horizontal)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(.bottom, 32)
            }
            .background(Color(.systemGroupedBackground))
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    ShareLink(item: shareText) {
                        Image(systemName: "square.and.arrow.up")
                    }
                }
                ToolbarItem(placement: .topBarLeading) {
                    Button("Done") {
                        dismiss()
                    }
                }
            }
        }
    }

    @Environment(\.dismiss) private var dismiss

    private var shareText: String {
        """
        \(artifact.title)
        by \(creatorName)

        \(artifact.content)
        """
    }

    private var formattedDate: String {
        // Try ISO8601 parsing, fall back to raw string
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: artifact.created_at) {
            let display = DateFormatter()
            display.dateStyle = .medium
            display.timeStyle = .none
            return display.string(from: date)
        }
        // Try without fractional seconds
        formatter.formatOptions = [.withInternetDateTime]
        if let date = formatter.date(from: artifact.created_at) {
            let display = DateFormatter()
            display.dateStyle = .medium
            display.timeStyle = .none
            return display.string(from: date)
        }
        return artifact.created_at
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
}

#Preview {
    ArtifactDetailView(
        artifact: Artifact(
            id: "1", creator_id: "eve", artifact_type: "poem",
            title: "Morning Light", content: "The dawn breaks softly\nover petals still with dew,\na world born again.",
            created_at: "2025-01-15T10:30:00Z"
        ),
        creatorName: "Eve"
    )
}
