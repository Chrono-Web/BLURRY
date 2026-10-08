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

    /// Empties tmp/ (pickers' copies, files shared a moment ago, videos of a
    /// previous session) and Documents/Inbox (files opened from other apps):
    /// all of it at launch; when the app leaves the screen, all but the files
    /// still in use (`keeping`: the queue's videos and an export waiting for
    /// its sheet).
    static func clearCopies(keeping: Set<URL> = []) {
        let fm = FileManager.default
        let keep = Set(keeping.map { $0.standardizedFileURL.path })
        var folders = [fm.temporaryDirectory]
        if let docs = fm.urls(for: .documentDirectory, in: .userDomainMask).first {
            folders.append(docs.appendingPathComponent("Inbox"))
        }
        func clear(_ folder: URL) {
            for child in (try? fm.contentsOfDirectory(at: folder, includingPropertiesForKeys: [.isDirectoryKey])) ?? [] {
                let path = child.standardizedFileURL.path
                if keep.contains(path) { continue }
                if keep.contains(where: { $0.hasPrefix(path + "/") }) {
                    clear(child)   // a folder holding a file in use: clear around it
                } else {
                    try? fm.removeItem(at: child)
                }
            }
        }
        folders.forEach(clear)
    }
}

/// Videos are too large to keep in memory: each one is copied, while it is in
/// the queue, into a private folder of the app's tmp/, and so is each clean
/// file until the export sheet closes. Nothing else of the user's ends up on disk.
enum Videos {
    static let types: [UTType] = [.mpeg4Movie, .quickTimeMovie, UTType("com.apple.m4v-video") ?? .movie]

    private static func folder(_ name: String) throws -> URL {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent(name, isDirectory: true)
        try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true,
                                                attributes: [.protectionKey: FileProtectionType.complete])
        return url
    }

    /// A copy of `url` (from a picker or Files) in tmp/videos/, under a new name.
    static func copy(_ url: URL) throws -> URL {
        let ext = url.pathExtension.lowercased()
        let dest = try folder("videos").appendingPathComponent(UUID().uuidString + "." + ext)
        try FileManager.default.copyItem(at: url, to: dest)
        return dest
    }

    /// Where a clean file is written before it leaves the app: its own folder,
    /// so that the share sheet shows the right name.
    static func outputFile(_ name: String) throws -> URL {
        let dir = try folder("out").appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent(name)
    }

    static func discard(_ url: URL) {
        let fm = FileManager.default
        try? fm.removeItem(at: url)
        // An output's own folder goes with it.
        let parent = url.deletingLastPathComponent()
        if parent.deletingLastPathComponent().lastPathComponent == "out" { try? fm.removeItem(at: parent) }
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

/// The clean file for "Save to Files", read from the app's temporary folder
/// as the system writes it where the user chose.
struct CleanFile: FileDocument {
    static var readableContentTypes: [UTType] { [.jpeg, .png, .mpeg4Movie] }
    let url: URL?

    init(url: URL) { self.url = url }

    init(configuration: ReadConfiguration) throws { url = nil }

    func fileWrapper(configuration: WriteConfiguration) throws -> FileWrapper {
        guard let url else { throw CocoaError(.fileNoSuchFile) }
        return try FileWrapper(url: url, options: [])   // read as written, not all into memory
    }
}
