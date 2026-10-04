import XCTest
@testable import Blurry

final class LifecycleTests: XCTestCase {
    private func preferences() -> (String, UserDefaults) {
        let domain = "com.chronocol.blurry.tests.\(UUID().uuidString)"
        return (domain, UserDefaults(suiteName: domain)!)
    }

    @MainActor
    func testIntroductionIsRememberedAndCanBeReplayed() async {
        let (domain, defaults) = preferences()
        defer { defaults.removePersistentDomain(forName: domain) }
        let first = Store(defaults: defaults)
        XCTAssertTrue(first.showWelcome)
        first.beginGuidedSession()
        XCTAssertFalse(first.showWelcome)
        XCTAssertTrue(first.guiding)
        let returning = Store(defaults: defaults)
        XCTAssertFalse(returning.showWelcome)
        XCTAssertFalse(returning.guiding)
        returning.restartOnboarding()
        XCTAssertTrue(returning.showWelcome)
        XCTAssertTrue(returning.guiding)
        returning.finishOnboarding()
        XCTAssertFalse(returning.showWelcome)
        XCTAssertFalse(returning.guiding)
    }

    func testFailedUninstallKeepsPreferences() throws {
        let (domain, defaults) = preferences()
        defer { defaults.removePersistentDomain(forName: domain) }
        defaults.set(true, forKey: "onboarded")
        let missing = FileManager.default.temporaryDirectory.appendingPathComponent("\(UUID()).app")
        XCTAssertThrowsError(try AppRemoval.remove(missing, defaults: defaults, domain: domain))
        XCTAssertTrue(defaults.bool(forKey: "onboarded"))
    }

    @MainActor
    func testUninstallResetsOnboardingWithoutTouchingMedia() async throws {
        let (domain, defaults) = preferences()
        defer { defaults.removePersistentDomain(forName: domain) }
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("blurry-lifecycle-\(UUID())")
        let app = folder.appendingPathComponent("Disposable.app")
        let media = folder.appendingPathComponent("original.jpg")
        try FileManager.default.createDirectory(at: app, withIntermediateDirectories: true)
        try Data("original fixture".utf8).write(to: media)
        defer { try? FileManager.default.removeItem(at: folder) }
        defaults.set(true, forKey: "onboarded")
        defaults.set("pixel", forKey: "mode")
        let trashed = try XCTUnwrap(AppRemoval.remove(app, defaults: defaults, domain: domain))
        // Restore the generated bundle, leaving no test item in the user's Trash.
        defer { try? FileManager.default.moveItem(at: trashed, to: app) }
        XCTAssertFalse(FileManager.default.fileExists(atPath: app.path))
        XCTAssertNil(defaults.object(forKey: "onboarded"))
        XCTAssertNil(defaults.object(forKey: "mode"))
        XCTAssertEqual(try Data(contentsOf: media), Data("original fixture".utf8))
        let reinstalled = Store(defaults: defaults)
        XCTAssertTrue(reinstalled.showWelcome)
        XCTAssertTrue(reinstalled.guiding)
        XCTAssertEqual(reinstalled.level, "high")
        XCTAssertEqual(reinstalled.mode, "solid")
        XCTAssertEqual(reinstalled.padding, 0.25)
    }
}
