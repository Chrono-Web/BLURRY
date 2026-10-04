import SwiftUI

/// View ▸ Queue: every file of this session, as a list. Double-click opens a
/// file in the guide; the Finder button shows it (the export, once there is one).
struct QueueWindow: View {
    @Environment(Store.self) private var store
    @Environment(\.openWindow) private var openWindow
    @State private var selection = Set<UUID>()

    var body: some View {
        Group {
            if store.items.isEmpty {
                Text(L.queueEmpty).foregroundStyle(.secondary)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else {
                List(store.items, selection: $selection) { item in
                    QueueRow(item: item, current: item.id == store.currentID)
                }
                .scrollContentBackground(.hidden)
                .contextMenu(forSelectionType: UUID.self) { ids in
                    if ids.count == 1, let id = ids.first {
                        Button(L.openInGuide) { open(id) }
                        Divider()
                    }
                    Button(L.remove) { store.remove(ids) }
                } primaryAction: { ids in
                    if let id = ids.first { open(id) }
                }
                .onDeleteCommand { store.remove(selection) }
            }
        }
        .background(WindowMaterial().ignoresSafeArea())
        .frame(minWidth: 460, idealWidth: 560, minHeight: 260, idealHeight: 420)
        .tint(accent)
        .preferredColorScheme(.dark)
    }

    private func open(_ id: UUID) {
        store.open(id)
        openWindow(id: "main")
    }
}

struct QueueRow: View {
    let item: Item
    let current: Bool

    var body: some View {
        HStack(spacing: 12) {
            Group {
                if let thumb = item.thumb {
                    Image(nsImage: thumb).resizable().aspectRatio(contentMode: .fill)
                } else {
                    Image(systemName: item.kind == .image ? "photo" : "film").foregroundStyle(.tertiary)
                }
            }
            .frame(width: 48, height: 36)
            .background(Color.black.opacity(0.3))
            .clipShape(RoundedRectangle(cornerRadius: 5, style: .continuous))
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(item.name).lineLimit(1).truncationMode(.middle)
                    if current { Circle().fill(Color.white).frame(width: 5, height: 5) }
                }
                HStack(spacing: 6) {
                    Circle().fill(color).frame(width: 6, height: 6)
                    Text(status).font(.caption).foregroundStyle(color == .secondary ? Color.secondary : color)
                    if let faces = item.faces, item.status != .noFaces {
                        Text("·  " + L.faces(faces)).font(.caption).foregroundStyle(.secondary)
                    }
                }
                .help(item.error)
            }
            Spacer()
            Button {
                NSWorkspace.shared.activateFileViewerSelecting([item.output ?? item.url])
            } label: {
                Image(nsImage: NSWorkspace.shared.icon(forFile: "/System/Library/CoreServices/Finder.app"))
                    .resizable()
                    .frame(width: 20, height: 20)
            }
            .buttonStyle(.borderless)
            .help(L.showInFinder)
        }
        .padding(.vertical, 3)
    }

    private var status: String {
        switch item.status {
        case .waiting: L.stWaiting
        case .analyzing: L.stAnalyzing(item.progress)
        case .ready: L.stReady
        case .review: L.stReview
        case .noFaces: L.stNoFaces
        case .exporting: L.stExporting(item.progress)
        case .exported: L.stExported
        case .error: L.stError
        case .cancelled: L.stCancelled
        }
    }

    private var color: Color {
        switch item.status {
        case .ready, .exported: accent
        case .review: .orange
        case .noFaces, .error: .red
        default: .secondary
        }
    }
}
