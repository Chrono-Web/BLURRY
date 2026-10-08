import AVFoundation
import BlurryKit
import CoreGraphics
import Observation
import SwiftUI

/// One file. A photo lives in memory only (its bytes, never a path); a video is
/// a copy in the app's temporary folder, deleted when it leaves the queue.
struct Item: Identifiable {
    enum Kind { case image, video }
    enum Status { case waiting, analyzing, ready, review, noFaces, exporting, exported, error }

    let id = UUID()
    let name: String          // shown, and the base of the exported file's name
    let kind: Kind
    let source: Source?       // photo
    let videoURL: URL?        // video
    var status: Status = .waiting
    var progress = 0          // analysis or export, percent
    var edits = Edits()       // corrections by hand
    var faces: Int?
    var thumb: CGImage?
    var error = ""
    var exportedAs: String?   // "Saved" / "Shared"

    // Photo
    var plans: [String: ImagePlan] = [:]   // one per level, from a single analysis
    var plan: ImagePlan?                   // the one for the chosen level, corrected
    var outFormat: OutFormat?

    // Video
    var videoPlans: [String: VideoPlan] = [:]
    var videoPlan: VideoPlan?
    var pts: [CMTime] = []
    var hasAudio: Bool?
    var index: Int?           // the frame on screen (at first, the one with most faces)

    init(name: String, data: Data, ext: String) {
        self.name = name
        kind = .image
        source = Source(id: id, data: data, ext: ext.lowercased())
        videoURL = nil
    }

    init(name: String, video: URL) {
        self.name = name
        kind = .video
        source = nil
        videoURL = video
    }

    var analysed: Bool { [.ready, .review, .noFaces, .exported].contains(status) }
    var busy: Bool { status == .analyzing || status == .exporting }
    var hasPlan: Bool { plan != nil || videoPlan != nil }
    var frameCount: Int { videoPlan?.frameCount ?? 0 }
    var fps: Double { videoPlan?.fps ?? 30 }

    /// `<name>_blurry.<ext>`, as in the Mac app.
    var outputName: String {
        let stem = (name as NSString).deletingPathExtension
        return stem + "_blurry." + (kind == .video ? "mp4" : outFormat?.ext ?? "jpg")
    }

    /// Video: the stretches of time where something is covered, for the timeline.
    var coveredRanges: [ClosedRange<Int>] {
        guard let plan = videoPlan else { return [] }
        var ranges: [ClosedRange<Int>] = []
        for t in plan.tracks where t.enabled { ranges.append(t.first...t.last) }
        for m in plan.manual where m.start <= m.end { ranges.append(m.start...m.end) }
        return ranges.sorted { $0.lowerBound < $1.lowerBound }.reduce(into: []) { out, r in
            if let last = out.last, r.lowerBound <= last.upperBound + 1 {
                out[out.count - 1] = last.lowerBound...max(last.upperBound, r.upperBound)
            } else {
                out.append(r)
            }
        }
    }
}

/// The guide's steps, one at a time. Audio only for videos.
enum Step: Int, CaseIterable {
    case sensitivity, cover, margin, audio, result
}

/// A clean file ready to leave the app, waiting for the sheet that takes it.
struct PendingExport: Identifiable {
    enum Destination { case files, share }
    let id = UUID()
    let item: UUID
    let destination: Destination
    let name: String
    let file: URL   // in the app's temporary folder, removed when the sheet closes
}

@Observable
@MainActor
final class Store {
    static let levelKeys = Levels.shared.levels.map(\.name)

    var items: [Item] = []
    var notice: String?
    var fatal: String?   // the model is missing or altered (R5): nothing works

    var currentID: UUID? { didSet { if currentID != oldValue { enterFile() } } }
    var step: Step = .sensitivity {
        didSet {
            guard step != oldValue else { return }
            if step != .result { usingPrevious = false }
            stopPlaying()
            refreshPreview()
        }
    }
    var preview: CGImage?
    var previewStale = false
    var usingPrevious = false
    var playing = false
    var pendingExport: PendingExport?

    // Correcting boxes by hand.
    var editing = false
    var editBoxes: [EditBox] = []
    var selection: String?
    @ObservationIgnored private var editSnapshot: Edits?

