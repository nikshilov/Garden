import Foundation

/// Global configuration values for the iOS PoC.
/// In real builds these should come from Info.plist or XCConfig.
public enum Config {
    /// Base URL of the Garden backend used for the PoC.
    /// Default points to localhost; override via Runtime Arguments or UserDefaults if needed.
    public static var backendBaseURL: URL {
        if let raw = UserDefaults.standard.string(forKey: "backendBaseURL"),
           let url = URL(string: raw) {
            return url
        }
        return URL(string: "http://127.0.0.1:5050")!
    }
}
