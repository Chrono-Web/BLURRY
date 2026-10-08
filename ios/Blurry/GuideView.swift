import BlurryKit
import SwiftUI
import UniformTypeIdentifiers

/// One file at a time: the steps on top, the picture in the middle, and below
/// it the settings, one step at a time, up to the check and the export. The
/// same flow as the Mac app's GuideView, laid out for a touch screen.
///
/// Nothing moves from one step to the next: the step bar is fixed at the top,
/// and the panel below the picture has the same height for every step and
/// for the box editor, so the picture keeps its place and size throughout
/// (a step that does not fit, with very large text, scrolls inside the panel).
struct GuideView: View {
    @Environment(Store.self) private var store
    @State private var confirmNoFaces = false
    @State private var chooseDestination = false
    @State private var showQueue = false
    @State private var showSettings = false

    /// Room for the tallest step (three levels and the buttons) at the default
    /// text size; it grows with Dynamic Type.
    @ScaledMetric(relativeTo: .body) private var panelHeight: CGFloat = 300

    var body: some View {
        if let item = store.current {
            NavigationStack {
                VStack(spacing: 0) {
                    // Hidden while correcting boxes (the bar holds Cancel and
                    // Done then), but it keeps its room.
                    StepBar(locked: item.busy || store.editing, item: item)
                        .opacity(store.editing ? 0 : 1)
                        .guideTip(.steps, L.tipSteps)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 6)
                    FloatingPicture(item: item)
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 22)
                        .frame(maxWidth: .infinity, maxHeight: .infinity)
                    Group {
                        if store.editing {
                            ScrollView { EditPanel(item: item) }
                                .scrollBounceBehavior(.basedOnSize)
                        } else {
                            VStack(spacing: 12) {
                                ScrollView { stepContent(item) }
                                    .scrollBounceBehavior(.basedOnSize)
                                nav(item)
                            }
                        }
                    }
                    .frame(maxWidth: 640)
                    .frame(height: panelHeight, alignment: .top)
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
                          contentTypes: [exportType], defaultFilename: store.pendingExport?.name) { result in
                store.finishExport((try? result.get()) != nil)
            } onCancellation: {
                store.finishExport(false)
            }
            .sheet(isPresented: shareShown) {
                if let url = store.pendingExport?.file {
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
        // Closing the sheet is not an answer: onCompletion or onCancellation is,
        // and it can arrive after the binding is set to false.
        Binding(get: { store.pendingExport?.destination == .files }, set: { _ in })
    }

    private var exporterDocument: CleanFile? {
        store.pendingExport.map { CleanFile(url: $0.file) }
    }

    private var exportType: UTType {
        switch (store.pendingExport?.name as NSString?)?.pathExtension {
        case "png": .png
        case "mp4": .mpeg4Movie
        default: .jpeg
        }
    }

    private var shareShown: Binding<Bool> {
        Binding(get: { store.pendingExport?.destination == .share }, set: { if !$0 { store.finishExport(false) } })
    }

    /// While correcting boxes the bar holds Cancel and Done, as in Photos;
    /// otherwise a new file, the position, the queue and settings.
    @ToolbarContentBuilder
    private func toolbar(_ item: Item) -> some ToolbarContent {
        if store.editing {
            ToolbarItem(placement: .cancellationAction) {
                Button(L.cancel) { store.endEditing(keep: false) }
            }
            ToolbarItem(placement: .principal) {
                Text(L.correct).font(.headline)
            }
            ToolbarItem(placement: .confirmationAction) {
                Button(L.doneEditing) { store.endEditing(keep: true) }.fontWeight(.semibold)
            }
        } else {
            ToolbarItem(placement: .topBarLeading) {
                Button { store.home() } label: { Image(systemName: "plus") }
                    .accessibilityLabel(L.homeTitle)
            }
            // The step in readable type, and where it stands: as iOS titles a
            // multi-step flow.
            ToolbarItem(placement: .principal) {
                let steps = store.steps
                let i = (steps.firstIndex(of: store.step) ?? 0) + 1
                let pos = store.position
                VStack(spacing: 1) {
                    Text(L.stepTitle(store.step)).font(.headline)
                    Text(L.stepCount(i, steps.count) + (pos.total > 1 ? "  ·  " + L.fileCount(pos.index, pos.total) : ""))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                .accessibilityElement(children: .combine)
            }
            ToolbarItemGroup(placement: .topBarTrailing) {
                if store.hasNext && !item.busy {
                    Button(L.skip) { store.skip() }
                }
                Button { showQueue = true } label: { Image(systemName: "list.bullet") }
                    .accessibilityLabel(L.queue)
                    .guideTip(.queue, L.tipQueue, actionTitle: L.done) { store.finishOnboarding() }
                Button { showSettings = true } label: { Image(systemName: "gearshape") }
                    .accessibilityLabel(L.settingsTitle)
            }
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
                ChoiceList(choices: Store.levelKeys.map {
                    Choice(id: $0, title: L.levelLabel($0), detail: L.levelDescription($0))
                }, selected: store.level) { store.level = $0 }
                if item.status == .noFaces && store.level != "high" {
                    Button(L.tryAggressive) { store.level = "high" }.controlSize(.small)
                }
            case .cover:
                ChoiceList(choices: [
                    Choice(id: "solid", title: L.modeSolid, detail: L.modeSolidHint, symbol: "rectangle.fill"),
                    Choice(id: "pixel", title: L.modePixel, detail: L.modePixelHint, symbol: "square.grid.3x3.fill"),
                ], selected: store.mode) { store.mode = $0 }
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
            case .audio:
                if item.hasAudio == false {
                    Text(L.noAudio).foregroundStyle(.secondary).multilineTextAlignment(.center)
                } else {
                    ChoiceList(choices: [
                        Choice(id: "remove", title: L.audioRemove, detail: L.audioRemoveHint, symbol: "speaker.slash.fill"),
                        Choice(id: "keep", title: L.audioKeep, detail: L.audioKeepHint, symbol: "speaker.wave.2.fill"),
                    ], selected: store.keepAudio ? "keep" : "remove") { store.keepAudio = $0 == "keep" }
                }
            case .result:
                VStack(spacing: 8) {
                    if item.kind == .video && item.analysed {
                        PlayerBar(item: item)
                    }
                    Text(L.summary(level: store.level, mode: store.mode,
                                   padding: Int((store.padding * 100).rounded()),
                                   audio: item.kind == .video && item.hasAudio != false ? store.keepAudio : nil))
                        .font(.callout)
                        .multilineTextAlignment(.center)
                    Text(L.alwaysRemoved).font(.caption).foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    resultStatus(item)
                }
            }
        }
        .frame(maxWidth: .infinity)
    }

    @ViewBuilder
    private func resultStatus(_ item: Item) -> some View {
        switch item.status {
        case .exporting:
            HStack(spacing: 8) {
                ProgressView()
                Text(item.kind == .video ? L.exporting(item.progress) : L.preparing)
                    .font(.caption).foregroundStyle(.secondary)
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
            if store.step != store.steps.first && !item.busy {
                Button(L.back) { move(-1) }.secondaryAction()
            }
            if store.step == .result {
                resultAction(item)
            } else {
                Button { move(1) } label: { Wide(L.next) }.primaryAction()
            }
        }
    }

    @ViewBuilder
    private func resultAction(_ item: Item) -> some View {
        switch item.status {
        case .exporting:
            Button {} label: { Wide(L.export) }.primaryAction().disabled(true)
        case .exported:
            Button {
                if store.hasNext { store.next() } else { store.home() }
            } label: {
                Wide(store.hasNext ? L.nextFile : L.done)
            }
            .primaryAction()
        case .error:
            Button { store.retry() } label: { Wide(L.retry, systemImage: "arrow.clockwise") }.primaryAction()
        default:
            Button {
                if item.status == .noFaces { confirmNoFaces = true } else { chooseDestination = true }
            } label: {
                Wide(L.export, systemImage: "square.and.arrow.up")
            }
            .primaryAction()
            .disabled(!item.analysed)
        }
    }

    private func move(_ delta: Int) {
        let steps = store.steps
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
                        if store.previewStale && !store.editing && !store.playing {
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(Color.black.opacity(0.45))
                                .overlay { ProgressView() }
                        }
                    }
                    .overlay {
                        if store.editing, let size = planSize { BoxEditor(planSize: size) }
                    }
                    .overlay(alignment: .bottom) { badge.offset(y: 14) }
                    .overlay(alignment: .topTrailing) { correctButton.padding(8) }
            } else {
                // Before the first picture (a video shows one only after its analysis).
                VStack(spacing: 12) {
                    ProgressView()
                    if item.status == .analyzing || item.status == .waiting {
                        Text(item.status == .waiting ? L.waiting
                             : item.kind == .video ? L.analyzing(item.progress) : L.analyzing)
                            .font(.caption.weight(.medium))
                            .foregroundStyle(.secondary)
                            .monospacedDigit()
                    }
                }
            }
        }
        .animation(.easeOut(duration: 0.2), value: store.step)
        .animation(.easeOut(duration: 0.15), value: store.previewStale)
    }

