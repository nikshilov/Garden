import SwiftUI
import GardenCore

struct SettingsView: View {
    @AppStorage("showCostMeta") private var showCostMeta: Bool = true
    @AppStorage("selectedModel") private var selectedModelRaw: String = LLMModel.gpt4o.rawValue
    private var selectedModel: LLMModel {
        get { LLMModel(rawValue: selectedModelRaw) ?? .gpt4o }
        set { selectedModelRaw = newValue.rawValue }
    }
    var body: some View {
        NavigationStack {
                    Form {
                Section("Backend") {
                    Link("Open FastAPI docs", destination: URL(string: "http://127.0.0.1:5050/docs")!)
                }
                Section("Model") {
                        Picker("LLM", selection: $selectedModelRaw) {
                            ForEach(LLMModel.allCases) { model in
                                Text(model.displayName).tag(model.rawValue)
                            }
                        }
                    }
                    Section("Display") {
                        Toggle("Show cost & time", isOn: $showCostMeta)
                    }
                    Section("About") {
                    Text("Version 0.1.0")
                }
            }
            .navigationTitle("Settings")
            .onChange(of: selectedModelRaw) { newValue in
#if DEBUG
                print("SettingsView: selectedModel changed to \(newValue)")
#endif
            }
            .onChange(of: showCostMeta) { newValue in
#if DEBUG
                print("SettingsView: showCostMeta changed to \(newValue)")
#endif
            }
        }
    }
}

#Preview {
    SettingsView()
}
