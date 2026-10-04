import AppKit
import Observation
import UniformTypeIdentifiers

/// One file. Lives in memory only.
struct Item: Identifiable {
    enum Kind { case image, video }
    enum Status { case waiting, analyzing, ready, review, noFaces, exporting, exported, error, cancelled }

    let id = UUID()
    let url: URL
    let kind: Kind
    var status: Status = .waiting
    var progress = 0
    var plans: [String: [String: Any]] = [:]  // one per level, from a single analysis
    var plan: [String: Any]?                  // the one for the chosen level, corrected
    var edits = Edits()                       // corrections by hand
    var pts: [Any]?          // video frame timestamps from the analysis, for fast seeking
    var outExt: String       // what the export will be: jpg, png… or mp4
    var hasAudio: Bool?      // video: read before the analysis; nil until known
    var faces: Int?
    var thumb: NSImage?      // the original: the image, or a video frame
    var previewIndex: Int?   // video: the frame on screen (at first, the one with most faces)
    var error = ""
    var output: URL?

    init(url: URL, kind: Kind) {
        self.url = url
        self.kind = kind
        outExt = kind == .video ? "mp4" : url.pathExtension.lowercased()
    }

    var name: String { url.lastPathComponent }
    var analysed: Bool { [.ready, .review, .noFaces, .exported].contains(status) }
    var busy: Bool { status == .analyzing || status == .exporting }

    var frameCount: Int { plan?["frame_count"] as? Int ?? 0 }
    var fps: Double { (plan?["fps"] as? NSNumber)?.doubleValue ?? 30 }

    /// Video: the stretches of time where something is covered, for the timeline.
    var coveredRanges: [ClosedRange<Int>] {
        guard let plan else { return [] }
        var ranges: [ClosedRange<Int>] = []
        for track in plan["tracks"] as? [[String: Any]] ?? [] where track["enabled"] as? Bool ?? true {
            let frames = (track["detections"] as? [[Any]] ?? []).compactMap { $0.first as? Int }
            if let lo = frames.min(), let hi = frames.max() { ranges.append(lo...hi) }
        }
        for manual in plan["manual"] as? [[String: Any]] ?? [] {
            if let lo = manual["start"] as? Int, let hi = manual["end"] as? Int, lo <= hi { ranges.append(lo...hi) }
        }
        return ranges.sorted { $0.lowerBound < $1.lowerBound }.reduce(into: []) { out, r in
            if let last = out.last, r.lowerBound <= last.upperBound + 1 {
                out[out.count - 1] = last.lowerBound...max(last.upperBound, r.upperBound)
            } else {
                out.append(r)
            }
        }
    }
}

// Same lists as image_io.IMAGE_EXTENSIONS and video_io.VIDEO_EXTENSIONS.
let imageExtensions: Set<String> = ["jpg", "jpeg", "png", "webp", "heic", "heif"]
let videoExtensions: Set<String> = ["mp4", "mov", "m4v", "mkv", "webm", "avi"]

// Same values as levels.py (LEVELS, DEFAULT_*, MODES).
let levelKeys = ["base", "medium", "high"]
let modeKeys = ["solid", "pixel"]

/// The guide's steps, one at a time.
enum Step: Int, CaseIterable {
    case sensitivity, cover, margin, audio, result
}

@Observable
@MainActor
final class Store {
    var items: [Item] = []
    var notice: String?

    // The guide: which file, which step, what the floating picture shows.
    var currentID: UUID? { didSet { if currentID != oldValue { enterFile() } } }
    var step: Step = .sensitivity {
        didSet {
            guard step != oldValue else { return }
            if step != .result { usingPrevious = false }
            stopPlaying()
            refreshPreview()
        }
    }
    var preview: NSImage?
    /// The picture on screen is not yet the one for the current step and
    /// settings (a preview is on its way): the view dims it.
    var previewStale = false
    var playing = false
    /// The file opened straight on the result, with the previous file's settings.
    var usingPrevious = false

    // Correcting boxes by hand: the picture uncovered, the boxes on it, the one selected.
    var editing = false
    var editBoxes: [EditBox] = []
    var selection: String?
    @ObservationIgnored private var editSnapshot: Edits?

    @ObservationIgnored let jobs = Worker()   // analysis and export
    @ObservationIgnored let view = Worker()   // previews and playback
    @ObservationIgnored private let defaults = UserDefaults.standard

