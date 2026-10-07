import BlurryKit
import SwiftUI
import UniformTypeIdentifiers

/// One file at a time: the picture on top, and below it the settings, one
/// step at a time, up to the check and the export. The same flow as the Mac
/// app's GuideView, laid out for a touch screen.
struct GuideView: View {
    @Environment(Store.self) private var store
    @Environment(\.horizontalSizeClass) private var sizeClass
    @State private var confirmNoFaces = false
    @State private var chooseDestination = false
    @State private var showQueue = false
    @State private var showSettings = false

    var body: some View {
        if let item = store.current {
            NavigationStack {
                VStack(spacing: 0) {
                    FloatingPicture(item: item)
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 22)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    Group {
                        if store.editing {
                            EditPanel()
                        } else {
                            VStack(spacing: 14) {
                                StepBar(locked: item.busy)
                                    .guideTip(.steps, L.tipSteps)
                                stepContent(item)
                                nav(item)
                            }
                        }
                    }
                    .frame(maxWidth: 640)
                    .padding(.horizontal, 16)
                    .padding(.bottom, 12)
                }
                .background(Color.black.ignoresSafeArea())
                .toolbar { toolbar(item) }
                .navigationBarTitleDisplayMode(.inline)
            }
            .alert(L.noFacesTitle, isPresented: $confirmNoFaces) {
                Button(L.exportAnyway, role: .destructive) { chooseDestination = true }
                Button(L.cancel, role: .cancel) {}
            } message: {
                Text(L.noFacesText)
            }
            .confirmationDialog(L.exportQuestion, isPresented: $chooseDestination, titleVisibility: .visible) {
                Button(L.saveToFiles) { store.export(to: .files) }
                Button(L.share) { store.export(to: .share) }
                Button(L.cancel, role: .cancel) {}
            } message: {
                Text(L.exportNote)
            }
            .fileExporter(isPresented: exporterShown, document: exporterDocument,
                          contentTypes: [store.pendingExport.map { $0.name.hasSuffix(".png") ? UTType.png : .jpeg } ?? .jpeg],
                          defaultFilename: store.pendingExport?.name) { result in
                store.finishExport((try? result.get()) != nil)
            } onCancellation: {
                store.finishExport(false)
            }
            .sheet(isPresented: shareShown) {
                if let url = store.pendingExport?.url {
                    ShareSheet(url: url) { done in store.finishExport(done) }
                        .presentationDetents([.medium, .large])
                        .ignoresSafeArea()
                }
            }
            .sheet(isPresented: $showQueue) { QueueView().environment(store) }
            .sheet(isPresented: $showSettings) { SettingsView().environment(store) }
        }
    }

    private var exporterShown: Binding<Bool> {
        Binding(get: { store.pendingExport?.destination == .files }, set: { if !$0 && store.pendingExport?.destination == .files { store.finishExport(false) } })
    }

    private var exporterDocument: CleanFile? {
        store.pendingExport.map { CleanFile(data: $0.data) }
    }

    private var shareShown: Binding<Bool> {
        Binding(get: { store.pendingExport?.destination == .share }, set: { if !$0 { store.finishExport(false) } })
    }

    @ToolbarContentBuilder
    private func toolbar(_ item: Item) -> some ToolbarContent {
        ToolbarItem(placement: .topBarLeading) {
            Button { store.home() } label: { Image(systemName: "plus") }
                .disabled(store.editing)
                .accessibilityLabel(L.homeTitle)
        }
        ToolbarItem(placement: .principal) {
            let pos = store.position
            if pos.total > 1 { SectionLabel(text: L.position(pos.index, pos.total)) }
        }
        ToolbarItemGroup(placement: .topBarTrailing) {
            if store.hasNext && !item.busy && !store.editing {
                Button(L.skip) { store.skip() }.font(.callout)
            }
            Button { showQueue = true } label: { Image(systemName: "list.bullet") }
                .disabled(store.editing)
                .accessibilityLabel(L.queue)
                .guideTip(.queue, L.tipQueue, actionTitle: L.done) { store.finishOnboarding() }
            Button { showSettings = true } label: { Image(systemName: "gearshape") }
                .disabled(store.editing)
                .accessibilityLabel(L.settingsTitle)
        }
    }

    // MARK: steps

    @ViewBuilder
    private func stepContent(_ item: Item) -> some View {
        @Bindable var store = store
        VStack(spacing: 12) {
            if store.step == .result && store.usingPrevious {
                HStack(spacing: 6) {
                    Text(L.sameSettings).foregroundStyle(.secondary)
                    Button(L.change) { store.step = .sensitivity }
                }
                .font(.callout.weight(.medium))
            } else {
                Text(L.stepQuestion(store.step)).font(.headline)
            }
            switch store.step {
            case .sensitivity:
                cards {
                    ForEach(Store.levelKeys, id: \.self) { key in
                        OptionCard(title: L.levelLabel(key), hint: L.levelDescription(key),
                                   selected: store.level == key) { store.level = key }
                    }
                }
                if item.status == .noFaces && store.level != "high" {
                    Button(L.tryAggressive) { store.level = "high" }.controlSize(.small)
                }
            case .cover:
                HStack(spacing: 10) {
                    OptionCard(title: L.modeSolid, hint: L.modeSolidHint, symbol: "rectangle.fill",
                               selected: store.mode == "solid") { store.mode = "solid" }
                    OptionCard(title: L.modePixel, hint: L.modePixelHint, symbol: "square.grid.3x3.fill",
                               selected: store.mode == "pixel") { store.mode = "pixel" }
                }
            case .margin:
                VStack(spacing: 8) {
                    HStack(spacing: 14) {
                        Slider(value: $store.padding, in: 0...0.6, step: 0.05)
                            .accessibilityLabel(L.margin)
                        Text("\(Int((store.padding * 100).rounded()))%")
                            .font(.system(size: 14, design: .monospaced))
                            .frame(width: 44, alignment: .trailing)
                    }
                    Text(L.marginHint).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
                }
            case .result:
                VStack(spacing: 8) {
                    Text(L.summary(level: store.level, mode: store.mode,
                                   padding: Int((store.padding * 100).rounded())))
                        .font(.system(size: 12, design: .monospaced))
                    Text(L.alwaysRemoved).font(.caption).foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    resultStatus(item)
                }
            }
        }
        .frame(maxWidth: .infinity)
    }

    /// Three cards side by side when there is room, one under the other on a phone.
    @ViewBuilder
    private func cards<Content: View>(@ViewBuilder _ content: () -> Content) -> some View {
        if sizeClass == .regular {
            HStack(spacing: 10) { content() }
        } else {
            VStack(spacing: 8) { content() }
        }
    }

    @ViewBuilder
    private func resultStatus(_ item: Item) -> some View {
        switch item.status {
        case .exporting:
            HStack(spacing: 8) {
                ProgressView()
                Text(L.preparing).font(.caption).foregroundStyle(.secondary)
            }
        case .exported:
            Label("\(item.exportedAs ?? L.saved): \(item.outputName)", systemImage: "checkmark.circle.fill")
                .font(.callout)
                .foregroundStyle(accent)
                .lineLimit(1)
                .truncationMode(.middle)
        case .error:
            Label(item.error, systemImage: "exclamationmark.triangle.fill")
                .font(.callout)
                .foregroundStyle(.red)
                .lineLimit(3)
        default:
            EmptyView()
        }
    }

    // MARK: navigation

    private func nav(_ item: Item) -> some View {
        HStack(spacing: 10) {
            if store.step != Step.allCases.first && !item.busy {
                Button(L.back) { move(-1) }.buttonStyle(SecondaryButtonStyle())
            }
            if store.step == .result {
                resultAction(item)
            } else {
                Button(L.next) { move(1) }.buttonStyle(PrimaryButtonStyle())
            }
        }
    }

    @ViewBuilder
    private func resultAction(_ item: Item) -> some View {
        switch item.status {
        case .exporting:
            Button(L.export) {}.buttonStyle(PrimaryButtonStyle()).disabled(true)
        case .exported:
            Button(store.hasNext ? L.nextFile : L.done) {
                if store.hasNext { store.next() } else { store.home() }
            }
            .buttonStyle(PrimaryButtonStyle())
        case .error:
            Button(L.retry) { store.retry() }.buttonStyle(PrimaryButtonStyle())
        default:
            Button(L.export) {
                if item.status == .noFaces { confirmNoFaces = true } else { chooseDestination = true }
            }
            .buttonStyle(PrimaryButtonStyle())
            .disabled(!item.analysed)
        }
    }

    private func move(_ delta: Int) {
        let steps = Step.allCases
        guard let i = steps.firstIndex(of: store.step) else { return }
        store.step = steps[max(0, min(steps.count - 1, i + delta))]
    }
}

