import BlurryKit
import PhotosUI
import SwiftUI
import UniformTypeIdentifiers

/// The first screen: choose photos and videos from the library (PHPicker:
/// Blurry never asks for access to the library) or from Files.
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
                    PhotosPicker(selection: $picked, matching: .any(of: [.images, .videos]),
                                 preferredItemEncoding: .current, photoLibrary: .shared()) {
                        Wide(L.choosePhotos, systemImage: "photo.on.rectangle")
                    }
                    .primaryAction()
                    Button { importing = true } label: {
                        Wide(L.chooseFiles, systemImage: "folder")
                    }
                    .secondaryAction()
                }
                .frame(maxWidth: 360)
                .disabled(loading || store.fatal != nil)
                if loading {
                    HStack(spacing: 8) {
                        ProgressView()
                        Text(L.copying).font(.footnote).foregroundStyle(.secondary)
                    }
                }
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
                      allowedContentTypes: ImageIn.extensions.compactMap { UTType(filenameExtension: $0) } + Videos.types,
                      allowsMultipleSelection: true) { result in
            guard case let .success(urls) = result else { return }
            Task { await importFiles(urls) }
        }
        .sheet(isPresented: $showQueue) { QueueView().environment(store) }
        .sheet(isPresented: $showSettings) { SettingsView().environment(store) }
    }

    /// The files as they are in the library (current encoding: HEIC stays HEIC,
    /// with its metadata, so that Blurry can report what it removes). Videos
    /// are copied into the app's private temporary folder.
    private func load(_ items: [PhotosPickerItem]) async {
        loading = true
        defer { loading = false }
        var photos: [(name: String?, ext: String, data: Data)] = []
        var videos: [(name: String?, url: URL)] = []
        for item in items {
            if item.supportedContentTypes.contains(where: { $0.conforms(to: .movie) }) {
                if let movie = try? await item.loadTransferable(type: PickedMovie.self),
                   VideoIn.extensions.contains(movie.url.pathExtension.lowercased()) {
                    videos.append((name: nil, url: movie.url))
                } else {
                    store.notice = L.unreadable
                }
                continue
            }
            guard let data = try? await item.loadTransferable(type: Data.self) else {
                store.notice = L.unreadable
                continue
            }
            let type = item.supportedContentTypes.first { ImageIn.extensions.contains($0.preferredFilenameExtension ?? "") }
            photos.append((name: nil, ext: type?.preferredFilenameExtension ?? "jpg", data: data))
        }
        if !photos.isEmpty { store.add(photos) }
        if !videos.isEmpty { store.addVideos(videos) }
    }

    /// Files chosen in Files: photos read into memory, videos copied, each
    /// under its security scope.
    private func importFiles(_ urls: [URL]) async {
        loading = true
        defer { loading = false }
        var videos: [(name: String?, url: URL)] = []
        var photos: [(name: String?, ext: String, data: Data)] = []
        for url in urls {
            if VideoIn.extensions.contains(url.pathExtension.lowercased()) {
                let scoped = url.startAccessingSecurityScopedResource()
                defer { if scoped { url.stopAccessingSecurityScopedResource() } }
                if let copy = try? Videos.copy(url) { videos.append((name: url.lastPathComponent, url: copy)) }
                else { store.notice = L.unreadable }
            } else if let photo = read(url) {
                photos.append(photo)
            }
        }
        if !photos.isEmpty { store.add(photos) }
        if !videos.isEmpty { store.addVideos(videos) }
    }

    /// A file from Files, read into memory under its security scope.
    private func read(_ url: URL) -> (name: String?, ext: String, data: Data)? {
        let scoped = url.startAccessingSecurityScopedResource()
        defer { if scoped { url.stopAccessingSecurityScopedResource() } }
        guard let data = try? Data(contentsOf: url) else { return nil }
        return (name: url.lastPathComponent, ext: url.pathExtension, data: data)
    }
}

/// A video from the photo library, copied by the system and then into the
/// app's private temporary folder.
struct PickedMovie: Transferable {
    let url: URL

    static var transferRepresentation: some TransferRepresentation {
        FileRepresentation(contentType: .movie) { movie in
            SentTransferredFile(movie.url)
        } importing: { received in
            PickedMovie(url: try Videos.copy(received.file))
        }
    }
}
