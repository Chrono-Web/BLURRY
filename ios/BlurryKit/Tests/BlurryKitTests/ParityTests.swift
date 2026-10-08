import CoreML
import XCTest
@testable import BlurryKit

/// PIANO_BLURRY 5a, tests (a) to (c): BlurryKit against the Python engine.
final class ParityTests: XCTestCase {
    static let detector = Result { try FaceDetector(level: Levels.shared.mostSensitive) }

    func detector() throws -> FaceDetector { try Self.detector.get() }

    /// (a) On the pixels the engine decoded: identical boxes, identical plans and
    /// flags at every level. Scores agree within 1e-5: Core ML and OpenCV DNN sum
    /// the convolutions in a different order, a few float32 ulps apart.
    func testDetectionIdenticalOnEnginePixels() throws {
        try identicalOnEnginePixels(try detector())
    }

    /// The same on the CPU alone, as the app detects in the background.
    func testDetectionIdenticalOnEnginePixelsCPUOnly() throws {
        try identicalOnEnginePixels(FaceDetector(level: Levels.shared.mostSensitive, computeUnits: .cpuOnly))
    }

    private func identicalOnEnginePixels(_ det: FaceDetector) throws {
        let fixtures = Reference.fixtures()
        XCTAssertFalse(fixtures.isEmpty)
        for (name, ref) in fixtures {
            let img = try ImageIn.load(url: Reference.url(ref["decoded"] as! String))
            let boxes = try det.detect(img.rgb)
            assertSame(boxes, Reference.boxes(ref["boxes"]), name)
            let plan = ImagePlan(width: img.rgb.width, height: img.rgb.height, boxes: boxes)
            for level in Levels.shared.levels {
                let at = Review.imagePlan(plan, at: level.confidence)
                let refPlan = (ref["plans"] as! [String: Any])[level.name] as! [String: Any]
                assertSame(at.boxes, Reference.boxes(refPlan["boxes"]), "\(name) \(level.name)")
                XCTAssertEqual(at.flags, Reference.flags(refPlan["flags"]), "\(name) \(level.name)")
            }
        }
    }

    /// (b) From the original file, read with ImageIO instead of Pillow: the same
    /// faces with IoU >= 0.9 each (the baseline criterion of PIANO_BLURRY §6),
    /// and pixels within JPEG decoder noise.
    func testEndToEndWithImageIO() throws {
        let det = try detector()
        for (name, ref) in Reference.fixtures() {
            let loaded = try ImageIn.load(url: Reference.root.appendingPathComponent(ref["source"] as! String))
            XCTAssertEqual(loaded.rgb.width, ref["width"] as? Int, name)
            XCTAssertEqual(loaded.rgb.height, ref["height"] as? Int, name)
            XCTAssertEqual(loaded.outFormat.rawValue, ref["out_format"] as? String, name)
            XCTAssertEqual(loaded.metadataFound, ref["metadata_found"] as? [String], name)

            let engine = try ImageIn.load(url: Reference.url(ref["decoded"] as! String))
            let d = Pixels.diff(loaded.rgb.pixels, engine.rgb.pixels)
            XCTAssertLessThanOrEqual(d.mean, Pixels.decoderNoise, "\(name): decoded pixels differ by \(d.mean) on average")

            let m = match(Reference.boxes(ref["boxes"]), try det.detect(loaded.rgb))
            XCTAssertTrue(m.missing.isEmpty && m.extra.isEmpty, "\(name): missing \(m.missing), extra \(m.extra)")
            XCTAssertGreaterThanOrEqual(m.minIoU, 0.9, name)
            print(String(format: "  %@: pixels Δ mean %.2f max %d, min IoU %.3f", name, d.mean, d.max, m.minIoU))
        }
    }

    /// (c) On the same pixels and boxes, the covered areas are those of redact.py:
    /// solid identical to the byte, pixelation at most 1 level apart.
    func testRedactionMatchesEngine() throws {
        for (name, ref) in Reference.fixtures() {
            let base = try ImageIn.load(url: Reference.url(ref["decoded"] as! String)).rgb
            let renders = ref["renders"] as! [String: String]
            for mode in CoverMode.allCases {
                var img = base
                var alpha: [UInt8]? = nil
                Redact.apply(&img, alpha: &alpha, boxes: Reference.boxes(ref["boxes"]), mode: mode,
                             padding: ref["padding"] as! Double, blocks: ref["blocks"] as! Int)
                let expected = try ImageIn.load(url: Reference.url(renders[mode.rawValue]!)).rgb
                let d = Pixels.diff(img.pixels, expected.pixels)
                if mode == .solid {
                    XCTAssertEqual(d.count, 0, "\(name) solid: \(d.count) bytes differ")
                } else {
                    XCTAssertLessThanOrEqual(d.max, 1, "\(name) pixel: max Δ \(d.max)")
                    print("  \(name) pixel: \(d.count) bytes 1 level apart")
                }
            }
        }
    }
}
