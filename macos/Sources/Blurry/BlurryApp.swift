import SwiftUI

let releasesURL = URL(string: "https://github.com/Chrono-Web/BLURRY/releases")!

final class AppDelegate: NSObject, NSApplicationDelegate {
    var store: Store?

    func applicationDidFinishLaunching(_ notification: Notification) { Privacy.scrub() }

    /// Files dropped on the Dock icon or opened with "Open With".
    func application(_ application: NSApplication, open urls: [URL]) {
        MainActor.assumeIsolated { store?.add(urls) }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated {
            store?.jobs.shutdown()
            store?.view.shutdown()
        }
        Privacy.scrub()
    }
}

@main
struct BlurryApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var store: Store
    @State private var choosing = false

    init() {
        // The app is never an engine. If something ever starts it as one, stop
        // here, before anything else (the engine included) can start.
        if CommandLine.arguments.contains("__worker") { exit(2) }
        #if DEBUG
        IconRenderer.runIfAsked()   // renders and quits before the engine starts
        #endif
        _store = State(initialValue: Store())
    }

    var body: some Scene {
        Window("Blurry", id: "main") {
            ContentView(choosing: $choosing)
                .environment(store)
                .onAppear { delegate.store = store }
        }
        .windowStyle(.hiddenTitleBar)
        .windowResizability(.contentSize)

        Settings {
            PreferencesView().environment(store)
        }

        Window(L.queue, id: "queue") {
            QueueWindow().environment(store)
        }
        .windowResizability(.contentMinSize)
        .defaultPosition(.topTrailing)
        .commands {
            CommandGroup(before: .toolbar) {
                QueueCommand()
                Divider()
            }
            CommandGroup(replacing: .newItem) {
                Button(L.chooseFiles) { choosing = true }
                    .keyboardShortcut("o")
            }
            CommandGroup(replacing: .help) {
                RestartGuideCommand().environment(store)
                Divider()
                Button(L.updates) { NSWorkspace.shared.open(releasesURL) }
            }
        }
    }
}

/// View ▸ Queue (⌘L).
@MainActor
struct QueueCommand: View {
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Button(L.queue) { openWindow(id: "queue") }
            .keyboardShortcut("l")
    }
}

/// Bring the main window back when replaying from another window.
@MainActor
struct RestartGuideCommand: View {
    @Environment(Store.self) private var store
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Button(L.restartGuide) {
            openWindow(id: "main")
            store.restartOnboarding()
        }
    }
}