    // Settings. Level, mode and padding are kept between sessions (R2 allows
    // exactly these); audio is off at every start.
    var level: String {
        didSet { if level != oldValue { defaults.set(level, forKey: "level"); applyLevel() } }
    }
    var mode: String { didSet { defaults.set(mode, forKey: "mode"); settingsChanged() } }
    var padding: Double {
        didSet { defaults.set((padding * 100).rounded() / 100, forKey: "padding"); settingsChanged() }
    }
    var keepAudio = false { didSet { settingsChanged() } }

    @ObservationIgnored private var skipped: Set<UUID> = []
    @ObservationIgnored private var confirmedOnce = false   // a file has been exported this session
    @ObservationIgnored private var playToken = 0
    @ObservationIgnored private var previewInFlight = false
    @ObservationIgnored private var previewAgain = false
    @ObservationIgnored private var exportQueue: [(UUID, URL)] = []

    init() {
        let l = defaults.string(forKey: "level") ?? ""
        level = levelKeys.contains(l) ? l : "high"
        let m = defaults.string(forKey: "mode") ?? ""
        mode = modeKeys.contains(m) ? m : "solid"
        let p = (defaults.object(forKey: "padding") as? NSNumber)?.doubleValue
            ?? Double(defaults.string(forKey: "padding") ?? "") ?? 0.25
        padding = (0...1).contains(p) ? p : 0.25
        jobs.onCrash = { [weak self] in self?.notice = L.workerCrashed }
        view.onCrash = { [weak self] in self?.previewInFlight = false; self?.playing = false }
    }

    var engineMissing: Bool { jobs.unavailable }

    var current: Item? { currentID.flatMap { id in items.first { $0.id == id } } }

    /// The steps, fixed from the start: audio is there for every video (and
    /// says so when the video has none), never for photos.
    var steps: [Step] {
        current?.kind == .image ? Step.allCases.filter { $0 != .audio } : Step.allCases
    }

    /// Files still to go through the guide, in order.
    private var todo: [Item] {
        items.filter { $0.status != .exported && $0.status != .error && !skipped.contains($0.id) }
    }

    var position: (index: Int, total: Int) {
        let open = items.filter { ($0.status != .exported && !skipped.contains($0.id)) || $0.id == currentID }
        let i = open.firstIndex { $0.id == currentID } ?? 0
        return (i + 1, open.count)
    }

    var hasNext: Bool { todo.contains { $0.id != currentID } }

    private var settings: [String: Any] {
        ["level": level, "mode": mode, "padding": padding, "keep_audio": keepAudio, "faces": true]
    }

    // MARK: adding, opening, removing

