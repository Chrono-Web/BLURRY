import SwiftUI

/// The first-run tips, as popovers next to what they talk about (also on a
/// phone). Only an explicit action advances the guide. No TipKit: it keeps a
/// datastore of its own, and R2 wants nothing but the allowed preferences.
struct TipContent: View {
    @Environment(Store.self) private var store
    let text: String
    var actionTitle = L.tipNext
    var action: (() -> Void)?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(alignment: .top, spacing: 8) {
                Circle().fill(accent).frame(width: 6, height: 6).padding(.top, 6)
                Text(text).font(.callout).fixedSize(horizontal: false, vertical: true)
            }
            HStack(spacing: 12) {
                Button(L.tipSkip) { store.finishOnboarding() }
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Spacer()
                Button(actionTitle) { (action ?? store.nextTip)() }.bold()
            }
        }
        .padding(16)
        .frame(width: 290)
        .presentationCompactAdaptation(.popover)
        .preferredColorScheme(.dark)
    }
}

extension View {
    func guideTip(_ tip: Store.Tip, _ text: String, actionTitle: String = L.tipNext,
                  action: (() -> Void)? = nil) -> some View {
        modifier(GuideTip(tip: tip, text: text, actionTitle: actionTitle, action: action))
    }
}

private struct GuideTip: ViewModifier {
    @Environment(Store.self) private var store
    let tip: Store.Tip
    let text: String
    let actionTitle: String
    let action: (() -> Void)?
    @State private var dismissed = false

    func body(content: Content) -> some View {
        content.popover(isPresented: Binding(
            get: { store.tip == tip && !dismissed },
            set: { shown in if !shown { dismissed = true } }
        )) {
            TipContent(text: text, actionTitle: actionTitle, action: action).environment(store)
        }
        .onChange(of: store.tip) { _, _ in dismissed = false }
    }
}

/// An introduction before any file is loaded, as on the Mac.
struct WelcomeView: View {
    @Environment(Store.self) private var store
    @State private var page = 0

    var body: some View {
        VStack(spacing: 18) {
            MascotView(nudge: page)
                .frame(width: 88, height: 88)
                .padding(.top, 24)
            HStack(spacing: 8) {
                ForEach(0..<3) { index in
                    Capsule().fill(index == page ? accent : Color.white.opacity(0.15))
                        .frame(width: index == page ? 28 : 8, height: 5)
                }
            }
            ScrollView {
                VStack(spacing: 14) {
                    Text(title).font(.title2.weight(.semibold))
                    if page == 0 {
                        Text(L.welcomeSubtitle).font(.title3)
                        Text(L.welcomePrivacy).foregroundStyle(.secondary)
                    } else if page == 1 {
                        Text(L.welcomeSafety)
                        Text(L.welcomeLimits).foregroundStyle(.secondary)
                    } else {
                        VStack(alignment: .leading, spacing: 12) {
                            row("1", L.welcomeChoose)
                            row("2", L.welcomeReview)
                            row("3", L.welcomeExport)
                        }
                        .multilineTextAlignment(.leading)
                        Text(L.welcomeOriginal).font(.callout).foregroundStyle(.secondary)
                    }
                }
                .multilineTextAlignment(.center)
                .padding(.horizontal, 8)
            }
            HStack(spacing: 10) {
                if page > 0 {
                    Button(L.back) { page -= 1 }.secondaryAction()
                }
                Button {
                    if page == 2 { store.beginGuidedSession() } else { page += 1 }
                } label: {
                    Wide(page == 2 ? L.start : L.next)
                }
                .primaryAction()
            }
            Button(L.tipSkip) { store.finishOnboarding() }
                .font(.callout)
                .foregroundStyle(.secondary)
        }
        .padding(24)
        .frame(maxWidth: 520)
        .presentationBackground(Color(white: 0.08))
        .preferredColorScheme(.dark)
    }

    private var title: String {
        switch page {
        case 0: L.welcomeTitle
        case 1: L.welcomeSafetyTitle
        default: L.welcomeWorkflowTitle
        }
    }

    private func row(_ number: String, _ text: String) -> some View {
        HStack(spacing: 12) {
            Text(number).font(.caption.monospaced().weight(.semibold))
                .foregroundStyle(accent).frame(width: 24, height: 24)
                .background(accent.opacity(0.12), in: Circle())
            Text(text)
        }
    }
}
