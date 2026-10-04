import SwiftUI
import UniformTypeIdentifiers

let accent = Color(red: 0x49 / 255, green: 0xDC / 255, blue: 0x18 / 255)
let hairline = Color.white.opacity(0.10)

/// The window's background: the system's own blurred material.
struct WindowMaterial: NSViewRepresentable {
    func makeNSView(context: Context) -> NSVisualEffectView {
        let view = NSVisualEffectView()
        view.material = .underWindowBackground
        view.blendingMode = .behindWindow
        view.state = .active
        return view
    }

    func updateNSView(_ view: NSVisualEffectView, context: Context) {}
}

/// Four L-shaped corner marks.
struct CornerTicks: Shape {
    var length: CGFloat = 12

    func path(in r: CGRect) -> Path {
        var p = Path()
        for (x, y, dx, dy) in [(r.minX, r.minY, 1.0, 1.0), (r.maxX, r.minY, -1.0, 1.0),
                               (r.minX, r.maxY, 1.0, -1.0), (r.maxX, r.maxY, -1.0, -1.0)] {
            p.move(to: CGPoint(x: x + dx * length, y: y))
            p.addLine(to: CGPoint(x: x, y: y))
            p.addLine(to: CGPoint(x: x, y: y + dy * length))
        }
        return p
    }
}

/// The drop frame: corner ticks, and green while something is dragged over it.
@MainActor
struct DropFrame: View {
    let active: Bool

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(active ? accent.opacity(0.07) : Color.white.opacity(0.025))
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(active ? accent.opacity(0.7) : Color.white.opacity(0.12),
                              style: StrokeStyle(lineWidth: 1, dash: active ? [] : [5, 4]))
            CornerTicks()
                .stroke(active ? accent : Color.white.opacity(0.55), lineWidth: 1)
                .padding(10)
        }
        .animation(.easeOut(duration: 0.15), value: active)
    }
}

/// Chrono's small monospace capitals, for section labels.
@MainActor
struct SectionLabel: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .medium, design: .monospaced))
            .tracking(1.5)
            .foregroundStyle(.secondary)
    }
}

/// White button with black text: the one primary action.
struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var enabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.semibold))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 9)
            .foregroundStyle(enabled ? Color.black : Color.white.opacity(0.35))
            .background(
                RoundedRectangle(cornerRadius: 8, style: .continuous)
                    .fill(enabled ? Color.white.opacity(configuration.isPressed ? 0.8 : 1) : Color.white.opacity(0.08))
            )
    }
}

@MainActor
struct ContentView: View {
    @Environment(Store.self) private var store
    @Binding var choosing: Bool
    @State private var targeted = false

    var body: some View {
        @Bindable var store = store
        Group {
            if store.currentID == nil {
                landing
            } else {
                GuideView(targeted: targeted)
            }
        }
        .background(WindowMaterial().ignoresSafeArea())
        .dropDestination(for: URL.self) { urls, _ in
            store.add(urls)
            return true
        } isTargeted: { targeted = $0 }
        .fileImporter(isPresented: $choosing,
                      allowedContentTypes: imageExtensions.union(videoExtensions).compactMap {
                          UTType(filenameExtension: $0)
                      },
                      allowsMultipleSelection: true) { result in
            Privacy.scrubAfterPanel()
            if case let .success(urls) = result { store.add(urls) }
        }
        .sheet(isPresented: $store.showWelcome) {
            WelcomeView().environment(store)
                .interactiveDismissDisabled()
        }
        .tint(accent)
        .preferredColorScheme(.dark)
    }

    private var landing: some View {
        VStack(spacing: 18) {
            Image(systemName: "photo.on.rectangle.angled")
                .font(.system(size: 46, weight: .ultraLight))
                .foregroundStyle(targeted ? accent : .secondary)
            Text(L.dropTitle)
                .font(.title3.weight(.medium))
            Button(L.chooseFiles) { choosing = true }
                .controlSize(.large)
            if !store.onboarded {
                Text(L.welcomeLine)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .padding(.top, 4)
            }
            if store.engineMissing {
                Text(L.engineMissing).font(.caption).foregroundStyle(.orange)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(DropFrame(active: targeted))
        .padding(.horizontal, 16)
        .padding(.bottom, 16)
        .padding(.top, 34) // room for the traffic lights
        .frame(minWidth: 440, idealWidth: 520, minHeight: 380, idealHeight: 440)
        .ignoresSafeArea()
    }
}
