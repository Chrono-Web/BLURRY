import BackgroundTasks
import Foundation

/// Work started on screen goes on when the app leaves it (iOS 26 and later):
/// a continued processing task, which the system shows with its progress on
/// the Lock Screen and in the Dynamic Island, and which the user can stop
/// from there. The texts never name a file (R2: nothing about the user's
/// pictures leaves the app, not even to the Lock Screen).
///
/// Before iOS 26, or when the system does not grant it, the work stops when
/// the app leaves the screen, as before.
@MainActor
final class BackgroundWork {
    /// The system took the time back, or the user stopped it from the Lock Screen.
    var onExpire: () -> Void = {}

    private var task: AnyObject?          // BGContinuedProcessingTask
    private var submitted: String?        // the identifier asked for
    private var refused = false
    private var last: (fraction: Double, subtitle: String)?

    /// True when the work may go on in the background.
    var granted: Bool { task != nil }

    private var prefix: String { (Bundle.main.bundleIdentifier ?? "blurry") + ".work" }

    /// Some work started on screen: ask for the time to finish it. Only on
    /// screen can it be asked.
    func begin(fraction: Double, subtitle: String) {
        last = (fraction, subtitle)
        guard #available(iOS 26.0, *), task == nil, submitted == nil, !refused else {
            return update(fraction: fraction, subtitle: subtitle)
        }
        // One identifier per job, registered just before it is asked for
        // (allowed after launch for these tasks), under the prefix in Info.plist.
        let identifier = prefix + "." + UUID().uuidString
        let ok = BGTaskScheduler.shared.register(forTaskWithIdentifier: identifier, using: nil) { [weak self] task in
            guard let task = task as? BGContinuedProcessingTask else { return task.setTaskCompleted(success: false) }
            Task { @MainActor in self?.started(task) }
        }
        let request = BGContinuedProcessingTaskRequest(identifier: identifier, title: L.bgTitle, subtitle: subtitle)
        request.strategy = .fail
        do {
            guard ok else { throw CocoaError(.featureUnsupported) }
            try BGTaskScheduler.shared.submit(request)
            submitted = identifier
        } catch {
            refused = true   // the system said no: this time the work stops in the background, as before
        }
    }

    func update(fraction: Double, subtitle: String) {
        last = (fraction, subtitle)
        guard #available(iOS 26.0, *), let task = task as? BGContinuedProcessingTask else { return }
        task.progress.completedUnitCount = Int64((min(1, max(0, fraction)) * 1000).rounded())
        if task.subtitle != subtitle { task.updateTitle(L.bgTitle, subtitle: subtitle) }
    }

    /// Nothing left to do.
    func end() {
        last = nil
        submitted = nil
        refused = false
        guard #available(iOS 26.0, *), let task = task as? BGContinuedProcessingTask else { return }
        self.task = nil
        task.progress.completedUnitCount = task.progress.totalUnitCount
        task.setTaskCompleted(success: true)
    }

    @available(iOS 26.0, *)
    private func started(_ task: BGContinuedProcessingTask) {
        // Finished, or replaced by another job, before the system started it.
        guard task.identifier == submitted, let last else { return task.setTaskCompleted(success: true) }
        task.progress.totalUnitCount = 1000
        task.expirationHandler = { [weak self] in
            Task { @MainActor in self?.expired() }
        }
        self.task = task
        update(fraction: last.fraction, subtitle: last.subtitle)
    }

    private func expired() {
        guard #available(iOS 26.0, *), let task = task as? BGContinuedProcessingTask else { return }
        self.task = nil
        submitted = nil
        task.setTaskCompleted(success: false)
        onExpire()
    }
}
