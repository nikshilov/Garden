import SwiftUI
import GardenCore
import UniformTypeIdentifiers

struct SettingsView: View {
    @AppStorage("showCostMeta") private var showCostMeta: Bool = true
    @AppStorage("selectedModel") private var selectedModelRaw: String = LLMModel.gpt4o.rawValue
    @State private var showExportSheet = false
    @State private var showImportPicker = false
    @State private var exportData: Data?
    @State private var alertMessage: String?
    @State private var showAlert = false

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
                Section("Data") {
                    Button {
                        exportChats()
                    } label: {
                        Label("Export All Chats", systemImage: "square.and.arrow.up")
                    }
                    Button {
                        showImportPicker = true
                    } label: {
                        Label("Import Chats", systemImage: "square.and.arrow.down")
                    }
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
            .sheet(isPresented: $showExportSheet) {
                if let data = exportData {
                    ShareSheet(items: [ChatExportDocument(data: data)])
                }
            }
            .fileImporter(
                isPresented: $showImportPicker,
                allowedContentTypes: [.json],
                allowsMultipleSelection: false
            ) { result in
                handleImport(result)
            }
            .alert("Chat Import", isPresented: $showAlert) {
                Button("OK", role: .cancel) { }
            } message: {
                Text(alertMessage ?? "")
            }
        }
    }

    private func exportChats() {
        Task { @MainActor in
            guard let data = ChatHistoryStore.shared.exportAllChats() else {
                alertMessage = "Failed to export chats"
                showAlert = true
                return
            }
            exportData = data
            showExportSheet = true
        }
    }

    private func handleImport(_ result: Result<[URL], Error>) {
        switch result {
        case .success(let urls):
            guard let url = urls.first else { return }
            guard url.startAccessingSecurityScopedResource() else {
                alertMessage = "Cannot access file"
                showAlert = true
                return
            }
            defer { url.stopAccessingSecurityScopedResource() }

            Task { @MainActor in
                do {
                    let data = try Data(contentsOf: url)
                    let result = ChatHistoryStore.shared.importChats(from: data)
                    if result.success {
                        alertMessage = "Successfully imported \(result.chatsImported) chat(s)"
                    } else {
                        alertMessage = result.error ?? "Import failed"
                    }
                } catch {
                    alertMessage = "Failed to read file: \(error.localizedDescription)"
                }
                showAlert = true
            }
        case .failure(let error):
            alertMessage = "Failed to select file: \(error.localizedDescription)"
            showAlert = true
        }
    }
}

// MARK: - Export Document

struct ChatExportDocument: Transferable {
    let data: Data

    static var transferRepresentation: some TransferRepresentation {
        DataRepresentation(exportedContentType: .json) { doc in
            doc.data
        }
    }
}

// MARK: - Share Sheet

struct ShareSheet: UIViewControllerRepresentable {
    let items: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let tempURL = FileManager.default.temporaryDirectory.appendingPathComponent("garden_chats_export.json")
        if let data = items.first as? ChatExportDocument {
            try? data.data.write(to: tempURL)
        }
        return UIActivityViewController(activityItems: [tempURL], applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}

#Preview {
    SettingsView()
}
