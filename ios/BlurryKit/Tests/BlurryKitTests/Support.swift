import Foundation
import XCTest
@testable import BlurryKit

/// What the Python engine did, written by scripts/coreml/riferimento.py.
enum Reference {
    static let root = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .deletingLastPathComponent().deletingLastPathComponent()
    static let parity = root.appendingPathComponent("build/parity")

    /// Fails (never skips) when the reference is missing: the parity tests are the point.
    static func data(file: StaticString = #filePath, line: UInt = #line) -> [String: Any]? {
        let url = parity.appendingPathComponent("reference.json")
        guard let data = try? Data(contentsOf: url),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            XCTFail("missing build/parity/reference.json: run scripts/coreml/test-kit.sh", file: file, line: line)
            return nil
        }
        return json
    }

    static func fixtures() -> [(String, [String: Any])] {
        ((data()?["fixtures"] as? [String: Any]) ?? [:]).map { ($0.key, $0.value as! [String: Any]) }
            .sorted { $0.0 < $1.0 }
    }

    static func extra() -> [(String, [String: Any])] {
        ((data()?["extra"] as? [String: Any]) ?? [:]).map { ($0.key, $0.value as! [String: Any]) }
            .sorted { $0.0 < $1.0 }
    }

    static func url(_ relative: String) -> URL { parity.appendingPathComponent(relative) }

    /// [[x, y, w, h, score]] -> boxes.
    static func boxes(_ value: Any?) -> [Box] {
        ((value as? [[Any]]) ?? []).map { b in
            Box(x: (b[0] as! NSNumber).intValue, y: (b[1] as! NSNumber).intValue,
                w: (b[2] as! NSNumber).intValue, h: (b[3] as! NSNumber).intValue,
                score: (b[4] as? NSNumber)?.doubleValue)
        }
    }

    static func flags(_ value: Any?) -> [Flag] {
        ((value as? [[String: Any]]) ?? []).map { d in
            Flag(Flag.Kind(rawValue: d["kind"] as! String)!, frame: d["frame"] as? Int,
                 track: d["track"] as? Int, box: d["box"] as? Int)
        }
    }
}

enum Pixels {
    /// Mean difference allowed between two JPEG/HEIC decoders (ImageIO and
    /// Pillow): measured up to 1.9 on macOS 14, 1.6 on macOS 26. A wrong
    /// orientation, profile or channel order gives tens of levels.
    static let decoderNoise = 3.0

    /// Mean and max absolute difference over the bytes where `mask` is true.
    static func diff(_ a: [UInt8], _ b: [UInt8], mask: ((Int) -> Bool)? = nil) -> (mean: Double, max: Int, count: Int) {
        precondition(a.count == b.count)
        var total = 0, worst = 0, n = 0, differing = 0
        for i in 0..<a.count where mask?(i) ?? true {
            let d = abs(Int(a[i]) - Int(b[i]))
            total += d
            worst = max(worst, d)
            n += 1
            if d != 0 { differing += 1 }
        }
        return (n > 0 ? Double(total) / Double(n) : 0, worst, differing)
    }
}

/// Greedy IoU matching, as scripts/coreml/compare.py.
func match(_ ref: [Box], _ got: [Box]) -> (missing: [Box], extra: [Box], minIoU: Double) {
    var used = Set<Int>(), missing: [Box] = [], minIoU = 1.0
    for r in ref {
        var best = 0.0, bi: Int?
        for (i, g) in got.enumerated() where !used.contains(i) {
            let v = r.iou(g)
            if v > best { best = v; bi = i }
        }
        guard let bi, best >= 0.5 else { missing.append(r); continue }
        used.insert(bi)
        minIoU = min(minIoU, best)
    }
    let extra = got.enumerated().filter { !used.contains($0.offset) }.map(\.element)
    return (missing, extra, minIoU)
}

/// Identical boxes; scores within 1e-5 (Core ML and OpenCV DNN sum the
/// convolutions in a different order).
func assertSame(_ got: [Box], _ ref: [Box], _ what: String,
                file: StaticString = #filePath, line: UInt = #line) {
    XCTAssertEqual(got.count, ref.count, what, file: file, line: line)
    for (g, r) in zip(got, ref) {
        XCTAssertEqual([g.x, g.y, g.w, g.h], [r.x, r.y, r.w, r.h], what, file: file, line: line)
        XCTAssertEqual(g.score ?? -1, r.score ?? -1, accuracy: 1e-5, what, file: file, line: line)
    }
}
