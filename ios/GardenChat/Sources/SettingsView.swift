import SwiftUI

struct SettingsView: View {
    var body: some View {
        NavigationStack {
            Form {
                Section("Backend") {
                    Link("Open FastAPI docs", destination: URL(string: "http://127.0.0.1:5050/docs")!)
                }
                Section("About") {
                    Text("Version 0.1.0")
                }
            }
            .navigationTitle("Settings")
        }
    }
}

#Preview {
    SettingsView()
}
