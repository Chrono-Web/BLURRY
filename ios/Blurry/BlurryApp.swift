import SwiftUI

let releasesURL = URL(string: "https://github.com/Chrono-Web/BLURRY/releases")!

@main
struct BlurryApp: App {
    @State private var store = Store()
    @Environment(\.scenePhase) private var phase

    init() {
        Privacy.scrub()
        Privacy.clearCopies()   // leftovers of a previous session that ended abruptly
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(store)
                // "Open in Blurry" from another app: iOS copies the file into
                // Documents/Inbox; it is read into memory and deleted at once.
                .onOpenURL { url in
                    let ext = url.pathExtension
                    let data = try? Data(contentsOf: url)
                    try? FileManager.default.removeItem(at: url)
                    if let data { store.add([(name: url.lastPathComponent, ext: ext, data: data)]) }
                    else { store.notice = L.unreadable }
                }
        }
        .onChange(of: phase) { _, now in
            switch now {
            case .background: store.didEnterBackground()
            case .active: store.active = true
            default: break
            }
        }
    }
}

struct RootView: View {
    @Environment(Store.self) private var store
    @Environment(\.scenePhase) private var phase

    var body: some View {
        @Bindable var store = store
        Group {
            if store.currentID == nil {
                HomeView()
            } else {
                GuideView()
            }
        }
        .overlay { if phase != .active { PrivacyCover() } }
        .sheet(isPresented: $store.showWelcome) {
            WelcomeView().environment(store).interactiveDismissDisabled()
        }
        .tint(accent)
        .preferredColorScheme(.dark)
    }
}
