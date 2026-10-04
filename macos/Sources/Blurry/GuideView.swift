import SwiftUI

/// After the drop: the file floats in the middle, and below it the settings,
/// one step at a time, up to the check and the export.
///
/// Navigation follows the HIG for assistants: Back and Continue side by side at
/// the bottom right (Return continues, ⌘[ goes back, Esc does nothing); the
/// step bar can be clicked; the steps are fixed from the start.
struct GuideView: View {
    @Environment(Store.self) private var store
    @Environment(\.openWindow) private var openWindow
    let targeted: Bool
    @State private var confirmNoFaces = false

    var body: some View {
        if let item = store.current {
            VStack(spacing: 0) {
                header(item)
                FloatingPicture(item: item)
                    .padding(.horizontal, 40)
                    .padding(.top, 6)
                    .padding(.bottom, 22)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                if store.editing {
                    EditPanel(item: item)
                        .frame(height: item.kind == .video ? 216 : 188, alignment: .bottom)
                } else {
                    StepBar(locked: item.status == .exporting)
                        .guideTip(.steps, L.tipSteps, arrowEdge: .top)
                        .padding(.bottom, 16)
                    stepContent(item)
                        .frame(height: 124)
                        .padding(.horizontal, 40)
                    nav(item)
                        .padding(.horizontal, 28)
                        .padding(.bottom, 20)
                }
            }
            .overlay {
                if targeted { DropFrame(active: true).padding(10).padding(.top, 30).allowsHitTesting(false) }
            }
            .frame(minWidth: 720, idealWidth: 820, minHeight: 700, idealHeight: 780)
            .ignoresSafeArea()
            .alert(L.noFacesTitle, isPresented: $confirmNoFaces) {
                Button(L.exportAnyway, role: .destructive) { chooseOutput(item) }
                Button(L.cancel, role: .cancel) {}
            } message: {
                Text(L.noFacesText)
            }
        }
    }

