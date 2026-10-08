import AVFoundation
import XCTest
@testable import BlurryKit

/// PIANO_BLURRY 5c: videos against the Python engine, on the videos of
/// tests/test_video.py (scripts/coreml/riferimento.py makes them).
final class VideoTests: XCTestCase {
    static let detector = Result { try FaceDetector(level: Levels.shared.mostSensitive) }

    private func videos() -> [(String, [String: Any])] {
        ((Reference.data()?["videos"] as? [String: Any]) ?? [:]).map { ($0.key, $0.value as! [String: Any]) }
            .sorted { $0.0 < $1.0 }
    }

    private func url(_ name: String) -> URL { Reference.url("video/\(name)") }

    /// Size in display orientation, frame rate, frames, sound, and the metadata
    /// found, as video_io.probe and analyze_video report them.
    func testProbeLikeEngine() async throws {
        let all = videos()
        XCTAssertFalse(all.isEmpty)
        for (name, ref) in all {
            let info = try await VideoIn.probe(url(name))
            XCTAssertEqual(info.width, ref["width"] as? Int, name)
            XCTAssertEqual(info.height, ref["height"] as? Int, name)
            XCTAssertEqual(info.fps, ref["fps"] as! Double, accuracy: 0.01, name)
            XCTAssertEqual(info.hasAudio, ref["has_audio"] as? Bool, name)
            XCTAssertEqual(info.metadataFound, ref["metadata_found"] as? [String], name)
            let frames = try await VideoIn.frames(url(name)) { _, _, _ in true }
            XCTAssertEqual(frames, ref["frames"] as? Int, name)
        }
    }

    /// From the engine's own detections, the same tracks, flags and coverage
    /// in every frame, at every level: tracking is a pure function.
    func testTrackingIdenticalFromEngineDetections() throws {
        for (name, ref) in videos() {
            let detections = (ref["detections"] as! [Any]).map { Reference.boxes($0) }
            for level in Levels.shared.levels {
                let r = (ref["plans"] as! [String: Any])[level.name] as! [String: Any]
                let plan = Tracking.videoPlan(detections, width: ref["width"] as! Int, height: ref["height"] as! Int,
                                              fps: ref["fps"] as! Double, facesExpected: true,
                                              confidence: level.confidence)
                let what = "\(name) \(level.name)"
                XCTAssertEqual(plan.extendFrames, r["extend_frames"] as? Int, what)
                XCTAssertEqual(plan.maxSimultaneous, r["max_simultaneous"] as? Int, what)
                XCTAssertEqual(plan.flags, Reference.flags(r["flags"]), what)
                let tracks = (r["tracks"] as! [[String: Any]]).map { t in
                    Track(id: t["id"] as! Int, detections: Dictionary(uniqueKeysWithValues:
                        (t["detections"] as! [[Any]]).map { ($0[0] as! Int, Reference.boxes([$0[1]])[0]) }))
                }
                XCTAssertEqual(plan.tracks, tracks, what)
                let coverage = plan.coverage()
                let refCoverage = (r["coverage"] as! [Any]).map { Reference.boxes($0) }
                for (i, boxes) in refCoverage.enumerated() {
                    XCTAssertEqual((coverage[i] ?? []).map { [$0.x, $0.y, $0.w, $0.h] },
                                   boxes.map { [$0.x, $0.y, $0.w, $0.h] }, "\(what) frame \(i)")
                }
            }
        }
    }

    /// AVFoundation's frames are FFmpeg's, but for the YUV to RGB step.
    func testDecodedFramesCloseToFFmpeg() async throws {
        for (name, ref) in videos() {
            let samples = ref["decoded_frames"] as! [String: String]
            try await VideoIn.frames(url(name)) { i, rgb, _ in
                if let png = samples[String(i)] {
                    let engine = try ImageIn.load(url: Reference.url(png)).rgb
                    let d = Pixels.diff(rgb.pixels, engine.pixels)
                    print(String(format: "  %@ frame %d: Δ mean %.2f max %d", name, i, d.mean, d.max))
                    XCTAssertLessThanOrEqual(d.mean, Pixels.decoderNoise, "\(name) frame \(i)")
                }
                return true
            }
        }
    }

    /// Decoded by AVFoundation instead of FFmpeg: the same faces in every frame,
    /// IoU >= 0.9 each (the frames differ in the YUV to RGB step, not in content).
    func testDetectionsPerFrame() async throws {
        let det = try Self.detector.get()
        for (name, ref) in videos() {
            let expected = (ref["detections"] as! [Any]).map { Reference.boxes($0) }
            var worst = 1.0, problems: [String] = []
            try await VideoIn.frames(url(name)) { i, rgb, _ in
                let m = match(expected[i], try det.detect(rgb))
                if !m.missing.isEmpty || !m.extra.isEmpty {
                    problems.append("frame \(i): -\(m.missing.map { $0.score ?? 0 }) +\(m.extra.map { $0.score ?? 0 })")
                }
                worst = min(worst, m.minIoU)
                return true
            }
            XCTAssertEqual(problems, [], name)
            XCTAssertGreaterThanOrEqual(worst, 0.9, name)
            print(String(format: "  %@: min IoU %.3f", name, worst))
        }
    }

    /// One frame by index (with the timestamps of the analysis) is the frame
    /// the full decode gives at that index.
    func testFrameByIndex() async throws {
        let name = "landscape.mp4"
        var all: [RGBImage] = [], pts: [CMTime] = []
        try await VideoIn.frames(url(name)) { _, rgb, t in all.append(rgb); pts.append(t); return true }
        for i in [0, 7, 22, all.count - 1] {
            let one = try await VideoIn.frame(url(name), at: i, pts: pts)
            XCTAssertEqual(one, all[i], "frame \(i)")
        }
    }

