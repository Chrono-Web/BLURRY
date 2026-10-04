import SwiftUI

/// Grouped native preferences, following Globy's settings window.
@MainActor
struct PreferencesView: View {
    @Environment(Store.self) private var store
    @State private var confirmUninstall = false

    var body: some View {
        @Bindable var store = store
        Form {
            Section {
                Picker(L.sensitivity, selection: $store.level) {
                    ForEach(levelKeys, id: \.self) { key in Text(L.levelLabel(key)).tag(key) }
                }
                Text(L.levelDescription(store.level)).font(.caption).foregroundStyle(.secondary)
                Picker(L.cover, selection: $store.mode) {
                    Text(L.modeSolid).tag("solid")
                    Text(L.modePixel).tag("pixel")
                }
                Text(store.mode == "solid" ? L.modeSolidHint : L.modePixelHint)
                    .font(.caption).foregroundStyle(.secondary)
                LabeledContent(L.margin) {
                    HStack(spacing: 10) {
                        Slider(value: $store.padding, in: 0...1, step: 0.05)
                            .accessibilityLabel(L.margin)
                            .frame(width: 180)
                        Text(store.padding, format: .percent.precision(.fractionLength(0)))
                            .monospacedDigit().foregroundStyle(.secondary)
                            .frame(width: 44, alignment: .trailing)
                    }
                }
                Button(L.restoreDefaults) {
                    store.level = "high"
                    store.mode = "solid"
                    store.padding = 0.25
                    store.keepAudio = false
                }
            } header: {
                Text(L.processing)
            } footer: {
                VStack(alignment: .leading, spacing: 6) {
                    footnote(L.preferencesEffect)
                    footnote(L.audioDefault)
                }
            }
            .disabled(store.items.contains { $0.status == .exporting })

            Section {
                RestartGuideCommand()
            } header: {
                Text(L.guideTitle)
            } footer: {
                footnote(L.guideDescription)
            }

            Section {
                Label(L.welcomeLine, systemImage: "lock.shield")
                    .font(.callout)
            } header: {
                Text(L.privacyTitle)
            } footer: {
                footnote(L.preferencesPrivacy)
            }

            Section {
                LabeledContent(L.version, value: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "—")
                Button(L.updates) { NSWorkspace.shared.open(releasesURL) }
            } header: {
                Text(L.updatesTitle)
            } footer: {
                footnote(L.updatesDescription)
            }

            Section {
                Button(L.uninstall, role: .destructive) { confirmUninstall = true }
                    .disabled(store.items.contains { $0.busy })
            } header: {
                Text(L.uninstallTitle)
            } footer: {
                footnote(L.uninstallDescription)
            }
        }
        .formStyle(.grouped)
        .frame(width: 500, height: 680)
        .tint(accent)
        .alert(L.uninstallQuestion, isPresented: $confirmUninstall) {
            Button(L.cancel, role: .cancel) {}
            Button(L.uninstall, role: .destructive) { store.uninstall() }
        } message: {
            Text(L.uninstallDescription)
        }
        .alert(L.uninstallErrorTitle, isPresented: Binding(
            get: { store.uninstallFailed },
            set: { store.uninstallFailed = $0 }
        )) {
            Button("OK") { store.uninstallFailed = false }
        } message: {
            Text(L.uninstallError)
        }
    }

    private func footnote(_ text: String) -> some View {
        Text(text).font(.caption).foregroundStyle(.secondary)
            .fixedSize(horizontal: false, vertical: true)
    }
}