    private func header(_ item: Item) -> some View {
        HStack(spacing: 14) {
            Spacer()
            let pos = store.position
            if pos.total > 1 && !store.editing {
                if store.hasNext && !item.busy {
                    Button(L.skip) { store.skip() }
                        .buttonStyle(.borderless)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                SectionLabel(text: L.position(pos.index, pos.total))
            }
        }
        .padding(.horizontal, 20)
        .frame(height: 40)
    }

    // MARK: steps

    @ViewBuilder
    private func stepContent(_ item: Item) -> some View {
        @Bindable var store = store
        VStack(spacing: 14) {
            if store.step == .result && store.usingPrevious {
                HStack(spacing: 6) {
                    Text(L.sameSettings).foregroundStyle(.secondary)
                    Button(L.change) { store.step = .sensitivity }
                        .buttonStyle(.borderless)
                }
                .font(.title3.weight(.medium))
            } else {
                Text(L.stepQuestion(store.step))
                    .font(.title3.weight(.medium))
            }
            switch store.step {
            case .sensitivity:
                HStack(spacing: 10) {
                    ForEach(levelKeys, id: \.self) { key in
                        OptionCard(title: L.levelLabel(key), hint: L.levelDescription(key),
                                   selected: store.level == key) { store.level = key }
                    }
                }
                if item.status == .noFaces && store.level != "high" {
                    Button(L.tryAggressive) { store.level = "high" }
                        .controlSize(.small)
                }
            case .cover:
                HStack(spacing: 10) {
                    OptionCard(title: L.modeSolid, hint: L.modeSolidHint, symbol: "rectangle.fill",
                               selected: store.mode == "solid") { store.mode = "solid" }
                    OptionCard(title: L.modePixel, hint: L.modePixelHint, symbol: "square.grid.3x3.fill",
                               selected: store.mode == "pixel") { store.mode = "pixel" }
                }
                .frame(maxWidth: 460)
            case .margin:
                VStack(spacing: 10) {
                    HStack(spacing: 14) {
                        Slider(value: $store.padding, in: 0...0.6)
                        Text("\(Int((store.padding * 100).rounded()))%")
                            .font(.system(size: 13, design: .monospaced))
                            .frame(width: 40, alignment: .trailing)
                    }
                    Text(L.marginHint).font(.caption).foregroundStyle(.secondary)
                }
                .frame(maxWidth: 460)
            case .audio:
                if item.hasAudio == false {
                    Text(L.noAudio).foregroundStyle(.secondary)
                } else {
                    HStack(spacing: 10) {
                        OptionCard(title: L.audioRemove, hint: L.audioRemoveHint, symbol: "speaker.slash.fill",
                                   selected: !store.keepAudio) { store.keepAudio = false }
                        OptionCard(title: L.audioKeep, hint: L.audioKeepHint, symbol: "speaker.wave.2.fill",
                                   selected: store.keepAudio, warning: true) { store.keepAudio = true }
                    }
                    .frame(maxWidth: 460)
                }
            case .result:
                VStack(spacing: 10) {
                    if item.kind == .video && item.analysed {
                        PlayerBar(item: item)
                    }
                    Text(L.summary(level: store.level, mode: store.mode,
                                   padding: Int((store.padding * 100).rounded()),
                                   audio: item.kind == .video && item.hasAudio != false ? store.keepAudio : nil))
                        .font(.system(size: 12, design: .monospaced))
                    Text(L.alwaysRemoved).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
        .frame(maxHeight: .infinity, alignment: .top)
    }

    // MARK: navigation

    @ViewBuilder
    private func nav(_ item: Item) -> some View {
        HStack(spacing: 10) {
            if store.step == .result {
                resultStatus(item)
            }
            Spacer()
            if store.step != store.steps.first && item.status != .exporting {
                Button(L.back) { move(-1) }
                    .controlSize(.large)
                    .tint(.primary)
                    .keyboardShortcut("[", modifiers: .command)
            }
            if store.step == .result {
                resultAction(item)
            } else {
                Button(L.next) { move(1) }
                    .buttonStyle(PrimaryButtonStyle())
                    .frame(width: 180)
                    .keyboardShortcut(.defaultAction)
            }
        }
        .frame(height: 36)
    }

    /// Left of the buttons: export progress, the saved file, or the error.
    @ViewBuilder
    private func resultStatus(_ item: Item) -> some View {
        switch item.status {
        case .exporting:
            ProgressView(value: Double(item.progress), total: 100)
                .frame(width: 160)
            Text(L.exporting(item.progress)).font(.caption).foregroundStyle(.secondary)
        case .exported:
            if let output = item.output {
                Label(output.lastPathComponent, systemImage: "checkmark.circle.fill")
                    .foregroundStyle(accent)
                    .lineLimit(1)
                    .truncationMode(.middle)
                    .guideTip(.queue, L.tipQueue, arrowEdge: .top, actionTitle: L.openQueue) {
                        openWindow(id: "queue")
                        store.finishOnboarding()
                    }
                Button(L.showInFinder) { NSWorkspace.shared.activateFileViewerSelecting([output]) }
                    .buttonStyle(.borderless)
            }
        case .error:
            Label(item.error, systemImage: "exclamationmark.triangle.fill")
                .foregroundStyle(.red)
                .lineLimit(2)
        default:
            EmptyView()
        }
    }

    @ViewBuilder
    private func resultAction(_ item: Item) -> some View {
        switch item.status {
        case .exporting:
            Button(L.cancel) { store.cancelExport() }
                .controlSize(.large)
                .tint(.primary)
        case .exported:
            Button(store.hasNext ? L.nextFile : L.done) { store.next() }
                .buttonStyle(PrimaryButtonStyle())
                .frame(width: 180)
                .keyboardShortcut(.defaultAction)
        case .error:
            Button(L.retry) { store.retry() }
                .buttonStyle(PrimaryButtonStyle())
                .frame(width: 180)
                .keyboardShortcut(.defaultAction)
        default:
            Button(L.export) {
                if item.status == .noFaces { confirmNoFaces = true } else { chooseOutput(item) }
            }
            .buttonStyle(PrimaryButtonStyle())
            .frame(width: 180)
            .disabled(!item.analysed)
            .keyboardShortcut(.defaultAction)
        }
    }

    private func move(_ delta: Int) {
        let steps = store.steps
        guard let i = steps.firstIndex(of: store.step) else { return }
        store.step = steps[max(0, min(steps.count - 1, i + delta))]
    }

    private func chooseOutput(_ item: Item) {
        store.stopPlaying()
        Privacy.chooseOutput(for: item, in: NSApp.keyWindow) { url in
            if let url { store.export(to: url) }
        }
    }
}

/// The file, lifted off the window: the original while choosing the
/// sensitivity (faces outlined in green), then covered as the export will be.
struct FloatingPicture: View {
    @Environment(Store.self) private var store
    let item: Item

    var body: some View {
        ZStack {
            if let image = store.preview {
                Image(nsImage: image)
                    .resizable()
                    .interpolation(.high)
                    .aspectRatio(contentMode: .fit)
                    .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .overlay(
                        RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(hairline, lineWidth: 1)
                    )
                    .overlay {
                        // Before the analysis, or while the right preview is on its way, the
                        // picture on screen is not what the step shows: dim it.
                        if store.previewStale && !store.playing {
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(Color.black.opacity(0.45))
                                .overlay { ProgressView().controlSize(.small) }
                        }
                    }
                    .overlay {
                        if store.editing, let size = planSize { BoxEditor(planSize: size) }
                    }
                    .shadow(color: .black.opacity(0.55), radius: 28, y: 18)
                    .overlay(alignment: .bottom) { badge.offset(y: 14) }
                    .overlay(alignment: .topTrailing) { correctButton.padding(10) }
            } else {
                ProgressView().controlSize(.small)
            }
        }
        .animation(.easeOut(duration: 0.2), value: store.step)
        .animation(.easeOut(duration: 0.15), value: store.previewStale)
        .animation(.easeOut(duration: 0.2), value: store.tip)
    }

    private var planSize: CGSize? {
        guard let w = (item.plan?["width"] as? NSNumber)?.doubleValue,
              let h = (item.plan?["height"] as? NSNumber)?.doubleValue else { return nil }
        return CGSize(width: w, height: h)
    }

    /// Enters edit mode. Orange when the analysis has uncertain faces to check.
    @ViewBuilder
    private var correctButton: some View {
        if item.analysed && !store.editing && !store.playing && item.status != .exporting {
            Button { store.startEditing() } label: {
                Label(item.status == .review ? L.checkBoxes : L.correct, systemImage: "square.dashed")
                    .font(.caption.weight(.medium))
                    .foregroundStyle(item.status == .review ? Color.orange : Color.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 6)
                    .background(.regularMaterial, in: Capsule())
                    .overlay(Capsule().strokeBorder(hairline, lineWidth: 1))
            }
            .buttonStyle(.plain)
            .keyboardShortcut("e", modifiers: .command)
            .guideTip(.correct, L.tipCorrect, arrowEdge: .bottom)
        }
    }

    @ViewBuilder
    private var badge: some View {
        let label: (text: String, color: Color)? = switch item.status {
        case .waiting, .analyzing: (L.analyzing(item.progress), .secondary)
        case .noFaces: (L.noFaceFound, .red)
        case .review: (L.facesFound(item.faces ?? 0), .orange)
        case .ready, .exported, .exporting: (L.facesFound(item.faces ?? 0), accent)
        case .error, .cancelled: nil
        }
        if let label {
            let (text, color) = label
            HStack(spacing: 7) {
                if item.status == .analyzing || item.status == .waiting {
                    ProgressView().controlSize(.mini)
                } else {
                    Circle().fill(color).frame(width: 6, height: 6)
                }
                Text(text).font(.caption.weight(.medium))
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 6)
            .background(.regularMaterial, in: Capsule())
            .overlay(Capsule().strokeBorder(hairline, lineWidth: 1))
            .help(item.status == .review ? L.toReview : "")
        }
    }
}

/// Video, last step: play/pause (space), a timeline to drag with the covered
/// stretches marked in green, and the time.
struct PlayerBar: View {
    @Environment(Store.self) private var store
    let item: Item

    var body: some View {
        let position = item.previewIndex ?? 0
        HStack(spacing: 12) {
            Button {
                store.playing ? store.stopPlaying() : store.play()
            } label: {
                Image(systemName: store.playing ? "pause.fill" : "play.fill")
                    .font(.system(size: 13))
                    .frame(width: 28, height: 28)
                    .background(Color.white.opacity(0.08), in: Circle())
            }
            .buttonStyle(.plain)
            .keyboardShortcut(.space, modifiers: [])
            .help(store.playing ? L.pause : L.play)
            Timeline(frameCount: item.frameCount, ranges: item.coveredRanges, position: position) {
                store.seek(to: $0)
            }
            Text("\(time(position)) / \(time(item.frameCount))")
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.secondary)
                .fixedSize()
        }
        .frame(maxWidth: 560)
    }

    private func time(_ frame: Int) -> String {
        let seconds = Int(Double(frame) / max(item.fps, 1))
        return String(format: "%02d:%02d", seconds / 60, seconds % 60)
    }
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
                    .frame(width: 12, height: 12)
                    .shadow(color: .black.opacity(0.4), radius: 2)
                    .offset(x: x(position) - 6)
            }
            .frame(height: geo.size.height)
            .contentShape(Rectangle())
            .gesture(DragGesture(minimumDistance: 0).onChanged { v in
                seek(Int((max(0, min(v.location.x, w)) / max(w, 1) * total).rounded()))
            })
        }
        .frame(height: 16)
    }
}

