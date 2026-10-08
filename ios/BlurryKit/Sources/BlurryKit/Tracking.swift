import Foundation

/// A face followed across frames, as plan.Track.
public struct Track: Equatable, Sendable {
    public let id: Int
    public var detections: [Int: Box]   // frame -> box
    public var enabled = true

    public init(id: Int, detections: [Int: Box], enabled: Bool = true) {
        self.id = id; self.detections = detections; self.enabled = enabled
    }

    public var first: Int { detections.keys.min()! }
    public var last: Int { detections.keys.max()! }
    public var lastBox: Box { detections[last]! }
}

/// A still box drawn by hand over a span of frames (both ends included).
public struct ManualRange: Equatable, Sendable {
    public var start: Int
    public var end: Int
    public var box: Box

    public init(start: Int, end: Int, box: Box) {
        self.start = start; self.end = end; self.box = box
    }
}

/// What will be covered in a video, as plan.VideoPlan. Memory only.
public struct VideoPlan: Equatable, Sendable {
    public var width: Int
    public var height: Int
    public var frameCount: Int
    public var fps: Double
    public var extendFrames: Int
    public var tracks: [Track] = []
    public var flags: [Flag] = []
    public var manual: [ManualRange] = []
    public var facesExpected = true
    public var maxSimultaneous = 0

    public init(width: Int, height: Int, frameCount: Int, fps: Double, extendFrames: Int,
                tracks: [Track] = [], flags: [Flag] = [], manual: [ManualRange] = [],
                facesExpected: Bool = true, maxSimultaneous: Int = 0) {
        self.width = width; self.height = height; self.frameCount = frameCount; self.fps = fps
        self.extendFrames = extendFrames; self.tracks = tracks; self.flags = flags; self.manual = manual
        self.facesExpected = facesExpected; self.maxSimultaneous = maxSimultaneous
    }

    /// Every box covered in every frame: enabled tracks in order (extended in
    /// time, gaps bridged), then the manual ranges. Frames with nothing are absent.
    public func coverage() -> [Int: [Box]] {
        var cov: [Int: [Box]] = [:]
        for track in tracks where track.enabled {
            for (frame, box) in Tracking.coverage(track, extend: extendFrames, frameCount: frameCount)
                .sorted(by: { $0.key < $1.key }) {
                cov[frame, default: []].append(box)
            }
        }
        for m in manual {
            let lo = max(0, m.start), hi = min(frameCount - 1, m.end)
            guard hi >= lo else { continue }
            for frame in lo...hi { cov[frame, default: []].append(m.box) }
        }
        return cov
    }

    public mutating func setTrackEnabled(_ id: Int, _ enabled: Bool) {
        if let i = tracks.firstIndex(where: { $0.id == id }) { tracks[i].enabled = enabled }
    }

    /// A manual box over [start, end], clipped to the video.
    public mutating func addManual(start: Int, end: Int, box: Box) {
        let lo = max(0, min(start, end)), hi = min(frameCount - 1, max(start, end))
        guard hi >= lo else { return }
        manual.append(ManualRange(start: lo, end: hi,
                                  box: Box(x: box.x, y: box.y, w: box.w, h: box.h, score: nil, source: .manual)))
    }
}

/// tracking.py: link per-frame detections into tracks and extend coverage in
/// time. Every box is held half a second before and after it was seen, and a
/// gap inside a track is covered by the union of the boxes on either side.
public enum Tracking {
    public static let matchIoU = 0.2
    /// A gap of this many missing frames (or more) inside a track is flagged.
    public static let gapFlagFrames = 3