    // Settings kept between sessions (R2 allows exactly these); audio is off at
    // every start, as on the Mac.
    var level: String {
        didSet { if level != oldValue { defaults.set(level, forKey: "level"); applyLevel() } }
    }
    var mode: String { didSet { defaults.set(mode, forKey: "mode"); settingsChanged() } }
    var padding: Double {
        didSet { defaults.set((padding * 100).rounded() / 100, forKey: "padding"); settingsChanged() }
    }
    var keepAudio = false { didSet { settingsChanged() } }

    // First-run guide, as on the Mac: only the "onboarded" flag is kept.
    enum Tip { case steps, correct, queue }
    var onboarded: Bool { didSet { defaults.set(onboarded, forKey: "onboarded") } }
    var showWelcome: Bool
    var guiding: Bool
    var tipStage = 0

    var tip: Tip? {
        guard guiding, !showWelcome, let item = current, !editing, pendingExport == nil else { return nil }
        if item.status == .exported { return .queue }
        switch tipStage {
        case 0: return .steps
        case 1: return item.analysed ? .correct : nil
        default: return nil
        }
    }

    func nextTip() { tipStage += 1 }

    func beginGuidedSession() {
        onboarded = true
        showWelcome = false
    }

    func finishOnboarding() {
        showWelcome = false
        guiding = false
        onboarded = true
        tipStage = 0
    }

    func restartOnboarding() {
        onboarded = false
        showWelcome = true
        guiding = true
        tipStage = 0
        defaults.removeObject(forKey: "onboarded")
    }

    /// False while the app is in the background: no work runs then (iOS does
    /// not let an app use the GPU from the background, and a long video would
    /// be cut short anyway).
    var active = true { didSet { if active && !oldValue { pump() } } }