    /// R3 and R4 on the written file: as tests/test_video.py checks the engine's.
    func testRenderedVideoIsCleanAndCovered() async throws {
        let det = try Self.detector.get()
        let name = "phone.mov"
        guard let ref = videos().first(where: { $0.0 == name })?.1 else { return XCTFail("no \(name)") }
        let detections = (ref["detections"] as! [Any]).map { Reference.boxes($0) }
        let plan = Tracking.videoPlan(detections, width: ref["width"] as! Int, height: ref["height"] as! Int,
                                      fps: ref["fps"] as! Double, facesExpected: true,
                                      confidence: try Levels.shared.get("high").confidence)
        let coverage = plan.coverage()
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("blurrykit-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        for keep in [false, true] {
            let out = dir.appendingPathComponent(keep ? "audio.mp4" : "silent.mp4")
            let wrote = try await VideoOut.render(url(name), to: out, frameCount: plan.frameCount, keepAudio: keep) { i, rgb in
                var alpha: [UInt8]? = nil
                Redact.apply(&rgb, alpha: &alpha, boxes: coverage[i] ?? [], mode: .solid, padding: 0.25, blocks: 4)
            }
            XCTAssertEqual(wrote, keep)
            guard let info = try tool("ffprobe", ["-v", "error", "-show_format", "-show_streams", "-show_chapters",
                                                   "-of", "json", out.path]) else { continue }
            let format = info["format"] as! [String: Any]
            let tags = Set((format["tags"] as? [String: Any] ?? [:]).keys)
            XCTAssertTrue(tags.isSubset(of: ["major_brand", "minor_version", "compatible_brands"]), "\(tags)")
            XCTAssertEqual((info["chapters"] as? [Any])?.count ?? 0, 0)
            let streams = info["streams"] as! [[String: Any]]
            XCTAssertEqual(streams.map { $0["codec_type"] as! String }, keep ? ["video", "audio"] : ["video"])
            let v = streams[0]
            XCTAssertEqual(v["codec_name"] as? String, "h264")
            XCTAssertEqual(v["pix_fmt"] as? String, "yuv420p")
            XCTAssertEqual([v["width"] as? Int, v["height"] as? Int], [640, 480], "upright, no display matrix")
            XCTAssertNil(v["side_data_list"])
            for s in streams {
                let t = Set((s["tags"] as? [String: Any] ?? [:]).keys)
                XCTAssertTrue(t.isSubset(of: ["language", "handler_name", "vendor_id"]), "\(t)")
            }
            if keep {
                let a = streams[1]
                XCTAssertEqual(a["codec_name"] as? String, "aac")
                let vd = Double(v["duration"] as! String)!, ad = Double(a["duration"] as! String)!
                XCTAssertEqual(vd, 2.0, accuracy: 0.15)
                XCTAssertEqual(ad, vd, accuracy: 0.15)
            }
            if let exif = try tool("exiftool", ["-j", "-a", "-G1", "-ee", out.path], array: true) {
                let bad = exif.keys.filter { k in
                    ["gps", "location", "make", "model"].contains { k.lowercased().contains($0) }
                }
                XCTAssertEqual(bad, [])
                let dates = exif.filter { $0.key.hasSuffix("Date") && !$0.key.hasPrefix("System:") }
                XCTAssertTrue(dates.values.allSatisfy { "\($0)".hasPrefix("0000:00:00") }, "\(dates)")
            }
            // Every analysed face covered in the written frames (test_faces_covered_in_every_frame).
            var frames = 0
            try await VideoIn.frames(out) { i, rgb, _ in
                frames += 1
                if [0, 10, 20, 29].contains(i) {
                    let after = try det.detect(rgb)
                    XCTAssertGreaterThanOrEqual(detections[i].count, 7, "frame \(i)")
                    XCTAssertFalse(after.contains { a in detections[i].contains { a.iou($0) > 0.3 } }, "frame \(i)")
                }
                return true
            }
            XCTAssertEqual(frames, plan.frameCount)
        }
    }

    /// The frame count is the analysis's: one fewer analysed frame is an error,
    /// and no file is left behind.
    func testFrameCountMustMatchAnalysis() async throws {
        let out = FileManager.default.temporaryDirectory.appendingPathComponent("blurrykit-\(UUID().uuidString).mp4")
        do {
            try await VideoOut.render(url("landscape.mp4"), to: out, frameCount: 44, keepAudio: false) { _, _ in }
            XCTFail("rendered more frames than analysed")
        } catch let e as VideoOut.RenderError {
            XCTAssertEqual(e.description, "decoded more frames than were analysed")
        }
        XCTAssertFalse(FileManager.default.fileExists(atPath: out.path))
    }

    /// ffprobe or exiftool as JSON, or nil when missing (in CI, BLURRY_REQUIRE_TOOLS=1
    /// makes that a failure).
    private func tool(_ name: String, _ args: [String], array: Bool = false) throws -> [String: Any]? {
        let candidates = ["/opt/homebrew/bin/\(name)", "/usr/local/bin/\(name)", "/usr/bin/\(name)"]
        guard let path = candidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) else {
            if ProcessInfo.processInfo.environment["BLURRY_REQUIRE_TOOLS"] == "1" { XCTFail("\(name) missing") }
            return nil
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: path)
        p.arguments = args
        let pipe = Pipe()
        p.standardOutput = pipe
        try p.run()
        let data = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        let json = try JSONSerialization.jsonObject(with: data)
        return array ? (json as? [[String: Any]])?.first : json as? [String: Any]
    }
}
