import SwiftUI

/// Settings, as the Mac app's preferences: the remembered choices, privacy,
/// the guide, and about. Plus the memory peak, to find out on a real device
/// how large a photo it can handle (PIANO_BLURRY 5b).
struct SettingsView: View {
    @Environment(Store.self) private var store
    @Environment(\.dismiss) private var dismiss
    @State private var peak = Pictures.peakMemory()

    var body: some View {
        @Bindable var store = store
        NavigationStack {
            Form {
                Section {
                    Picker(L.sensitivity, selection: $store.level) {
                        ForEach(Store.levelKeys, id: \.self) { Text(L.levelLabel($0)).tag($0) }
                    }
                    Picker(L.cover, selection: $store.mode) {
                        Text(L.modeSolid).tag("solid")
                        Text(L.modePixel).tag("pixel")
                    }
                    LabeledContent(L.margin) {
                        HStack(spacing: 10) {
                            Slider(value: $store.padding, in: 0...1, step: 0.05)
                                .accessibilityLabel(L.margin)
                            Text(store.padding, format: .percent.precision(.fractionLength(0)))
                                .monospacedDigit().foregroundStyle(.secondary)
                                .frame(width: 48, alignment: .trailing)
                        }
                    }
                    Button(L.restoreDefaults) {
                        store.level = "high"
                        store.mode = "solid"
                        store.padding = 0.25
                    }
                } header: {
                    Text(L.processing)
                } footer: {
                    Text(L.settingsEffect)
                }
                .disabled(store.items.contains { $0.status == .exporting })

                Section {
                    Button(L.restartGuide) {
                        dismiss()
                        store.home()
                        store.restartOnboarding()
                    }
                } header: {
                    Text(L.guideTitle)
                }

                Section {
                    Label(L.welcomeLine, systemImage: "lock.shield")
                } header: {
                    Text(L.privacyTitle)
                } footer: {
                    Text(L.settingsPrivacy)
                }

                Section {
                    LabeledContent(L.memoryPeak, value: "\(peak / 1_048_576) MB")
                } header: {
                    Text(L.memoryTitle)
                } footer: {
                    Text(L.memoryDescription)
                }

                Section {
                    LabeledContent(L.version, value: Bundle.main.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String ?? "")
                    Link(L.updates, destination: releasesURL)
                } header: {
                    Text(L.aboutTitle)
                } footer: {
                    Text(L.updatesDescription)
                }
            }
            .navigationTitle(L.settingsTitle)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .confirmationAction) { Button(L.close) { dismiss() } }
            }
            .onAppear { peak = Pictures.peakMemory() }
        }
        .preferredColorScheme(.dark)
    }
}