    /// Greedy IoU matching against the last box of each recently seen track.
    public static func buildTracks(_ detections: [[Box]], maxGap: Int) -> [Track] {
        var tracks: [Track] = []
        for (frame, boxes) in detections.enumerated() {
            let active = tracks.indices.filter { frame - tracks[$0].last <= maxGap + 1 }
            // Python sorts (iou, box index, track index) tuples, largest first.
            var pairs: [(Double, Int, Int)] = []
            for (bi, box) in boxes.enumerated() {
                for (ti, t) in active.enumerated() { pairs.append((box.iou(tracks[t].lastBox), bi, ti)) }
            }
            pairs.sort { a, b in
                if a.0 != b.0 { return a.0 > b.0 }
                if a.1 != b.1 { return a.1 > b.1 }
                return a.2 > b.2
            }
            var usedBoxes = Set<Int>(), usedTracks = Set<Int>()
            for (iou, bi, ti) in pairs {
                if iou < matchIoU { break }
                if usedBoxes.contains(bi) || usedTracks.contains(ti) { continue }
                tracks[active[ti]].detections[frame] = boxes[bi]
                usedBoxes.insert(bi)
                usedTracks.insert(ti)
            }
            for (bi, box) in boxes.enumerated() where !usedBoxes.contains(bi) {
                tracks.append(Track(id: tracks.count, detections: [frame: box]))
            }
        }
        return tracks
    }

    public static func coverage(_ track: Track, extend: Int, frameCount: Int) -> [Int: Box] {
        let frames = track.detections.keys.sorted()
        var cov: [Int: Box] = [:]
        func put(_ frame: Int, _ box: Box) {
            guard frame >= 0 && frame < frameCount else { return }
            cov[frame] = cov[frame].map { $0.union(box) } ?? box
        }
        for (a, b) in zip(frames, frames.dropFirst()) {
            let boxA = track.detections[a]!, boxB = track.detections[b]!
            let bridge = boxA.union(boxB)
            put(a, boxA)
            for f in (a + 1)..<max(a + 1, b) { put(f, bridge) }
        }
        if let last = frames.last { put(last, track.detections[last]!) }
        for f in frames {
            let box = track.detections[f]!
            for g in (f - extend)...(f + extend) { put(g, box) }
        }
        return cov
    }

    public static func flags(_ tracks: [Track], confidence: Double, levels: Levels = .shared) -> [Flag] {
        var flags: [Flag] = []
        for track in tracks {
            let frames = track.detections.keys.sorted()
            for (a, b) in zip(frames, frames.dropFirst()) where b - a - 1 >= gapFlagFrames {
                flags.append(Flag(.trackGap, frame: b, track: track.id))
            }
            let scores = track.detections.values.compactMap(\.score)
            if let best = scores.max(), best < confidence + levels.nearThresholdMargin {
                flags.append(Flag(.nearThreshold, frame: track.first, track: track.id))
            }
            let sides = track.detections.values.map(\.longSide).sorted()
            if sides[sides.count / 2] < levels.smallFacePx {
                flags.append(Flag(.smallFace, frame: track.first, track: track.id))
            }
        }
        return flags
    }

    public static func maxSimultaneous(_ detections: [[Box]]) -> Int {
        detections.map(\.count).max() ?? 0
    }

    /// engine.video_plan_from: tracks, flags and coverage from per-frame
    /// detections, keeping only the boxes whose score reaches `confidence`.
    public static func videoPlan(_ detections: [[Box]], width: Int, height: Int, fps: Double,
                                 facesExpected: Bool, confidence: Double,
                                 levels: Levels = .shared) -> VideoPlan {
        // Python's round() rounds half to even.
        var plan = VideoPlan(width: width, height: height, frameCount: detections.count, fps: fps,
                             extendFrames: max(1, Int((fps * 0.5).rounded(.toNearestOrEven))),
                             facesExpected: facesExpected)
        if facesExpected {
            let kept = detections.map { $0.filter { Review.reaches($0, confidence) } }
            plan.tracks = buildTracks(kept, maxGap: max(1, Int(fps.rounded(.toNearestOrEven))))
            plan.flags = flags(plan.tracks, confidence: confidence, levels: levels)
            plan.maxSimultaneous = maxSimultaneous(kept)
            if plan.tracks.isEmpty { plan.flags.append(Flag(.noFaces)) }
        }
        return plan
    }
}