    func add(_ urls: [URL]) {
        var expanded: [URL] = []
        for url in urls {
            var isDir: ObjCBool = false
            guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDir) else { continue }
            if isDir.boolValue {
                let children = (try? FileManager.default.contentsOfDirectory(
                    at: url, includingPropertiesForKeys: nil, options: [.skipsHiddenFiles])) ?? []
                expanded += children.sorted { $0.lastPathComponent < $1.lastPathComponent }
            } else {
                expanded.append(url)
            }
        }
        var known = Set(items.map { $0.url.standardizedFileURL })
        var skipped = 0
        var first: UUID?
        for url in expanded {
            let std = url.standardizedFileURL
            if known.contains(std) || url.lastPathComponent.hasPrefix(".") { continue }
            let ext = url.pathExtension.lowercased()
            let kind: Item.Kind
            if imageExtensions.contains(ext) {
                kind = .image
            } else if videoExtensions.contains(ext) {
                kind = .video
            } else {
                skipped += 1
                continue
            }
            let item = Item(url: url, kind: kind)
            items.append(item)
            known.insert(std)
            first = first ?? item.id
            if kind == .video { firstFrame(item.id) }
        }
        notice = skipped > 0 ? L.skipped(skipped) : nil
        if currentID == nil, let first { currentID = first }
        pump()
    }

    func remove(_ ids: Set<UUID>) {
        if items.contains(where: { ids.contains($0.id) && $0.busy }) { jobs.cancel() }
        exportQueue.removeAll { ids.contains($0.0) }
        if let id = currentID, ids.contains(id) { currentID = nil }
        items.removeAll { ids.contains($0.id) }
    }

    /// Next file in the guide, or back to the drop window.
    func next() {
        currentID = todo.first { $0.id != currentID }?.id
    }

    /// Leave this file for now: it stays in the queue, not exported.
    func skip() {
        if let id = currentID { skipped.insert(id) }
        next()
    }

    func open(_ id: UUID) {
        skipped.remove(id)
        currentID = id
    }

    private func enterFile() {
        stopPlaying()
        // After a first export, the next files open on the result with the same settings.
        let fresh = current.map { $0.status != .exported } ?? false
        usingPrevious = confirmedOnce && fresh
        step = usingPrevious ? .result : .sensitivity
        preview = current?.thumb
        refreshPreview()
        pump()
    }

    private func index(of id: UUID) -> Int? { items.firstIndex { $0.id == id } }

    // MARK: analysis and export (jobs worker)

    private func pump() {
        guard !jobs.busy else { return }
        if !exportQueue.isEmpty {
            let (id, url) = exportQueue.removeFirst()
            return render(id, to: url)
        }
        // The file on screen first, then the others in order.
        let waiting = items.filter { $0.status == .waiting }
        if let next = waiting.first(where: { $0.id == currentID }) ?? waiting.first {
            analyze(next.id)
        }
    }

    /// A new level is instant: every analysed file already has the plan for it.
    /// Files already exported keep their status, except the one on screen.
    private func applyLevel() {
        for i in items.indices where !items[i].plans.isEmpty && items[i].status != .exporting {
            if items[i].status == .exported && items[i].id != currentID { continue }
            rebuild(i)
        }
        refreshPreview()
    }

    /// The plan for the chosen level with the corrections applied, and its status.
    private func rebuild(_ i: Int) {
        items[i].plan = items[i].edits.apply(to: items[i].plans[level])
        settle(i)
    }

    /// Mode, margin or audio changed: refresh, and the file on screen, if it was
    /// already exported, can be exported again with the new settings.
    private func settingsChanged() {
        if let id = currentID, let i = index(of: id), items[i].status == .exported {
            settle(i)
        }
        refreshPreview()
    }

    /// After an error: analyse again, or allow the export again.
    func retry() {
        guard let id = currentID, let i = index(of: id) else { return }
        items[i].error = ""
        if items[i].plans.isEmpty {
            items[i].status = .waiting
        } else {
            settle(i)
        }
        refreshPreview()
        pump()
    }

    private func analyze(_ id: UUID) {
        guard let i = index(of: id) else { return }
        items[i].status = .analyzing
        items[i].progress = 0
        let payload: [String: Any] = ["path": items[i].url.path, "settings": settings, "max_side": 1600,
                                      "all_levels": true]
        jobs.request("analyze", payload) { [weak self] event in
            guard let self else { return }
            guard let i = self.index(of: id) else { return self.pump() }
            switch event {
            case let .progress(done, total):
                self.items[i].progress = total > 0 ? min(99, done * 100 / total) : 0
                return
            case let .result(msg):
                self.items[i].plans = msg["plans"] as? [String: [String: Any]] ?? [:]
                if self.items[i].plans.isEmpty, let plan = msg["plan"] as? [String: Any] {
                    self.items[i].plans = [self.level: plan]
                }
                self.items[i].plan = self.items[i].edits.apply(to: self.items[i].plans[self.level])
                self.items[i].pts = msg["pts"] as? [Any]
                if let audio = msg["has_audio"] as? Bool { self.items[i].hasAudio = audio }
                if let ext = msg["out_ext"] as? String { self.items[i].outExt = ext }
                if let b64 = msg["preview"] as? String, let data = Data(base64Encoded: b64) {
                    self.items[i].thumb = NSImage(data: data)
                }
                self.settle(i)
                if id == self.currentID { self.refreshPreview() }
            case let .error(message):
                self.fail(i, message)
            case .cancelled:
                self.items[i].status = .cancelled
            case .frame:
                return
            }
            self.pump()
        }
    }

    /// Export the current file to a path chosen in the save panel.
    func export(to url: URL) {
        guard let id = currentID else { return }
        exportQueue.append((id, url))
        pump()
    }

    func cancelExport() {
        exportQueue.removeAll()
        if current?.status == .exporting { jobs.cancel() }
    }

    private func render(_ id: UUID, to url: URL) {
        guard let i = index(of: id), let plan = items[i].plan else { return pump() }
        items[i].status = .exporting
        items[i].progress = 0
        let payload: [String: Any] = ["path": items[i].url.path, "plan": plan, "settings": settings,
                                      "output": url.path]
        jobs.request("render", payload) { [weak self] event in
            guard let self else { return }
            guard let i = self.index(of: id) else { return self.pump() }
            switch event {
            case let .progress(done, total):
                self.items[i].progress = total > 0 ? min(99, done * 100 / total) : 0
                return
            case let .result(msg):
                self.items[i].status = .exported
                self.items[i].output = (msg["output"] as? String).map { URL(fileURLWithPath: $0) }
                self.confirmedOnce = true
            case let .error(message):
                self.fail(i, message)
            case .cancelled, .frame:
                self.settle(i)
            }
            self.pump()
        }
    }

    private func fail(_ i: Int, _ message: String) {
        items[i].status = .error
        items[i].error = message == "worker" ? L.workerCrashed : message
    }

    /// Port of gui/model.py Item.settle: the status after analysis.
    private func settle(_ i: Int) {
        let plan = items[i].plan ?? [:]
        let faces: Int
        if plan["type"] as? String == "image" {
            faces = (plan["boxes"] as? [Any])?.count ?? 0
        } else {
            let tracks = plan["tracks"] as? [[String: Any]] ?? []
            faces = tracks.filter { $0["enabled"] as? Bool ?? true }.count
                + ((plan["manual"] as? [Any])?.count ?? 0)
        }
        items[i].faces = faces
        let flags = (plan["flags"] as? [[String: Any]] ?? []).filter { $0["kind"] as? String != "no_faces" }
        if plan["faces_expected"] as? Bool ?? true, faces == 0 {
            items[i].status = .noFaces
        } else if !flags.isEmpty && items[i].edits.isEmpty {
            items[i].status = .review
        } else {
            items[i].status = .ready
        }
    }

    // MARK: the floating picture (view worker)

    private func firstFrame(_ id: UUID) {
        guard let item = items.first(where: { $0.id == id }) else { return }
        let payload: [String: Any] = ["path": item.url.path, "index": 0, "max_side": 1600, "probe": true]
        view.request("frame", payload) { [weak self] event in
            guard let self, case let .result(r) = event, let i = self.index(of: id),
                  let b64 = r["preview"] as? String, let data = Data(base64Encoded: b64) else { return }
            if let audio = r["has_audio"] as? Bool { self.items[i].hasAudio = audio }
            self.items[i].thumb = NSImage(data: data)
            if id == self.currentID, self.items[i].plan == nil { self.preview = self.items[i].thumb }
        }
    }

    /// The picture for the current step: detected faces outlined while choosing
    /// the sensitivity, then covered exactly as the export will be. Requests are
    /// coalesced: while one is running, only the latest change is sent next.
    func refreshPreview() {
        guard let item = current, let plan = item.plan else {
            preview = current?.thumb
            // Before the analysis the original is right for the sensitivity step only.
            previewStale = step != .sensitivity && current.map { !$0.analysed && $0.status != .error } ?? false
            return
        }
        previewStale = true
        if previewInFlight {
            previewAgain = true
            return
        }
        previewInFlight = true
        let id = item.id
        let edit = editing
        var payload: [String: Any] = ["path": item.url.path, "plan": plan, "settings": settings,
                                      "max_side": 1600, "outline": step == .sensitivity && !edit, "edit": edit]
        if item.kind == .video {
            payload["index"] = item.previewIndex ?? NSNull()
            payload["pts"] = item.pts ?? NSNull()
        }
        view.request("preview", payload) { [weak self] event in
            guard let self else { return }
            self.previewInFlight = false
            if case let .result(r) = event, let i = self.index(of: id), id == self.currentID, !self.playing {
                if self.items[i].kind == .video, self.items[i].previewIndex == nil {
                    self.items[i].previewIndex = r["index"] as? Int
                }
                if let b64 = r["preview"] as? String, let data = Data(base64Encoded: b64) {
                    self.preview = NSImage(data: data)
                }
                if edit && self.editing { self.editBoxes = self.parseBoxes(r["boxes"] as? [[String: Any]] ?? [], i) }
            }
            if self.previewAgain {
                self.previewAgain = false
                self.refreshPreview()
            } else {
                self.previewStale = false
            }
        }
    }

    /// Video: play the covered result in real time, from where the playhead is
    /// (from the start if it is at the end). Stopping leaves the picture there.
    func play() {
        guard let id = currentID, let i = index(of: id), items[i].kind == .video,
              let plan = items[i].plan, !playing else { return }
        let last = items[i].frameCount - 1
        var start = items[i].previewIndex ?? 0
        if start >= last { start = 0 }
        playing = true
        playToken += 1
        let token = playToken
        let payload: [String: Any] = ["path": items[i].url.path, "plan": plan, "settings": settings,
                                      "start": start, "max_side": 1280, "pts": items[i].pts ?? NSNull()]
        view.request("play", payload) { [weak self] event in
            guard let self, token == self.playToken else { return }
            switch event {
            case let .frame(index, b64):
                guard self.playing, let i = self.index(of: id) else { return }
                self.items[i].previewIndex = index
                self.previewStale = false
                if let data = Data(base64Encoded: b64) { self.preview = NSImage(data: data) }
            case .result, .cancelled, .error:
                self.playing = false
            case .progress:
                break
            }
        }
    }

    func stopPlaying() {
        guard playing else { return }
        playing = false
        playToken += 1
        view.cancel()
    }

    // MARK: correcting boxes by hand

    func startEditing() {
        guard let item = current, item.plan != nil, !item.busy else { return }
        stopPlaying()
        editSnapshot = item.edits
        selection = nil
        editBoxes = []
        editing = true
        refreshPreview()
    }

    /// Done keeps the corrections; Cancel puts back the ones from before.
    func endEditing(keep: Bool) {
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

    private func parseBoxes(_ list: [[String: Any]], _ i: Int) -> [EditBox] {
        let baseManual = (items[i].plans[level]?["manual"] as? [Any])?.count ?? 0
        let found = list.filter { $0["index"] != nil && $0["source"] as? String != "manual" }.count
        return list.compactMap { b in
            let n = { (k: String) in CGFloat((b[k] as? NSNumber)?.doubleValue ?? 0) }
            let rect = CGRect(x: n("x"), y: n("y"), width: n("w"), height: n("h"))
            let owner: EditBox.Owner
            let id: String
            if let index = b["index"] as? Int {
                if b["source"] as? String == "manual" {
                    owner = .drawn(index - found)
                } else {
                    owner = .found(key: Edits.key(b))
                }
                id = "b\(index)"
            } else if let track = b["track"] as? Int {
                owner = .track(track)
                id = "t\(track)"
            } else if let m = b["manual"] as? Int {
                guard m >= baseManual else { return nil }
                owner = .manual(m - baseManual)
                id = "m\(m - baseManual)"
            } else {
                return nil
            }
            return EditBox(id: id, owner: owner, rect: rect, enabled: b["enabled"] as? Bool ?? true,
                           uncertain: b["uncertain"] as? Bool ?? false,
                           start: b["start"] as? Int, end: b["end"] as? Int)
        }
    }

    private func edit(_ change: (inout Item) -> Void) {
        guard let id = currentID, let i = index(of: id) else { return }
        change(&items[i])
        rebuild(i)
        refreshPreview()
    }

    /// A box drawn on the picture: on a photo it covers that area; on a video it
    /// covers it, still, for the whole video (the range can then be narrowed).
    func addBox(_ rect: CGRect) {
        guard let item = current else { return }
        if item.kind == .image {
            selection = "b\((item.plan?["boxes"] as? [Any])?.count ?? 0)"
            editBoxes.append(EditBox(id: selection!, owner: .drawn(item.edits.added.count), rect: rect,
                                     enabled: true, uncertain: false, start: nil, end: nil))
            edit { $0.edits.added.append(Edits.box(rect)) }
        } else {
            let last = max(0, item.frameCount - 1)
            selection = "m\(item.edits.manual.count)"
            editBoxes.append(EditBox(id: selection!, owner: .manual(item.edits.manual.count), rect: rect,
                                     enabled: true, uncertain: false, start: 0, end: last))
            edit { $0.edits.manual.append(["start": 0, "end": last, "box": Edits.box(rect)]) }
        }
    }

    /// A box moved or resized. A found box becomes one drawn by hand.
    func moveBox(_ box: EditBox, to rect: CGRect) {
        if let k = editBoxes.firstIndex(where: { $0.id == box.id }) { editBoxes[k].rect = rect }
        switch box.owner {
        case let .found(key):
            let boxes = (current?.plan?["boxes"] as? [Any])?.count ?? 1
            selection = "b\(boxes - 1)"   // the found box goes, the drawn one is last
            edit {
                $0.edits.removed.insert(key)
                $0.edits.added.append(Edits.box(rect))
            }
        case let .drawn(j):
            edit { if $0.edits.added.indices.contains(j) { $0.edits.added[j] = Edits.box(rect) } }
        case let .manual(j):
            edit { if $0.edits.manual.indices.contains(j) { $0.edits.manual[j]["box"] = Edits.box(rect) } }
        case .track:
            break
        }
    }

    /// Delete: a photo box goes away, a manual video box goes away, a track is
    /// switched off (or on again).
    func removeBox(_ box: EditBox) {
        selection = nil
        switch box.owner {
        case let .found(key):
            editBoxes.removeAll { $0.id == box.id }
            edit { $0.edits.removed.insert(key) }
        case let .drawn(j):
            editBoxes.removeAll { $0.id == box.id }
            edit { if $0.edits.added.indices.contains(j) { $0.edits.added.remove(at: j) } }
        case let .manual(j):
            editBoxes.removeAll { $0.id == box.id }
            edit { if $0.edits.manual.indices.contains(j) { $0.edits.manual.remove(at: j) } }
        case let .track(id):
            selection = box.id
            toggleTrack(id)
        }
    }

    func toggleTrack(_ id: Int) {
        guard let base = current?.plans[level],
              let track = (base["tracks"] as? [[String: Any]])?.first(where: { $0["id"] as? Int == id }) else { return }
        let keys = (track["detections"] as? [[Any]] ?? []).compactMap { d -> String? in
            guard d.count == 2, let f = d[0] as? Int, let b = d[1] as? [String: Any] else { return nil }
            return Edits.detectionKey(f, b)
        }
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
        guard let frame = current?.previewIndex else { return }
        edit { item in
            guard item.edits.manual.indices.contains(j) else { return }
            var lo = item.edits.manual[j]["start"] as? Int ?? 0
            var hi = item.edits.manual[j]["end"] as? Int ?? frame
            if start { lo = frame } else { hi = frame }
            item.edits.manual[j]["start"] = min(lo, hi)
            item.edits.manual[j]["end"] = max(lo, hi)
        }
    }

    /// Video: move the playhead (timeline) and show that frame, covered.
    func seek(to frame: Int) {
        guard let id = currentID, let i = index(of: id) else { return }
        stopPlaying()
        items[i].previewIndex = max(0, min(frame, max(0, items[i].frameCount - 1)))
        refreshPreview()
    }
}

