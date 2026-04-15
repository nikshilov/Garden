import XCTest

final class ScreenshotTests: XCTestCase {
    let app = XCUIApplication(bundleIdentifier: "ai.garden.chat")

    override func setUp() {
        continueAfterFailure = true
        app.launch()
        sleep(3) // Wait for data to load
    }

    func testTakeScreenshots() throws {
        // 1. Dashboard
        screenshot("01_dashboard")

        // 2. Chats tab
        let chatsTab = app.tabBars.buttons["Chats"]
        XCTAssertTrue(chatsTab.waitForExistence(timeout: 5), "Chats tab not found")
        chatsTab.tap()
        sleep(1)
        screenshot("02_chats_list")

        // 3. Open World Chat
        let worldChat = app.cells.firstMatch
        if worldChat.waitForExistence(timeout: 3) {
            worldChat.tap()
            sleep(2)
            screenshot("03_chat_view")

            // Go back
            if app.navigationBars.buttons.firstMatch.exists {
                app.navigationBars.buttons.firstMatch.tap()
                sleep(1)
            }
        }

        // 4. Characters tab
        let charsTab = app.tabBars.buttons["Characters"]
        if charsTab.waitForExistence(timeout: 3) {
            charsTab.tap()
            sleep(1)
            screenshot("04_characters")
        }

        // 5. Settings tab
        let settingsTab = app.tabBars.buttons["Settings"]
        if settingsTab.waitForExistence(timeout: 3) {
            settingsTab.tap()
            sleep(1)
            screenshot("05_settings")
        }
    }

    private func screenshot(_ name: String) {
        let shot = XCUIScreen.main.screenshot()
        let attachment = XCTAttachment(screenshot: shot)
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }
}
