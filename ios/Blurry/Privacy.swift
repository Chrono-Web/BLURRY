import SwiftUI
import UIKit
import UniformTypeIdentifiers

/// R2 on iOS: nothing about the user's files stays in the app's container.
enum Privacy {
    /// The same list as the Mac app and src/blurry_opsec/gui/prefs.py.
    static let allowedKeys: Set<String> = ["level", "mode", "padding", "language", "onboarded"]

    /// The app's defaults hold only the allowed preferences: any other key
    /// (the system adds some of its own) is removed.
    static func scrub(_ defaults: UserDefaults = .standard) {
        guard let id = Bundle.main.bundleIdentifier,
              let domain = defaults.persistentDomain(forName: id) else { return }
        for key in domain.keys where !allowedKeys.contains(key) {
            defaults.removeObject(forKey: key)
        }
    }

    /// Empties tmp/ (pickers' copies, the file shared a moment ago) and
    /// Documents/Inbox (files opened from other apps), at launch and whenever
    /// the app leaves the screen.
    static func clearCopies() {
        let fm = FileManager.default
        var folders = [fm.temporaryDirectory]
        if let docs = fm.urls(for: .documentDirectory, in: .userDomainMask).first {
            folders.append(docs.appendingPathComponent("Inbox"))
        }
        for folder in folders {
            for child in (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: nil)) ?? [] {
                try? fm.removeItem(at: child)
            }
        }
    }

    /// The clean file, written where the share sheet can read it, in a folder
    /// of its own that `clearCopies` removes afterwards.
    static func shareableFile(_ data: Data, name: String) throws -> URL {
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("share-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let url = folder.appendingPathComponent(name)
        try data.write(to: url, options: [.completeFileProtection])
        return url
    }
}

/// While the app is not active its picture is covered, so that the snapshot
/// iOS takes for the app switcher never shows an uncovered photo.
struct PrivacyCover: View {
    var body: some View {
        ZStack {
            Color.black
            CornerTicks(length: 18)
                .stroke(accent, lineWidth: 2)
                .frame(width: 96, height: 96)
        }
        .ignoresSafeArea()
    }
}

/// The system share sheet, without "Save Image" (Photos syncs to iCloud) and
/// other actions that would keep a copy around.
struct ShareSheet: UIViewControllerRepresentable {
    let url: URL
    let done: (Bool) -> Void

    func makeUIViewController(context: Context) -> UIActivityViewController {
        let vc = UIActivityViewController(activityItems: [url], applicationActivities: nil)
        vc.excludedActivityTypes = [.saveToCameraRoll, .addToReadingList, .assignToContact,
                                    .print, .openInIBooks, .sharePlay]
        vc.completionWithItemsHandler = { _, completed, _, _ in done(completed) }
        return vc
    }

    func updateUIViewController(_ vc: UIActivityViewController, context: Context) {}
}

/// The clean file for "Save to Files".
struct CleanFile: FileDocument {
    static var readableContentTypes: [UTType] { [.jpeg, .png] }
    let data: Data

    init(data: Data) { self.data = data }

    init(configuration: ReadConfiguration) throws {
        data = configuration.file.regularFileContents ?? Data()
    }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        FileWrapper(regularFileWithContents: data)
    }
}
