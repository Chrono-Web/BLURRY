import SwiftUI

/// An introduction before any file is loaded, with no extra persistent state.
@MainActor
struct WelcomeView: View {
    @Environment(Store.self) private var store
    @State private var page = 0

    var body: some View {
        VStack(spacing: 18) {
            // Blurry stays still at the top, centred; only the text below changes.
            MascotView(nudge: page)
                .frame(width: 88, height: 88)
            HStack(spacing: 8) {
                ForEach(0..<3) { index in
                    Capsule().fill(index == page ? accent : Color.white.opacity(0.15))
                        .frame(width: index == page ? 28 : 8, height: 5)
                }
            }
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
                        row("1", L.welcomeDrop)
                        row("2", L.welcomeReview)
                        row("3", L.welcomeExport)
                    }
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                    Text(L.welcomeOriginal).font(.callout).foregroundStyle(.secondary)
                }
            }
            .multilineTextAlignment(.center)
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
            HStack(spacing: 14) {
                Button(L.tipSkip) { store.finishOnboarding() }
                    .buttonStyle(.borderless).foregroundStyle(.secondary)
                Spacer()
                if page > 0 { Button(L.back) { page -= 1 } }
                Button(page == 2 ? L.start : L.next) {
                    if page == 2 { store.beginGuidedSession() } else { page += 1 }
                }
                .buttonStyle(.borderedProminent)
                .keyboardShortcut(.defaultAction)
            }
        }
        .padding(30)
        .frame(width: 500, height: 420)
        .background(WindowMaterial())
        .tint(accent)
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
