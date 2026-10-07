import SwiftUI

/// The boxes over the picture, in edit mode. One drag does everything, as on
/// the Mac: starting on a corner of the selected box resizes it, on a box
/// moves it, elsewhere draws a new one. A tap selects.
struct BoxEditor: View {
    @Environment(Store.self) private var store
    let planSize: CGSize

    private enum Op {
        case draw(CGPoint)
        case move(EditBox, CGRect)
        case resize(EditBox, CGRect, CGPoint)   // the fixed corner
    }

    @State private var op: Op?
    @State private var draft: CGRect?

    var body: some View {
        GeometryReader { geo in
            let s = geo.size.width / max(planSize.width, 1)
            ZStack(alignment: .topLeading) {
                ForEach(store.editBoxes) { box in
                    BoxShape(box: box, rect: scaled(rect(for: box), s), selected: box.id == store.selection)
                }
                if case .draw = op, let d = draft {
                    Rectangle()
                        .stroke(Color.white, style: StrokeStyle(lineWidth: 1.5, dash: [5, 3]))
                        .frame(width: d.width * s, height: d.height * s)
                        .offset(x: d.minX * s, y: d.minY * s)
                }
            }
            .frame(width: geo.size.width, height: geo.size.height, alignment: .topLeading)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0)
                .onChanged { changed($0, s) }
                .onEnded { ended($0, s) })
        }
    }

    private func rect(for box: EditBox) -> CGRect {
        switch op {
        case let .move(b, _) where b.id == box.id, let .resize(b, _, _) where b.id == box.id:
            draft ?? box.rect
        default:
            box.rect
        }
    }

    private func scaled(_ r: CGRect, _ s: CGFloat) -> CGRect {
        CGRect(x: r.minX * s, y: r.minY * s, width: r.width * s, height: r.height * s)
    }

    private func clamp(_ r: CGRect) -> CGRect {
        r.standardized.intersection(CGRect(origin: .zero, size: planSize))
    }

    private func changed(_ v: DragGesture.Value, _ s: CGFloat) {
        let start = CGPoint(x: v.startLocation.x / s, y: v.startLocation.y / s)
        let now = CGPoint(x: v.location.x / s, y: v.location.y / s)
        if op == nil { op = begin(at: start, s) }
        switch op {
        case let .draw(p):
            draft = clamp(CGRect(x: p.x, y: p.y, width: now.x - p.x, height: now.y - p.y))
        case let .move(_, r):
            var m = r.offsetBy(dx: now.x - start.x, dy: now.y - start.y)
            m.origin.x = min(max(0, m.minX), planSize.width - m.width)
            m.origin.y = min(max(0, m.minY), planSize.height - m.height)
            draft = m
        case let .resize(_, _, fixed):
            draft = clamp(CGRect(x: fixed.x, y: fixed.y, width: now.x - fixed.x, height: now.y - fixed.y))
        case nil:
            break
        }
    }

    private func begin(at p: CGPoint, _ s: CGFloat) -> Op {
        let grab = 22 / s   // a fingertip, at any zoom
        if let sel = store.selectedBox {
            let r = sel.rect
            let corners = [(CGPoint(x: r.minX, y: r.minY), CGPoint(x: r.maxX, y: r.maxY)),
                           (CGPoint(x: r.maxX, y: r.minY), CGPoint(x: r.minX, y: r.maxY)),
                           (CGPoint(x: r.minX, y: r.maxY), CGPoint(x: r.maxX, y: r.minY)),
                           (CGPoint(x: r.maxX, y: r.maxY), CGPoint(x: r.minX, y: r.minY))]
            for (corner, opposite) in corners where abs(corner.x - p.x) < grab && abs(corner.y - p.y) < grab {
                return .resize(sel, r, opposite)
            }
        }
        if let hit = hit(p) {
            store.selection = hit.id
            return .move(hit, hit.rect)
        }
        return .draw(p)
    }

    /// The box under the finger: the selected one first, then the smallest.
    private func hit(_ p: CGPoint) -> EditBox? {
        let under = store.editBoxes.filter { $0.rect.contains(p) }
        return under.first { $0.id == store.selection }
            ?? under.min { $0.rect.width * $0.rect.height < $1.rect.width * $1.rect.height }
    }

    private func ended(_ v: DragGesture.Value, _ s: CGFloat) {
        let tap = hypot(v.translation.width, v.translation.height) < 6
        let p = CGPoint(x: v.startLocation.x / s, y: v.startLocation.y / s)
        defer { op = nil; draft = nil }
        if tap {
            store.selection = hit(p)?.id
            return
        }
        switch op {
        case .draw:
            if let d = draft, d.width >= 4, d.height >= 4 { store.addBox(d) }
        case let .move(box, _), let .resize(box, _, _):
            if let d = draft, d.width >= 4, d.height >= 4 { store.moveBox(box, to: d) }
        case nil:
            break
        }
    }
}

/// One box: green found, orange uncertain, white drawn by hand. The selected
/// one is thicker, with corner handles.
struct BoxShape: View {
    let box: EditBox
    let rect: CGRect
    let selected: Bool

    var color: Color {
        if case .drawn = box.owner { return .white }
        return box.uncertain ? .orange : accent
    }

    var body: some View {
        ZStack(alignment: .topLeading) {
            Rectangle()
                .fill(color.opacity(selected ? 0.18 : 0.06))
                .overlay(Rectangle().stroke(color, lineWidth: selected ? 2 : 1.5))
                .frame(width: rect.width, height: rect.height)
            if selected {
                ForEach(0..<4, id: \.self) { k in
                    Circle()
                        .fill(Color.white)
                        .frame(width: 11, height: 11)
                        .offset(x: (k % 2 == 0 ? 0 : rect.width) - 5.5, y: (k < 2 ? 0 : rect.height) - 5.5)
                }
            }
        }
        .offset(x: rect.minX, y: rect.minY)
        .allowsHitTesting(false)
    }
}

/// Below the picture, in edit mode: what to do, the legend, the action for
/// the selected box, and Cancel / Done.
struct EditPanel: View {
    @Environment(Store.self) private var store

    var body: some View {
        VStack(spacing: 12) {
            Text(L.correct).font(.headline)
            Text(L.editHint)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
            HStack(spacing: 12) {
                dot(accent, L.legendFound)
                dot(.orange, L.legendUncertain)
                dot(.white, L.legendDrawn)
                Spacer()
                if let box = store.selectedBox {
                    Button(L.removeBox, role: .destructive) { store.removeBox(box) }
                        .font(.callout)
                }
            }
            .frame(height: 30)
            HStack(spacing: 10) {
                Button(L.cancel) { store.endEditing(keep: false) }.buttonStyle(SecondaryButtonStyle())
                Button(L.doneEditing) { store.endEditing(keep: true) }.buttonStyle(PrimaryButtonStyle())
            }
        }
    }

    private func dot(_ color: Color, _ text: String) -> some View {
        HStack(spacing: 5) {
            RoundedRectangle(cornerRadius: 1).stroke(color, lineWidth: 1.5).frame(width: 9, height: 9)
            Text(text).font(.caption).foregroundStyle(.secondary)
        }
    }
}
