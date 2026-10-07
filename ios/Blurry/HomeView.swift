import BlurryKit
import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

/// The first screen: choose photos from the library (PHPicker: Blurry never
/// asks for access to the library) or from Files.
struct HomeView: View {
    @Environment(Store.self) private var store
    @State private var picked: [PhotosPickerItem] = []
    @State private var importing = false
    @State private var showQueue = false
    @State private var showSettings = false
    @State private var loading = false

    var body: some View {
        NavigationStack {
            VStack(spacing: 22) {
                Spacer()
                ZStack {
                    CornerTicks(length: 22)
                        .stroke(Color.white.opacity(0.55), lineWidth: 1.5)
                        .frame(width: 150, height: 150)
                    MascotView()
                        .frame(width: 92, height: 92)
                }
                Text(L.homeTitle)
                    .font(.title2.weight(.semibold))
                    .multilineTextAlignment(.center)
                VStack(spacing: 12) {
                    PhotosPicker(selection: $picked, matching: .images, preferredItemEncoding: .current,
                                 photoLibrary: .shared()) {
                        Label(L.choosePhotos, systemImage: "photo.on.rectangle")
                    }
                    .buttonStyle(PrimaryButtonStyle())
                    Button { importing = true } label: {
                        Label(L.chooseFiles, systemImage: "folder").frame(maxWidth: .infinity)
                    }
                    .buttonStyle(SecondaryButtonStyle())
                }
                .frame(maxWidth: 360)
                .disabled(loading || store.fatal != nil)
                if loading { ProgressView() }
                Text(store.onboarded ? L.homeHint : L.welcomeLine)
                    .font(.footnote)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 360)
                if let notice = store.notice {
                    Text(notice).font(.footnote).foregroundStyle(.orange)
                }
                if let fatal = store.fatal {
                    Text(fatal).font(.footnote).foregroundStyle(.red).multilineTextAlignment(.center)
                }
                Spacer()
            }
            .padding(.horizontal, 24)
            .frame(maxWidth: .infinity)
            .background(Color.black.ignoresSafeArea())
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button { showSettings = true } label: { Image(systemName: "gearshape") }
                        .accessibilityLabel(L.settingsTitle)
                }
                if !store.items.isEmpty {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button { showQueue = true } label: { Label(L.queue, systemImage: "list.bullet") }
                    }
                }
            }
        }
        .onChange(of: picked) { _, items in
            guard !items.isEmpty else { return }
            picked = []
            Task { await load(items) }
        }
        .fileImporter(isPresented: $importing,
                      allowedContentTypes: ImageIn.extensions.compactMap { UTType(filenameExtension: $0) },
                      allowsMultipleSelection: true) { result in
            guard case let .success(urls) = result else { return }
            store.add(urls.compactMap(read))
        }
        .sheet(isPresented: $showQueue) { QueueView().environment(store) }
        .sheet(isPresented: $showSettings) { SettingsView().environment(store) }
    }

    /// The photos as they are in the library (current encoding: HEIC stays
    /// HEIC, with its metadata, so that Blurry can report what it removes).
    private func load(_ items: [PhotosPickerItem]) async {
        loading = true
        defer { loading = false }
        var files: [(name: String?, ext: String, data: Data)] = []
        for item in items {
            guard let data = try? await item.loadTransferable(type: Data.self) else {
                store.notice = L.unreadable
                continue
            }
            let type = item.supportedContentTypes.first { ImageIn.extensions.contains($0.preferredFilenameExtension ?? "") }
            files.append((name: nil, ext: type?.preferredFilenameExtension ?? "jpg", data: data))
        }
        store.add(files)
        Privacy.clearCopies()   // the picker may have left copies in tmp/
    }

    /// A file from Files, read into memory under its security scope.
    private func read(_ url: URL) -> (name: String?, ext: String, data: Data)? {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else { return nil }
        return (name: url.lastPathComponent, ext: url.pathExtension, data: data)
    }
}
