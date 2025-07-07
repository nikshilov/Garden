import SwiftUI

struct DashboardView: View {
    var body: some View {
        VStack(spacing: 16) {
            Image(systemName: "sparkles")
                .resizable()
                .scaledToFit()
                .frame(width: 64, height: 64)
                .foregroundColor(.accentColor)
            Text("Garden AI Chat")
                .font(.title).bold()
            Text("Welcome! Choose a character or continue a conversation.")
                .multilineTextAlignment(.center)
                .foregroundColor(.secondary)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(.systemGroupedBackground))
    }
}

#Preview {
    DashboardView()
}
