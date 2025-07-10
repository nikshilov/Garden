import SwiftUI

struct SettingsView: View {
    @AppStorage("showCostMeta") private var showCostMeta: Bool = true
    var body: some View {
        NavigationStack {
                    Form {
                Section("Backend") {
                    Link("Open FastAPI docs", destination: URL(string: "http://127.0.0.1:5050/docs")!)
                }
                Section("Display") {
                        Toggle("Show cost & time", isOn: $showCostMeta)
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
