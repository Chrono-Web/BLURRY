import BlurryKit
import CoreGraphics
import Foundation

/// Corrections made by hand on a photo, kept apart from the analysis so that
/// they survive a change of sensitivity: every level's plan comes from the
/// same detections, so a found box is recognised by its coordinates at any
/// level. The photo half of macos/Sources/Blurry/Edits.swift.
struct Edits: Equatable {
    var removed: Set<String> = []   // found boxes taken away (by key)
    var added: [Box] = []           // boxes drawn by hand

    var isEmpty: Bool { removed.isEmpty && added.isEmpty }

    static func key(_ b: Box) -> String { "\(b.x),\(b.y),\(b.w),\(b.h)" }

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
        case found(key: String)   // found by the analysis
        case drawn(Int)           // index in Edits.added
    }

    let id: String
    let owner: Owner
    var rect: CGRect
    let uncertain: Bool
}
