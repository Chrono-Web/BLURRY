import Foundation

/// Trash only this bundle; clear its preferences only after that succeeds.
/// Returning the Trash URL also lets the lifecycle test restore its disposable bundle.
enum AppRemoval {
    enum Failure: Error { case notAnApp }

    @discardableResult
    static func remove(_ app: URL, defaults: UserDefaults, domain: String) throws -> URL? {
        guard app.pathExtension == "app" else { throw Failure.notAnApp }
        var trashed: NSURL?
        try FileManager.default.trashItem(at: app, resultingItemURL: &trashed)
        defaults.removePersistentDomain(forName: domain)
        defaults.synchronize()
        return trashed as URL?
    }
}
