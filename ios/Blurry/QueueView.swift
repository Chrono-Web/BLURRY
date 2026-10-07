import SwiftUI

/// Every file of this session, with its status. A tap opens it in the guide.
struct QueueView: View {
    @Environment(Store.self) private var store
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        NavigationStack {
            List {
                if store.items.isEmpty {
                    Text(L.queueEmpty).foregroundStyle(.secondary)
                }
                ForEach(store.items) { item in
                    Button {
                        store.open(item.id)
                        dismiss()
                    } label: {
                        row(item)
                    }
                    .disabled(item.busy)
                }
                .onDelete { offsets in
                    let ids = Set(offsets.map { store.items[$0].id }.filter { id in
                        !(store.items.first { $0.id == id }?.busy ?? false)
                    })
                    store.remove(ids)
                }
            }
            .navigationTitle(L.queue)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button(L.clearQueue, role: .destructive) { store.clear() }
                        .disabled(store.items.isEmpty)
                }
                ToolbarItem(placement: .confirmationAction) { Button(L.close) { dismiss() } }
            }
        }
        .preferredColorScheme(.dark)
    }

    private func row(_ item: Item) -> some View {
        HStack(spacing: 12) {
            if let thumb = item.thumb {
                Image(decorative: thumb, scale: 1)
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: 44, height: 44)
                    .clipShape(RoundedRectangle(cornerRadius: 6, style: .continuous))
            } else {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .fill(Color.white.opacity(0.06))
                    .frame(width: 44, height: 44)
            }
            VStack(alignment: .leading, spacing: 3) {
                Text(item.name).lineLimit(1).truncationMode(.middle).foregroundStyle(.primary)
                HStack(spacing: 6) {
                    Text(status(item)).foregroundStyle(color(item))
                    if let faces = item.faces, item.analysed { Text("· " + L.faces(faces)).foregroundStyle(.secondary) }
                }
                .font(.caption)
            }
        }
    }

    private func status(_ item: Item) -> String {
        switch item.status {
        case .waiting: L.stWaiting
        case .analyzing: L.stAnalyzing
        case .ready: L.stReady
        case .review: L.stReview
        case .noFaces: L.stNoFaces
        case .exporting: L.stExporting
        case .exported: L.stExported
        case .error: L.stError
        }
    }

    private func color(_ item: Item) -> Color {
        switch item.status {
        case .review: .orange
        case .noFaces, .error: .red
        case .exported, .ready: accent
        default: .secondary
        }
    }
}
