import SwiftUI

/// The first-run guide: three tips shown as system popovers next to what they
/// talk about (step bar, "Correct the boxes", the saved file). Only an explicit
/// action advances the guide; dismissing a popover never opens another window.
/// No TipKit: it keeps a datastore in Application Support, and R2 wants that
/// folder not to exist.
@MainActor
struct TipContent: View {
    @Environment(Store.self) private var store
    let text: String
    var actionTitle = L.tipNext
    var action: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 8) {
                Circle().fill(accent).frame(width: 6, height: 6).padding(.top, 6)
                Text(text)
                    .font(.callout)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack(spacing: 12) {
                Button(L.tipSkip) { store.finishOnboarding() }
                    .buttonStyle(.borderless)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Button(actionTitle) { (action ?? store.nextTip)() }
                    .keyboardShortcut(.defaultAction)
            }
        }
        .padding(16)
        .frame(width: 300)
    }
}

extension View {
    /// Shows `tip` as a popover on this view while it is the guide's current tip.
    func guideTip(_ tip: Store.Tip, _ text: String, arrowEdge: Edge, actionTitle: String = L.tipNext,
                  action: (() -> Void)? = nil) -> some View {
        modifier(GuideTip(tip: tip, text: text, arrowEdge: arrowEdge, actionTitle: actionTitle, action: action))
    }
}

@MainActor
private struct GuideTip: ViewModifier {
    @Environment(Store.self) private var store
    let tip: Store.Tip
    let text: String
    let arrowEdge: Edge
    let actionTitle: String
    let action: (() -> Void)?
    @State private var dismissed = false

    func body(content: Content) -> some View {
        content.popover(isPresented: Binding(
            get: { store.tip == tip && !dismissed },
            set: { shown in if !shown { dismissed = true } }
        ), arrowEdge: arrowEdge) {
            TipContent(text: text, actionTitle: actionTitle, action: action)
        }
        .onChange(of: store.tip) { _, _ in dismissed = false }
    }
}
