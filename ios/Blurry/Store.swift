import BlurryKit
import CoreGraphics
import Observation
import SwiftUI

/// One photo. Lives in memory only: its bytes, never a path.
struct Item: Identifiable {
    enum Status { case waiting, analyzing, ready, review, noFaces, exporting, exported, error }

    let id = UUID()
    let name: String          // shown, and the base of the exported file's name
    let source: Source
    var status: Status = .waiting
    var plans: [String: ImagePlan] = [:]   // one per level, from a single analysis
    var plan: ImagePlan?                   // the one for the chosen level, corrected
    var edits = Edits()                    // corrections by hand
    var outFormat: OutFormat?
    var faces: Int?
    var thumb: CGImage?
    var error = ""
    var exportedAs: String?                // "Saved" / "Shared"

    init(name: String, data: Data, ext: String) {
        self.name = name
        source = Source(id: id, data: data, ext: ext.lowercased())
    }

    var analysed: Bool { [.ready, .review, .noFaces, .exported].contains(status) }
    var busy: Bool { status == .analyzing || status == .exporting }

    /// `<name>_blurry.<ext>`, as in the Mac app.
    var outputName: String {
        let stem = (name as NSString).deletingPathExtension
        return stem + "_blurry." + (outFormat?.ext ?? "jpg")
    }
}

/// The guide's steps, one at a time (no audio step: photos only, for now).
enum Step: Int, CaseIterable {
    case sensitivity, cover, margin, result
}