/// The file: the original while choosing the sensitivity (faces outlined in
/// green), then covered as the export will be.
struct FloatingPicture: View {
    @Environment(Store.self) private var store
    let item: Item

    var body: some View {
        ZStack {
            if let image = store.preview {
                Image(decorative: image, scale: 1)
                    .resizable()
                    .interpolation(.high)
                    .aspectRatio(contentMode: .fit)
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(hairline, lineWidth: 1))
                    .overlay {
                        if store.previewStale && !store.editing {
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(Color.black.opacity(0.45))
                                .overlay { ProgressView() }
                        }
                    }
                    .overlay {
                        if store.editing, let plan = item.plan {
                            BoxEditor(planSize: CGSize(width: plan.width, height: plan.height))
                        }
                    }
                    .overlay(alignment: .bottom) { badge.offset(y: 14) }
                    .overlay(alignment: .topTrailing) { correctButton.padding(8) }
            } else {
                ProgressView()
            }
        }
        .animation(.easeOut(duration: 0.2), value: store.step)
        .animation(.easeOut(duration: 0.15), value: store.previewStale)
    }

    @ViewBuilder
    private var correctButton: some View {
        if item.analysed && !store.editing && item.status != .exporting {
            Button { store.startEditing() } label: {
                Label(item.status == .review ? L.checkBoxes : L.correct, systemImage: "square.dashed")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(item.status == .review ? Color.orange : Color.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 7)
                    .background(.regularMaterial, in: Capsule())
                    .overlay(Capsule().strokeBorder(hairline, lineWidth: 1))
            }
            .buttonStyle(.plain)
            .guideTip(.correct, L.tipCorrect)
        }
    }

    @ViewBuilder
    private var badge: some View {
        let label: (text: String, color: Color)? = switch item.status {
        case .waiting: (L.waiting, .secondary)
        case .analyzing: (L.analyzing, .secondary)
        case .noFaces: (L.noFaceFound, .red)
        case .review: (L.facesFound(item.faces ?? 0), .orange)
        case .ready, .exported, .exporting: (L.facesFound(item.faces ?? 0), accent)
        case .error: nil
        }
        if let label {
            HStack(spacing: 7) {
                if item.status == .analyzing || item.status == .waiting {
                    ProgressView().controlSize(.mini)
                } else {
                    Circle().fill(label.color).frame(width: 6, height: 6)
                }
                Text(label.text).font(.caption.weight(.medium))
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(.regularMaterial, in: Capsule())
            .overlay(Capsule().strokeBorder(hairline, lineWidth: 1))
            .accessibilityHint(item.status == .review ? L.toReview : "")
        }
    }
}

/// Where you are in the guide: done steps green, the current one white.
/// Every step can be tapped.
struct StepBar: View {
    @Environment(Store.self) private var store
    let locked: Bool

    var body: some View {
        let steps = Step.allCases
        let current = steps.firstIndex(of: store.step) ?? 0
        HStack(spacing: 14) {
            ForEach(Array(steps.enumerated()), id: \.element) { i, step in
                Button { store.step = step } label: {
                    HStack(spacing: 5) {
                        Circle()
                            .fill(i < current ? accent : i == current ? Color.white : Color.white.opacity(0.2))
                            .frame(width: 5, height: 5)
                        Text(L.stepTitle(step))
                            .font(.system(size: 9, weight: .medium, design: .monospaced))
                            .tracking(1)
                            .foregroundStyle(i == current ? Color.white : Color.white.opacity(i < current ? 0.6 : 0.3))
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                    }
                    .padding(.vertical, 6)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(locked)
            }
        }
    }
}
