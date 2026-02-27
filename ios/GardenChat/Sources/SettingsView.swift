import SwiftUI
import GardenCore
import UniformTypeIdentifiers

struct SettingsView: View {
    @EnvironmentObject var charactersStore: CharactersStore
    @AppStorage("showCostMeta") private var showCostMeta: Bool = true
    @AppStorage("selectedModel") private var selectedModelRaw: String = LLMModel.gpt4o.rawValue
    @AppStorage("backendBaseURL") private var backendURL: String = "http://127.0.0.1:5050"
    @State private var showExportSheet = false
    @State private var showImportPicker = false
    @State private var exportData: Data?
    @State private var alertMessage: String?
    @State private var showAlert = false

    // Initiative settings state
    @State private var initiativesEnabled = true
    @State private var quietHoursStart: Int? = nil
    @State private var quietHoursEnd: Int? = nil
    @State private var disabledCharacters: Set<String> = []
    @State private var isLoadingSettings = true
    @State private var quietHoursEnabled = false

    // Connection test state
    @State private var connectionStatus: ConnectionStatus = .unknown

    private let api = APIClient()

    private enum ConnectionStatus {
        case unknown, testing, connected, failed
    }

    var body: some View {
        NavigationStack {
            Form {
                backendSection
                notificationsSection
                modelSection
                displaySection
                dataSection
                aboutSection
            }
            .navigationTitle("Settings")
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
            .task { await loadInitiativeSettings() }
        }
    }

    // MARK: - Sections

    private var backendSection: some View {
        Section("Backend") {
            HStack {
                TextField("Backend URL", text: $backendURL)
                    .textContentType(.URL)
                    .autocapitalization(.none)
                    .disableAutocorrection(true)
                    .onSubmit { testConnection() }

                connectionIndicator
            }

            Button {
                testConnection()
            } label: {
                HStack {
                    Label("Test Connection", systemImage: "bolt.horizontal.fill")
                    Spacer()
                    if connectionStatus == .testing {
                        ProgressView()
                    }
                }
            }
            .disabled(connectionStatus == .testing)

            Link("Open FastAPI docs", destination: URL(string: "\(backendURL)/docs") ?? URL(string: "http://127.0.0.1:5050/docs")!)
        }
    }

    @ViewBuilder
    private var connectionIndicator: some View {
        switch connectionStatus {
        case .unknown:
            Circle().fill(.gray).frame(width: 10, height: 10)
        case .testing:
            ProgressView().scaleEffect(0.7)
        case .connected:
            Circle().fill(.green).frame(width: 10, height: 10)
        case .failed:
            Circle().fill(.red).frame(width: 10, height: 10)
        }
    }

    private var notificationsSection: some View {
        Section {
            if isLoadingSettings {
                HStack {
                    Text("Loading settings...")
                    Spacer()
                    ProgressView()
                }
            } else {
                Toggle("Character Initiatives", isOn: $initiativesEnabled)
                    .onChange(of: initiativesEnabled) { _ in saveSettings() }

                Toggle("Quiet Hours", isOn: $quietHoursEnabled)
                    .onChange(of: quietHoursEnabled) { _ in
                        if quietHoursEnabled {
                            quietHoursStart = quietHoursStart ?? 23
                            quietHoursEnd = quietHoursEnd ?? 8
                        } else {
                            quietHoursStart = nil
                            quietHoursEnd = nil
                        }
                        saveSettings()
                    }

                if quietHoursEnabled {
                    Picker("Start", selection: Binding(
                        get: { quietHoursStart ?? 23 },
                        set: { quietHoursStart = $0; saveSettings() }
                    )) {
                        ForEach(0..<24, id: \.self) { hour in
                            Text(formatHour(hour)).tag(hour)
                        }
                    }

                    Picker("End", selection: Binding(
                        get: { quietHoursEnd ?? 8 },
                        set: { quietHoursEnd = $0; saveSettings() }
                    )) {
                        ForEach(0..<24, id: \.self) { hour in
                            Text(formatHour(hour)).tag(hour)
                        }
                    }
                }

                ForEach(charactersStore.characters) { character in
                    Toggle(character.displayName, isOn: Binding(
                        get: { !disabledCharacters.contains(character.id) },
                        set: { enabled in
                            if enabled {
                                disabledCharacters.remove(character.id)
                            } else {
                                disabledCharacters.insert(character.id)
                            }
                            saveSettings()
                        }
                    ))
                }
            }
        } header: {
            Text("Notifications")
        } footer: {
            Text("When enabled, characters may reach out when they have something on their mind.")
        }
    }

    private var modelSection: some View {
        Section("Model") {
            Picker("LLM", selection: $selectedModelRaw) {
                ForEach(LLMModel.allCases) { model in
                    Text(model.displayName).tag(model.rawValue)
                }
            }
        }
    }

    private var displaySection: some View {
        Section("Display") {
            Toggle("Show cost & time", isOn: $showCostMeta)
        }
    }

    private var dataSection: some View {
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
    }

    private var aboutSection: some View {
        Section("About") {
            Text("Version 0.2.0")
        }
    }

    // MARK: - Actions

    private func testConnection() {
        connectionStatus = .testing
        Task {
            do {
                let ok = try await api.testConnection()
                connectionStatus = ok ? .connected : .failed
            } catch {
                connectionStatus = .failed
            }
        }
    }

    private func loadInitiativeSettings() async {
        defer { isLoadingSettings = false }
        do {
            let resp = try await api.fetchInitiativeSettings()
            initiativesEnabled = resp.settings.enabled
            quietHoursStart = resp.settings.quiet_hours_start
            quietHoursEnd = resp.settings.quiet_hours_end
            quietHoursEnabled = quietHoursStart != nil
            disabledCharacters = Set(resp.settings.disabled_characters)
        } catch {
            // Use defaults on failure
        }
    }

    private func saveSettings() {
        var update: [String: Any] = [
            "enabled": initiativesEnabled,
            "disabled_characters": Array(disabledCharacters),
        ]
        if let start = quietHoursStart { update["quiet_hours_start"] = start }
        if let end = quietHoursEnd { update["quiet_hours_end"] = end }

        Task {
            _ = try? await api.updateInitiativeSettings(update)
        }
    }

    private func formatHour(_ hour: Int) -> String {
        let formatter = DateFormatter()
        formatter.dateFormat = "h a"
        var components = DateComponents()
        components.hour = hour
        if let date = Calendar.current.date(from: components) {
            return formatter.string(from: date)
        }
        return "\(hour):00"
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
        .environmentObject(CharactersStore())
}