    @ObservationIgnored let engine = Engine()
    @ObservationIgnored private let defaults: UserDefaults
    @ObservationIgnored private var skipped: Set<UUID> = []
    @ObservationIgnored private var confirmedOnce = false
    @ObservationIgnored private var analysis: (id: UUID, task: Task<Void, Never>)?
    @ObservationIgnored private var exporting: (id: UUID, task: Task<Void, Never>, cancel: CancelFlag)?
    @ObservationIgnored private var playTask: Task<Void, Never>?
    @ObservationIgnored private var previewInFlight = false
    @ObservationIgnored private var previewAgain = false
    @ObservationIgnored private var photoCount = 0
    @ObservationIgnored private var videoCount = 0

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        let l = defaults.string(forKey: "level") ?? ""
        level = Self.levelKeys.contains(l) ? l : Levels.shared.defaultLevel
        let m = defaults.string(forKey: "mode") ?? ""
        mode = CoverMode(rawValue: m) != nil ? m : Levels.shared.defaultMode
        let p = (defaults.object(forKey: "padding") as? NSNumber)?.doubleValue ?? Levels.shared.defaultPadding
        padding = (0...1).contains(p) ? p : Levels.shared.defaultPadding
        let seen = defaults.bool(forKey: "onboarded")
        onboarded = seen
        showWelcome = !seen
        guiding = !seen
        Task { [engine] in
            do { try await engine.prepare() } catch { await MainActor.run { self.fatal = "\(error)" } }
        }
    }

    var current: Item? { currentID.flatMap { id in items.first { $0.id == id } } }

    var settings: Settings {
        Settings(level: level, mode: CoverMode(rawValue: mode) ?? .solid, padding: padding, keepAudio: keepAudio)
    }

    /// The steps, fixed from the start: audio for every video (it says so when
    /// the video has none), never for photos.
    var steps: [Step] {
        current?.kind == .video ? Step.allCases : Step.allCases.filter { $0 != .audio }
    }

    private var todo: [Item] {
        items.filter { $0.status != .exported && $0.status != .error && !skipped.contains($0.id) }
    }

    var position: (index: Int, total: Int) {
        let open = items.filter { ($0.status != .exported && !skipped.contains($0.id)) || $0.id == currentID }
        let i = open.firstIndex { $0.id == currentID } ?? 0
        return (i + 1, open.count)
    }

    var hasNext: Bool { todo.contains { $0.id != currentID } }

    // MARK: adding, opening, removing

    /// Photos read into memory by a picker or "Open in". `name` is nil for
    /// photos from the library, which get "Photo 1", "Photo 2"...
    func add(_ files: [(name: String?, ext: String, data: Data)]) {
        var first: UUID?
        var skippedCount = 0
        for f in files {
            guard ImageIn.extensions.contains(f.ext.lowercased()) else {
                skippedCount += 1
                continue
            }
            let name: String
            if let n = f.name {
                name = n
            } else {
                photoCount += 1
                name = L.photoName(photoCount) + "." + f.ext.lowercased()
            }
            let item = Item(name: name, data: f.data, ext: f.ext)
            items.append(item)
            first = first ?? item.id
        }
        notice = skippedCount > 0 ? L.skipped(skippedCount) : nil
        if currentID == nil, let first { currentID = first }
        pump()
    }

    /// Videos already copied into the app's temporary folder (Videos.copy).
    func addVideos(_ files: [(name: String?, url: URL)]) {
        var first: UUID?
        for f in files {
            let name: String
            if let n = f.name {
                name = n
            } else {
                videoCount += 1
                name = L.videoName(videoCount) + "." + f.url.pathExtension.lowercased()
            }
            let item = Item(name: name, video: f.url)
            items.append(item)
            first = first ?? item.id
        }
        if currentID == nil, let first { currentID = first }
        pump()
    }

    func remove(_ ids: Set<UUID>) {
        if let a = analysis, ids.contains(a.id) { a.task.cancel() }
        if let e = exporting, ids.contains(e.id) { e.cancel.set(); e.task.cancel() }
        if let id = currentID, ids.contains(id) { currentID = nil }
        for item in items where ids.contains(item.id) {
            if let url = item.videoURL { Videos.discard(url) }
        }
        items.removeAll { ids.contains($0.id) }
        for id in ids { Task { await engine.forget(id) } }
    }

    func clear() { remove(Set(items.filter { !$0.busy }.map(\.id))) }

    func next() { currentID = todo.first { $0.id != currentID }?.id }

    func skip() {
        if let id = currentID { skipped.insert(id) }
        next()
    }

    func open(_ id: UUID) {
        skipped.remove(id)
        currentID = id
    }

    func home() { currentID = nil }

    private func enterFile() {
        stopPlaying()
        endEditing(keep: true)
        let fresh = current.map { $0.status != .exported } ?? false
        usingPrevious = confirmedOnce && fresh
        step = usingPrevious ? .result : .sensitivity
        preview = current?.thumb
        refreshPreview()
        pump()
    }

    private func index(of id: UUID) -> Int? { items.firstIndex { $0.id == id } }

    // MARK: analysis, one file at a time

    private func pump() {
        guard active, analysis == nil, fatal == nil else { return }
        let waiting = items.filter { $0.status == .waiting }
        guard let next = waiting.first(where: { $0.id == currentID }) ?? waiting.first,
              let i = index(of: next.id) else { return }
        items[i].status = .analyzing
        items[i].progress = 0
        let id = next.id
        let task: Task<Void, Never>
        if let url = next.videoURL {
            task = Task { await analyzeVideo(id, url) }
        } else if let source = next.source {
            task = Task { await analyzePhoto(id, source) }
        } else {
            return
        }
        analysis = (id, task)
    }

    private func analyzePhoto(_ id: UUID, _ source: Source) async {
        let result: Result<Analysis, Error>
        do { result = .success(try await engine.analyze(source)) } catch { result = .failure(error) }
        finishAnalysis(id) { i in
            let a = try result.get()
            items[i].plans = a.plans
            items[i].outFormat = a.outFormat
            items[i].thumb = a.thumb
        }
    }

    private func analyzeVideo(_ id: UUID, _ url: URL) async {
        let result: Result<VideoAnalysis, Error>
        do {
            result = .success(try await engine.analyzeVideo(url) { pct in
                Task { @MainActor in
                    if let i = self.index(of: id), self.items[i].status == .analyzing { self.items[i].progress = pct }
                }
            })
        } catch {
            result = .failure(error)
        }
        finishAnalysis(id) { i in
            let a = try result.get()
            items[i].videoPlans = a.plans
            items[i].pts = a.pts
            items[i].hasAudio = a.info.hasAudio
            items[i].index = a.bestFrame
            items[i].thumb = a.thumb
        }
    }

    /// After an analysis: store it, or the error, or (interrupted by the
    /// background or a removal) leave the file waiting.
    private func finishAnalysis(_ id: UUID, _ store: (Int) throws -> Void) {
        analysis = nil
        defer { pump() }
        guard let i = index(of: id) else { return }
        do {
            try store(i)
            rebuild(i)
            if id == currentID {
                preview = items[i].thumb
                refreshPreview()
            }
        } catch is CancellationError {
            items[i].status = .waiting
        } catch {
            if active { fail(i, error) } else { items[i].status = .waiting }
        }
    }

    private func fail(_ i: Int, _ error: Error) {
        items[i].status = .error
        // BlurryKit's errors carry the engine's own messages; anything else, the system's.
        switch error {
        case let e as InputError: items[i].error = e.description
        case let e as ModelIntegrityError: items[i].error = e.description
        case let e as ImageOut.EncodeError: items[i].error = e.description
        case let e as VideoOut.RenderError: items[i].error = e.description
        default: items[i].error = error.localizedDescription
        }
    }

    func retry() {
        guard let id = currentID, let i = index(of: id) else { return }
        items[i].error = ""
        if items[i].plans.isEmpty && items[i].videoPlans.isEmpty { items[i].status = .waiting } else { settle(i) }
        refreshPreview()
        pump()
    }

    /// A new level is instant: every analysed file already has the plan for it.
    private func applyLevel() {
        for i in items.indices where (!items[i].plans.isEmpty || !items[i].videoPlans.isEmpty)
            && items[i].status != .exporting {
            if items[i].status == .exported && items[i].id != currentID { continue }
            rebuild(i)
        }
        refreshPreview()
    }

    private func rebuild(_ i: Int) {
        if items[i].kind == .video {
            items[i].videoPlan = items[i].edits.apply(toVideo: items[i].videoPlans[level])
        } else {
            items[i].plan = items[i].edits.apply(to: items[i].plans[level])
        }
        settle(i)
    }

    private func settingsChanged() {
        if let id = currentID, let i = index(of: id), items[i].status == .exported { settle(i) }
        refreshPreview()
    }

    /// The status after analysis, as Store.settle on the Mac.
    private func settle(_ i: Int) {
        let faces: Int, flags: [Flag], expected: Bool
        if let v = items[i].videoPlan {
            faces = v.tracks.filter(\.enabled).count + v.manual.count
            flags = v.flags
            expected = v.facesExpected
        } else {
            faces = items[i].plan?.boxes.count ?? 0
            flags = items[i].plan?.flags ?? []
            expected = items[i].plan?.facesExpected ?? true
        }
        items[i].faces = faces
        if expected, faces == 0 {
            items[i].status = .noFaces
        } else if flags.contains(where: { $0.kind != .noFaces }) && items[i].edits.isEmpty {
            items[i].status = .review
        } else {
            items[i].status = .ready
        }
    }

    // MARK: the picture

    /// Coalesced: while one preview is being made, only the latest change follows.
    func refreshPreview() {
        guard let item = current, item.hasPlan else {
            preview = current?.thumb
            previewStale = step != .sensitivity && current.map { !$0.analysed && $0.status != .error } ?? false
            return
        }
        if playing { return }
        previewStale = true
        if previewInFlight {
            previewAgain = true
            return
        }
        previewInFlight = true
        let id = item.id, edit = editing, settings = settings
        let outline = step == .sensitivity && !edit
        Task {
            var image: CGImage?
            if let url = item.videoURL, let plan = item.videoPlan {
                image = try? await engine.previewVideo(url, plan: plan, index: item.index ?? 0, pts: item.pts,
                                                       settings: settings, outline: outline, plain: edit)
            } else if let source = item.source, let plan = item.plan {
                image = try? await engine.preview(source, plan: plan, settings: settings, outline: outline, plain: edit)
            }
            previewInFlight = false
            if id == currentID, !playing, let image { preview = image }
            if previewAgain {
                previewAgain = false
                refreshPreview()
            } else {
                previewStale = false
            }
        }
    }

    /// Video: play the covered result from the playhead (from the start if it
    /// is at the end). Stopping leaves the picture there.
    func play() {
        guard let item = current, let url = item.videoURL, let plan = item.videoPlan, !playing else { return }
        var start = item.index ?? 0
        if start >= plan.frameCount - 1 { start = 0 }
        playing = true
        let id = item.id, settings = settings, pts = item.pts
        playTask = Task {
            try? await engine.play(url, plan: plan, from: start, pts: pts, settings: settings) { index, image in
                Task { @MainActor in
                    guard self.playing, let i = self.index(of: id) else { return }
                    self.items[i].index = index
                    self.preview = image
                    self.previewStale = false
                }
            }
            playing = false
            refreshPreview()
        }
    }

    func stopPlaying() {
        guard playing else { return }
        playing = false
        playTask?.cancel()
        playTask = nil
    }

    /// Video: move the playhead and show that frame.
    func seek(to frame: Int) {
        guard let id = currentID, let i = index(of: id) else { return }
        stopPlaying()
        items[i].index = max(0, min(frame, max(0, items[i].frameCount - 1)))
        if editing { editBoxes = boxes(of: items[i]) }
        refreshPreview()
    }

    // MARK: export

    /// Render the clean file into the app's temporary folder, then hand it to
    /// Files or to the share sheet.
    func export(to destination: PendingExport.Destination) {
        guard let id = currentID, let i = index(of: id), items[i].hasPlan, !items[i].busy else { return }
        stopPlaying()
        items[i].status = .exporting
        items[i].progress = 0
        let item = items[i], settings = settings, name = item.outputName
        let flag = CancelFlag()
        let task = Task {
            do {
                let file = try Videos.outputFile(name)
                if let url = item.videoURL, let plan = item.videoPlan {
                    try await engine.renderVideo(url, to: file, plan: plan, settings: settings, progress: { pct in
                        Task { @MainActor in
                            if let i = self.index(of: id), self.items[i].status == .exporting { self.items[i].progress = pct }
                        }
                    }, cancelled: { flag.isSet })
                } else if let source = item.source, let plan = item.plan {
                    let data = try await engine.render(source, plan: plan, settings: settings)
                    try data.write(to: file, options: .completeFileProtection)
                }
                exporting = nil
                guard index(of: id) != nil else { return Videos.discard(file) }
                pendingExport = PendingExport(item: id, destination: destination, name: name, file: file)
            } catch {
                exporting = nil
                guard let i = index(of: id) else { return }
                if error is CancellationError || flag.isSet {
                    settle(i)
                    notice = L.interrupted
                } else {
                    fail(i, error)
                }
            }
        }
        exporting = (id, task, flag)
    }

    /// The sheet closed: saved or shared, or cancelled (back to ready).
    func finishExport(_ done: Bool) {
        guard let pending = pendingExport else { return }
        pendingExport = nil
        Videos.discard(pending.file)
        guard let i = index(of: pending.item) else { return }
        if done {
            items[i].status = .exported
            items[i].exportedAs = pending.destination == .files ? L.saved : L.shared
            confirmedOnce = true
        } else {
            settle(i)
        }
    }

    // MARK: correcting boxes by hand

    func startEditing() {
        guard let item = current, item.hasPlan, !item.busy else { return }
        stopPlaying()
        editSnapshot = item.edits
        selection = nil
        editing = true
        editBoxes = boxes(of: item)
        refreshPreview()
    }

    func endEditing(keep: Bool) {
        guard editing else { return }
        if !keep, let snapshot = editSnapshot, let id = currentID, let i = index(of: id) {
            items[i].edits = snapshot
            rebuild(i)
        }
        editSnapshot = nil
        editing = false
        selection = nil
        editBoxes = []
        refreshPreview()
    }

    var selectedBox: EditBox? { editBoxes.first { $0.id == selection } }

    /// What the editor draws (worker.edit_boxes): every box, with who owns it.
    /// For a video, the boxes at the frame on screen, switched-off tracks included.
    private func boxes(of item: Item) -> [EditBox] {
        func rect(_ b: Box) -> CGRect { CGRect(x: b.x, y: b.y, width: b.w, height: b.h) }
        if let plan = item.videoPlan {
            let frame = item.index ?? 0
            let flagged = Set(plan.flags.compactMap(\.track))
            var out: [EditBox] = []
            for t in plan.tracks {
                if let b = Tracking.coverage(t, extend: plan.extendFrames, frameCount: plan.frameCount)[frame] {
                    out.append(EditBox(id: "t\(t.id)", owner: .track(t.id), rect: rect(b), enabled: t.enabled,
                                       uncertain: flagged.contains(t.id)))
                }
            }
            for (j, m) in item.edits.manual.enumerated() where m.start <= frame && frame <= m.end {
                out.append(EditBox(id: "m\(j)", owner: .manual(j), rect: rect(m.box), uncertain: false,
                                   start: m.start, end: m.end))
            }
            return out
        }
        guard let plan = item.plan else { return [] }
        let uncertain = Set(plan.flags.compactMap(\.box))
        var drawn = 0
        return plan.boxes.enumerated().map { i, b in
            let owner: EditBox.Owner
            if b.source == .manual {
                owner = .drawn(drawn)
                drawn += 1
            } else {
                owner = .found(key: Edits.key(b))
            }
            return EditBox(id: "b\(i)", owner: owner, rect: rect(b), uncertain: uncertain.contains(i))
        }
    }

    private func edit(_ change: (inout Item) -> Void) {
        guard let id = currentID, let i = index(of: id) else { return }
        change(&items[i])
        rebuild(i)
        editBoxes = boxes(of: items[i])
        refreshPreview()
    }

    /// A box drawn on the picture: on a photo it covers that area; on a video
    /// it covers it, still, for the whole video (the span can then be narrowed).
    func addBox(_ rect: CGRect) {
        guard let item = current else { return }
        if item.kind == .video {
            let j = item.edits.manual.count
            edit { $0.edits.manual.append(ManualRange(start: 0, end: max(0, $0.frameCount - 1), box: Edits.box(rect))) }
            selection = "m\(j)"
        } else {
            edit { $0.edits.added.append(Edits.box(rect)) }
            selection = "b\((item.plan?.boxes.count ?? 0))"
        }
    }

    /// A box moved or resized. A found photo box becomes one drawn by hand.
    func moveBox(_ box: EditBox, to rect: CGRect) {
        switch box.owner {
        case let .found(key):
            edit {
                $0.edits.removed.insert(key)
                $0.edits.added.append(Edits.box(rect))
            }
            selection = "b\(editBoxes.count - 1)"   // the drawn one is last
        case let .drawn(j):
            edit { if $0.edits.added.indices.contains(j) { $0.edits.added[j] = Edits.box(rect) } }
        case let .manual(j):
            edit { if $0.edits.manual.indices.contains(j) { $0.edits.manual[j].box = Edits.box(rect) } }
        case .track:
            break
        }
    }

    /// Delete: a photo box or a manual video box goes away; a track is switched
    /// off (or on again).
    func removeBox(_ box: EditBox) {
        switch box.owner {
        case let .found(key):
            selection = nil
            edit { $0.edits.removed.insert(key) }
        case let .drawn(j):
            selection = nil
            edit { if $0.edits.added.indices.contains(j) { $0.edits.added.remove(at: j) } }
        case let .manual(j):
            selection = nil
            edit { if $0.edits.manual.indices.contains(j) { $0.edits.manual.remove(at: j) } }
        case let .track(id):
            toggleTrack(id)
        }
    }

    func toggleTrack(_ id: Int) {
        guard let base = current?.videoPlans[level], let track = base.tracks.first(where: { $0.id == id }) else { return }
        let keys = track.detections.map { Edits.detectionKey($0.key, $0.value) }
        edit { item in
            if keys.contains(where: item.edits.disabled.contains) {
                item.edits.disabled.subtract(keys)
            } else {
                item.edits.disabled.formUnion(keys)
            }
        }
    }

    /// Video: the selected manual box starts (or ends) at the playhead.
    func setRange(_ j: Int, start: Bool) {
        guard let frame = current?.index else { return }
        edit { item in
            guard item.edits.manual.indices.contains(j) else { return }
            var lo = item.edits.manual[j].start, hi = item.edits.manual[j].end
            if start { lo = frame } else { hi = frame }
            item.edits.manual[j].start = min(lo, hi)
            item.edits.manual[j].end = max(lo, hi)
        }
    }

    // MARK: life cycle

    /// The app left the screen: stop the work (a long video would be cut short
    /// anyway), drop decoded pictures, and remove the copies nothing needs.
    func didEnterBackground() {
        active = false
        stopPlaying()
        if let a = analysis {
            a.task.cancel()
            notice = L.interrupted
        }
        if let e = exporting {
            e.cancel.set()
            e.task.cancel()
        }
        Task { await engine.forget() }
        Privacy.clearCopies(keeping: Set(items.compactMap(\.videoURL)).union(pendingExport.map { [$0.file] } ?? []))
        Privacy.scrub(defaults)
    }
}

/// A flag the export checks between frames.
final class CancelFlag: @unchecked Sendable {
    private let lock = NSLock()
    private var value = false
    var isSet: Bool { lock.withLock { value } }
    func set() { lock.withLock { value = true } }
}