/// R2: the app's defaults hold only the four allowed preferences. AppKit adds
/// its own: the open and save panels' last folder and recent places (NSNav*,
/// NSOSP*, written after the panel has returned) and window frames. Every
/// other key is removed at launch, when a panel closes (again shortly after)
/// and at quit.
enum Privacy {
    static let allowedKeys: Set<String> = ["level", "mode", "padding", "language"]

    static func scrub() {
        let defaults = UserDefaults.standard
        guard let id = Bundle.main.bundleIdentifier,
              let domain = defaults.persistentDomain(forName: id) else { return }
        for key in domain.keys where !allowedKeys.contains(key) {
            defaults.removeObject(forKey: key)
        }
        defaults.synchronize()
    }

    static func scrubAfterPanel() {
        scrub()
        for delay in [0.5, 2.0] {
            DispatchQueue.main.asyncAfter(deadline: .now() + delay) { scrub() }
        }
    }

    /// The save panel, opened on the original's folder with `<name>_blurry.<ext>`.
    @MainActor
    static func chooseOutput(for item: Item, in window: NSWindow?, done: @escaping (URL?) -> Void) {
        let panel = NSSavePanel()
        panel.directoryURL = item.url.deletingLastPathComponent()
        panel.nameFieldStringValue = item.url.deletingPathExtension().lastPathComponent + "_blurry." + item.outExt
        if let type = UTType(filenameExtension: item.outExt) { panel.allowedContentTypes = [type] }
        panel.canCreateDirectories = true
        panel.isExtensionHidden = false
        let finish: (NSApplication.ModalResponse) -> Void = { response in
            scrubAfterPanel()
            done(response == .OK ? panel.url : nil)
        }
        if let window {
            panel.beginSheetModal(for: window, completionHandler: finish)
        } else {
            finish(panel.runModal())
        }
    }
}