    /// The picture's own size, in which the boxes are expressed.
    private var planSize: CGSize? {
        if let p = item.plan { return CGSize(width: p.width, height: p.height) }
        if let v = item.videoPlan { return CGSize(width: v.width, height: v.height) }
        return nil
    }

    @ViewBuilder
    private var correctButton: some View {
        if item.analysed && !store.editing && !store.playing && item.status != .exporting {
            Button { store.startEditing() } label: {
                Label(item.status == .review ? L.checkBoxes : L.correct, systemImage: "square.dashed")
            }
            .buttonStyle(.bordered)
            .buttonBorderShape(.capsule)
            .controlSize(.small)
            .tint(item.status == .review ? .orange : .white)
            .background(.ultraThinMaterial, in: Capsule())   // legible on any picture
            .guideTip(.correct, L.tipCorrect)
        }
    }

    @ViewBuilder
    private var badge: some View {
        let label: (text: String, color: Color)? = switch item.status {
        case .waiting: (L.waiting, .secondary)
        case .analyzing: (item.kind == .video ? L.analyzing(item.progress) : L.analyzing, .secondary)
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

/// Where you are in the guide, under the navigation bar: one segment per
/// step, green when done, white for the current one. The step's name is in
/// the title; each segment can be tapped to go back to it.
struct StepBar: View {
    @Environment(Store.self) private var store
    let locked: Bool
    let item: Item

    var body: some View {
        let steps = store.steps
        let current = steps.firstIndex(of: store.step) ?? 0
        HStack(spacing: 6) {
            ForEach(Array(steps.enumerated()), id: \.element) { i, step in
                // A video without sound: its audio step has nothing to choose.
                let off = step == .audio && item.hasAudio == false
                Button { store.step = step } label: {
                    Capsule()
                        .fill(i < current ? accent : i == current ? Color.white : Color.white.opacity(off ? 0.08 : 0.22))
                        .frame(height: 4)
                        .frame(maxWidth: .infinity, minHeight: 28)   // a fingertip high
                        .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(locked)
                .accessibilityLabel(L.stepTitle(step))
                .accessibilityAddTraits(i == current ? .isSelected : [])
            }
        }
        .animation(.easeOut(duration: 0.2), value: store.step)
    }
}

/// Video, last step: play/pause, a timeline to drag with the covered stretches
/// marked in green, and the time.
struct PlayerBar: View {
    @Environment(Store.self) private var store
    let item: Item

    var body: some View {
        let position = item.index ?? 0
        HStack(spacing: 12) {
            Button {
                store.playing ? store.stopPlaying() : store.play()
            } label: {
                Image(systemName: store.playing ? "pause.fill" : "play.fill")
            }
            .buttonStyle(.bordered)
            .buttonBorderShape(.circle)
            .accessibilityLabel(store.playing ? L.pause : L.play)
            Timeline(frameCount: item.frameCount, ranges: item.coveredRanges, position: position) {
                store.seek(to: $0)
            }
            Text("\(clock(position, fps: item.fps)) / \(clock(item.frameCount, fps: item.fps))")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.secondary)
                .fixedSize()
        }
    }
}

func clock(_ frame: Int, fps: Double) -> String {
    let seconds = Int(Double(frame) / max(fps, 1))
    return String(format: "%02d:%02d", seconds / 60, seconds % 60)
}

struct Timeline: View {
    let frameCount: Int
    let ranges: [ClosedRange<Int>]
    let position: Int
    let seek: (Int) -> Void

    var body: some View {
        GeometryReader { geo in
            let w = geo.size.width
            let total = CGFloat(max(frameCount - 1, 1))
            let x = { (f: Int) in w * CGFloat(f) / total }
            ZStack(alignment: .leading) {
                Capsule().fill(Color.white.opacity(0.14)).frame(height: 4)
                Capsule().fill(Color.white.opacity(0.35)).frame(width: x(position), height: 4)
                ForEach(ranges, id: \.lowerBound) { r in
                    Rectangle()
                        .fill(accent.opacity(0.8))
                        .frame(width: max(2, x(r.upperBound) - x(r.lowerBound)), height: 4)
                        .offset(x: x(r.lowerBound))
                }
                Circle()
                    .fill(Color.white)
                    .frame(width: 16, height: 16)
                    .shadow(color: .black.opacity(0.4), radius: 2)
                    .offset(x: x(position) - 8)
            }
            .frame(height: geo.size.height)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { v in
                seek(Int((max(0, min(v.location.x, w)) / max(w, 1) * total).rounded()))
            })
        }
        .frame(height: 28)
        .accessibilityElement()
        .accessibilityValue("\(position + 1) / \(frameCount)")
    }
}

