import Foundation

/// A rectangle in display-oriented image coordinates (before padding), as plan.Box.
public struct Box: Equatable, Hashable, Sendable {
    public enum Source: String, Sendable { case auto, manual }

    public var x, y, w, h: Int
    public var score: Double?   // nil for manual boxes
    public var source: Source

    public init(x: Int, y: Int, w: Int, h: Int, score: Double? = nil, source: Source = .auto) {
        self.x = x; self.y = y; self.w = w; self.h = h
        self.score = score
        self.source = source
    }

    public var longSide: Int { max(w, h) }

    public func iou(_ other: Box) -> Double {
        let ix = max(0, min(x + w, other.x + other.w) - max(x, other.x))
        let iy = max(0, min(y + h, other.y + other.h) - max(y, other.y))
        let inter = ix * iy
        let union = w * h + other.w * other.h - inter
        return union > 0 ? Double(inter) / Double(union) : 0
    }

    public func union(_ other: Box) -> Box {
        let x0 = min(x, other.x), y0 = min(y, other.y)
        let x1 = max(x + w, other.x + other.w), y1 = max(y + h, other.y + other.h)
        return Box(x: x0, y: y0, w: x1 - x0, h: y1 - y0, score: nil, source: source)
    }
}

/// A review flag, as plan.Flag.
public struct Flag: Equatable, Hashable, Sendable {
    public enum Kind: String, Sendable {
        case noFaces = "no_faces"
        case nearThreshold = "near_threshold"
        case smallFace = "small_face"
        case trackGap = "track_gap"
    }

    public var kind: Kind
    public var frame: Int?
    public var track: Int?
    public var box: Int?

    public init(_ kind: Kind, frame: Int? = nil, track: Int? = nil, box: Int? = nil) {
        self.kind = kind; self.frame = frame; self.track = track; self.box = box
    }
}

/// What will be covered in an image. Lives in memory only, never on disk.
public struct ImagePlan: Equatable, Sendable {
    public var width: Int
    public var height: Int
    public var boxes: [Box] = []
    public var flags: [Flag] = []
    public var facesExpected = true

    public init(width: Int, height: Int, boxes: [Box] = [], flags: [Flag] = [], facesExpected: Bool = true) {
        self.width = width; self.height = height
        self.boxes = boxes; self.flags = flags
        self.facesExpected = facesExpected
    }

    public mutating func addBox(_ box: Box) {
        boxes.append(Box(x: box.x, y: box.y, w: box.w, h: box.h, score: nil, source: .manual))
    }

    public mutating func removeBox(at index: Int) {
        boxes.remove(at: index)
    }
}

/// The rules of engine.py that do not touch files.
public enum Review {
    /// engine.image_flags.
    public static func imageFlags(_ plan: ImagePlan, confidence: Double,
                                  levels: Levels = .shared) -> [Flag] {
        var flags: [Flag] = []
        for (i, box) in plan.boxes.enumerated() {
            if let score = box.score, score < confidence + levels.nearThresholdMargin {
                flags.append(Flag(.nearThreshold, box: i))
            }
            if box.longSide < levels.smallFacePx {
                flags.append(Flag(.smallFace, box: i))
            }
        }
        if plan.facesExpected && plan.boxes.isEmpty {
            flags.append(Flag(.noFaces))
        }
        return flags
    }

    /// Manual boxes have no score and always count.
    public static func reaches(_ box: Box, _ confidence: Double) -> Bool {
        box.score.map { $0 >= confidence } ?? true
    }

    /// engine.image_plan_at: the plan a less sensitive level would give, from a
    /// detection at the most sensitive one (YuNet applies the threshold before NMS).
    public static func imagePlan(_ plan: ImagePlan, at confidence: Double,
                                 levels: Levels = .shared) -> ImagePlan {
        var out = ImagePlan(width: plan.width, height: plan.height,
                            boxes: plan.boxes.filter { reaches($0, confidence) },
                            facesExpected: plan.facesExpected)
        if plan.facesExpected {
            out.flags = imageFlags(out, confidence: confidence, levels: levels)
        }
        return out
    }
}