/// Where you are in the guide: done steps green, the current one white. Every
/// step can be clicked; a video's audio step is dimmed when it has no sound.
struct StepBar: View {
    @Environment(Store.self) private var store
    let locked: Bool

    var body: some View {
        let steps = store.steps
        let current = steps.firstIndex(of: store.step) ?? 0
        HStack(spacing: 18) {
            ForEach(Array(steps.enumerated()), id: \.element) { i, step in
                let off = step == .audio && store.current?.hasAudio == false
                Button { store.step = step } label: {
                    HStack(spacing: 6) {
                        Circle()
                            .fill(i < current ? accent : i == current ? Color.white : Color.white.opacity(0.2))
                            .frame(width: 5, height: 5)
                        Text(L.stepTitle(step))
                            .font(.system(size: 10, weight: .medium, design: .monospaced))
                            .tracking(1.5)
                            .strikethrough(off)
                            .foregroundStyle(i == current ? Color.white : Color.white.opacity(i < current ? 0.6 : 0.3))
                    }
                    .padding(.vertical, 4)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .disabled(locked)
            }
        }
    }
}

/// One choice in a step: a card, green when chosen.
struct OptionCard: View {
    let title: String
    let hint: String
    var symbol: String?
    let selected: Bool
    var warning = false
    let action: () -> Void
    @State private var hover = false

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 10) {
                if let symbol {
                    Image(systemName: symbol)
                        .font(.system(size: 15))
                        .foregroundStyle(selected ? accent : .secondary)
                        .frame(width: 20)
                }
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).font(.callout.weight(.medium))
                    Text(hint)
                        .font(.caption)
                        .foregroundStyle(warning && selected ? Color.orange : Color.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }
            .padding(12)
            .frame(maxWidth: .infinity, minHeight: 64, alignment: .topLeading)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(Color.white.opacity(selected ? 0.07 : hover ? 0.05 : 0.025))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .strokeBorder(selected ? accent.opacity(0.85) : hairline, lineWidth: 1)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .onHover { hover = $0 }
        .animation(.easeOut(duration: 0.12), value: selected)
    }
}
