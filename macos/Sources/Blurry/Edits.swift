import CoreGraphics
import Foundation

/// Corrections made by hand, kept apart from the analysis so that they survive
/// a change of sensitivity: every level's plan comes from the same detections,
/// so a found box or a track is recognised by its coordinates at any level.
struct Edits {
    var removed: Set<String> = []          // photo: found boxes taken away (by key)
    var added: [[String: Any]] = []        // photo: boxes drawn by hand
    var disabled: Set<String> = []         // video: detections of switched-off tracks
    var manual: [[String: Any]] = []       // video: {start, end, box}, still boxes over a span

    var isEmpty: Bool { removed.isEmpty && added.isEmpty && disabled.isEmpty && manual.isEmpty }

    static func key(_ b: [String: Any]) -> String {
        ["x", "y", "w", "h"].map { String((b[$0] as? NSNumber)?.intValue ?? 0) }.joined(separator: ",")
    }

    static func key(_ r: CGRect) -> String {
        [r.minX, r.minY, r.width, r.height].map { String(Int($0)) }.joined(separator: ",")
    }

    static func detectionKey(_ frame: Int, _ b: [String: Any]) -> String { "\(frame):" + key(b) }

    static func box(_ r: CGRect) -> [String: Any] {
        ["x": Int(r.minX), "y": Int(r.minY), "w": max(1, Int(r.width)), "h": max(1, Int(r.height)),
         "source": "manual"]
    }

    /// The plan the export uses: the analysis for the chosen level, corrected.
    func apply(to base: [String: Any]?) -> [String: Any]? {
        guard var plan = base else { return nil }
        if plan["type"] as? String == "image" {
            let boxes = plan["boxes"] as? [[String: Any]] ?? []
            var kept: [[String: Any]] = []
            var moved: [Int: Int] = [:]
            for (i, b) in boxes.enumerated() where !removed.contains(Edits.key(b)) {
                moved[i] = kept.count
                kept.append(b)
            }
            let all = kept + added
            plan["boxes"] = all
            // Flags point at boxes by position: follow them, drop those of removed boxes.
            plan["flags"] = (plan["flags"] as? [[String: Any]] ?? []).compactMap { flag -> [String: Any]? in
                if flag["kind"] as? String == "no_faces" { return all.isEmpty ? flag : nil }
                guard let i = flag["box"] as? Int else { return flag }
                guard let j = moved[i] else { return nil }
                var f = flag
                f["box"] = j
                return f
            }
        } else {
            plan["tracks"] = (plan["tracks"] as? [[String: Any]] ?? []).map { track -> [String: Any] in
                var t = track
                let off = (track["detections"] as? [[Any]] ?? []).contains { d in
                    guard d.count == 2, let f = d[0] as? Int, let b = d[1] as? [String: Any] else { return false }
                    return disabled.contains(Edits.detectionKey(f, b))
                }
                t["enabled"] = !off
                return t
            }
            plan["manual"] = (plan["manual"] as? [[String: Any]] ?? []) + manual
        }
        return plan
    }
}

/// One box as the editor draws it, in the picture's own pixels.
struct EditBox: Identifiable, Equatable {
    enum Owner: Equatable {
        case found(key: String)      // photo, found by the analysis
        case drawn(Int)              // photo, index in Edits.added
        case track(Int)              // video, a track id (follows the face)
        case manual(Int)             // video, index in Edits.manual
    }

    let id: String
    let owner: Owner
    var rect: CGRect
    let enabled: Bool
    let uncertain: Bool
    let start: Int?
    let end: Int?

    /// Photo boxes and manual video boxes can be moved and resized; a track
    /// follows the face, so it can only be switched off.
    var movable: Bool { if case .track = owner { false } else { true } }
}