/// A clean file ready to leave the app, waiting for the sheet that takes it.
struct PendingExport: Identifiable {
    enum Destination { case files, share }
    let id = UUID()
    let item: UUID
    let destination: Destination
    let data: Data
    let name: String
    var url: URL?   // share: the temporary copy the share sheet reads
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
            refreshPreview()
        }
    }
    var preview: CGImage?
    var previewStale = false
    var usingPrevious = false
    var pendingExport: PendingExport?

    // Correcting boxes by hand.
    var editing = false
    var editBoxes: [EditBox] = []
    var selection: String?
    @ObservationIgnored private var editSnapshot: Edits?

    // Settings kept between sessions (R2 allows exactly these).
    var level: String {
        didSet { if level != oldValue { defaults.set(level, forKey: "level"); applyLevel() } }
    }
    var mode: String { didSet { defaults.set(mode, forKey: "mode"); settingsChanged() } }
    var padding: Double {
        didSet { defaults.set((padding * 100).rounded() / 100, forKey: "padding"); settingsChanged() }
    }

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

    /// False while the app is in the background: no work starts then (iOS
    /// does not let an app use the GPU from the background).
    var active = true { didSet { if active && !oldValue { pump() } } }

    @ObservationIgnored let engine = Engine()
    @ObservationIgnored private let defaults: UserDefaults
    @ObservationIgnored private var skipped: Set<UUID> = []
    @ObservationIgnored private var confirmedOnce = false
    @ObservationIgnored private var analysing = false
    @ObservationIgnored private var previewInFlight = false
    @ObservationIgnored private var previewAgain = false
    @ObservationIgnored private var photoCount = 0

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
        Settings(level: level, mode: CoverMode(rawValue: mode) ?? .solid, padding: padding)
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

    /// Files read into memory by a picker or "Open in". `name` is nil for
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

    func remove(_ ids: Set<UUID>) {
        if let id = currentID, ids.contains(id) { currentID = nil }
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
        guard active, !analysing, fatal == nil else { return }
        let waiting = items.filter { $0.status == .waiting }
        guard let next = waiting.first(where: { $0.id == currentID }) ?? waiting.first,
              let i = index(of: next.id) else { return }
        analysing = true
        items[i].status = .analyzing
        let id = next.id, source = next.source
        Task {
            let result: Result<Analysis, Error>
            do { result = .success(try await engine.analyze(source)) } catch { result = .failure(error) }
            analysing = false
            if let i = index(of: id) {
                switch result {
                case let .success(a):
                    items[i].plans = a.plans
                    items[i].outFormat = a.outFormat
                    items[i].thumb = a.thumb
                    rebuild(i)
                    if id == currentID {
                        preview = a.thumb
                        refreshPreview()
                    }
                case let .failure(error):
                    if active {
                        fail(i, error)
                    } else {
                        items[i].status = .waiting   // interrupted by the background: again later
                    }
                }
            }
            pump()
        }
    }

    private func fail(_ i: Int, _ error: Error) {
        items[i].status = .error
        // BlurryKit's errors carry the engine's own messages; anything else, the system's.
        switch error {
        case let e as InputError: items[i].error = e.description
        case let e as ModelIntegrityError: items[i].error = e.description
        case let e as ImageOut.EncodeError: items[i].error = e.description
        default: items[i].error = error.localizedDescription
        }
    }

    func retry() {
        guard let id = currentID, let i = index(of: id) else { return }
        items[i].error = ""
        if items[i].plans.isEmpty { items[i].status = .waiting } else { settle(i) }
        refreshPreview()
        pump()
    }

    /// A new level is instant: every analysed file already has the plan for it.
    private func applyLevel() {
        for i in items.indices where !items[i].plans.isEmpty && items[i].status != .exporting {
            if items[i].status == .exported && items[i].id != currentID { continue }
            rebuild(i)
        }
        refreshPreview()
    }

    private func rebuild(_ i: Int) {
        items[i].plan = items[i].edits.apply(to: items[i].plans[level])
        settle(i)
    }

    private func settingsChanged() {
        if let id = currentID, let i = index(of: id), items[i].status == .exported { settle(i) }
        refreshPreview()
    }

    /// The status after analysis, as Store.settle on the Mac.
    private func settle(_ i: Int) {
        let plan = items[i].plan
        let faces = plan?.boxes.count ?? 0
        items[i].faces = faces
        let flags = (plan?.flags ?? []).filter { $0.kind != .noFaces }
        if plan?.facesExpected ?? true, faces == 0 {
            items[i].status = .noFaces
        } else if !flags.isEmpty && items[i].edits.isEmpty {
            items[i].status = .review
        } else {
            items[i].status = .ready
        }
    }

    // MARK: the picture

    /// Coalesced: while one preview is being made, only the latest change follows.
    func refreshPreview() {
        guard let item = current, let plan = item.plan else {
            preview = current?.thumb
            previewStale = step != .sensitivity && current.map { !$0.analysed && $0.status != .error } ?? false
            return
        }
        previewStale = true
        if previewInFlight {
            previewAgain = true
            return
        }
        previewInFlight = true
        let id = item.id, edit = editing, settings = settings
        let outline = step == .sensitivity && !edit
        Task {
            let image = try? await engine.preview(item.source, plan: plan, settings: settings,
                                                  outline: outline, plain: edit)
            previewInFlight = false
            if id == currentID, let image { preview = image }
            if previewAgain {
                previewAgain = false
                refreshPreview()
            } else {
                previewStale = false
            }
        }
    }

    // MARK: export

    /// Render the clean file, then hand it to Files or to the share sheet.
    func export(to destination: PendingExport.Destination) {
        guard let id = currentID, let i = index(of: id), let plan = items[i].plan, !items[i].busy else { return }
        items[i].status = .exporting
        let source = items[i].source, settings = settings, name = items[i].outputName
        Task {
            do {
                let data = try await engine.render(source, plan: plan, settings: settings)
                guard index(of: id) != nil else { return }
                var pending = PendingExport(item: id, destination: destination, data: data, name: name)
                if destination == .share { pending.url = try Privacy.shareableFile(data, name: name) }
                pendingExport = pending
            } catch {
                if let i = index(of: id) { fail(i, error) }
            }
        }
    }

    /// The sheet closed: saved or shared, or cancelled (back to ready).
    func finishExport(_ done: Bool) {
        guard let pending = pendingExport else { return }
        pendingExport = nil
        if let url = pending.url { try? FileManager.default.removeItem(at: url.deletingLastPathComponent()) }
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
        guard let item = current, item.plan != nil, !item.busy else { return }
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
    private func boxes(of item: Item) -> [EditBox] {
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
            return EditBox(id: "b\(i)", owner: owner,
                           rect: CGRect(x: b.x, y: b.y, width: b.w, height: b.h), uncertain: uncertain.contains(i))
        }
    }

    private func edit(_ change: (inout Item) -> Void) {
        guard let id = currentID, let i = index(of: id) else { return }
        change(&items[i])
        rebuild(i)
        editBoxes = boxes(of: items[i])
    }

    func addBox(_ rect: CGRect) {
        guard let item = current else { return }
        edit { $0.edits.added.append(Edits.box(rect)) }
        selection = "b\((item.plan?.boxes.count ?? 0))"
    }

    /// A box moved or resized. A found box becomes one drawn by hand.
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
        }
    }

    func removeBox(_ box: EditBox) {
        selection = nil
        switch box.owner {
        case let .found(key): edit { $0.edits.removed.insert(key) }
        case let .drawn(j): edit { if $0.edits.added.indices.contains(j) { $0.edits.added.remove(at: j) } }
        }
    }

    // MARK: life cycle

    /// The app left the screen: drop the decoded picture and every copy.
    func didEnterBackground() {
        active = false
        Task { await engine.forget() }
        if pendingExport == nil { Privacy.clearCopies() }
        Privacy.scrub(defaults)
    }
}
