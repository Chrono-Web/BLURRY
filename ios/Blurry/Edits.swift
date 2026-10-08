import BlurryKit
import CoreGraphics
import Foundation

/// Corrections made by hand, kept apart from the analysis so that they
/// survive a change of sensitivity: every level's plan comes from the same
/// detections, so a found box or a track is recognised by its coordinates at
/// any level. As macos/Sources/Blurry/Edits.swift.
struct Edits: Equatable {
    var removed: Set<String> = []     // photo: found boxes taken away (by key)
    var added: [Box] = []             // photo: boxes drawn by hand
    var disabled: Set<String> = []    // video: detections of switched-off tracks
    var manual: [ManualRange] = []    // video: still boxes over a span of frames

    var isEmpty: Bool { removed.isEmpty && added.isEmpty && disabled.isEmpty && manual.isEmpty }

    static func key(_ b: Box) -> String { "\(b.x),\(b.y),\(b.w),\(b.h)" }

    static func detectionKey(_ frame: Int, _ b: Box) -> String { "\(frame):" + key(b) }

    /// Video: the plan for the chosen level with tracks switched off and the
    /// boxes drawn by hand.
    func apply(toVideo base: VideoPlan?) -> VideoPlan? {
        guard var plan = base else { return nil }
        for i in plan.tracks.indices {
            let off = plan.tracks[i].detections.contains { disabled.contains(Edits.detectionKey($0.key, $0.value)) }
            plan.tracks[i].enabled = !off
        }
        plan.manual += manual
        return plan
    }

    static func box(_ r: CGRect) -> Box {
        Box(x: Int(r.minX), y: Int(r.minY), w: max(1, Int(r.width)), h: max(1, Int(r.height)),
            score: nil, source: .manual)
    }

    /// The plan the export uses: the analysis for the chosen level, corrected.
    func apply(to base: ImagePlan?) -> ImagePlan? {
        guard var plan = base else { return nil }
        var kept: [Box] = []
        var moved: [Int: Int] = [:]
        for (i, b) in plan.boxes.enumerated() where !removed.contains(Edits.key(b)) {
            moved[i] = kept.count
            kept.append(b)
        }
        let all = kept + added
        plan.boxes = all
        // Flags point at boxes by position: follow them, drop those of removed boxes.
        plan.flags = plan.flags.compactMap { flag in
            if flag.kind == .noFaces { return all.isEmpty ? flag : nil }
            guard let i = flag.box else { return flag }
            guard let j = moved[i] else { return nil }
            var f = flag
            f.box = j
            return f
        }
        return plan
    }
}

/// One box as the editor draws it, in the picture's own pixels.
struct EditBox: Identifiable, Equatable {
    enum Owner: Equatable {
        case found(key: String)   // photo, found by the analysis
        case drawn(Int)           // photo, index in Edits.added
        case track(Int)           // video, a track id (follows the face)
        case manual(Int)          // video, index in Edits.manual
    }

    let id: String
    let owner: Owner
    var rect: CGRect
    var enabled = true
    let uncertain: Bool
    var start: Int? = nil
    var end: Int? = nil

    /// Photo boxes and manual video boxes move and resize; a track follows the
    /// face, so it can only be switched off.
    var movable: Bool { if case .track = owner { false } else { true } }
}
