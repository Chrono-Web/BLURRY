import AVFoundation
import VideoToolbox
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

    /// On the frames FFmpeg decoded for the engine: identical boxes, as for
    /// photos (ParityTests, test a).
    func testDetectionIdenticalOnEngineFrames() throws {
        let det = try Self.detector.get()
        for (name, ref) in videos() {
            let expected = (ref["detections"] as! [Any]).map { Reference.boxes($0) }
            for (i, png) in ref["decoded_frames"] as! [String: String] {
                let rgb = try ImageIn.load(url: Reference.url(png)).rgb
                assertSame(try det.detect(rgb), expected[Int(i)!], "\(name) frame \(i)")
            }
        }
    }

    /// Decoded by AVFoundation instead of FFmpeg: the same faces in every frame,
    /// IoU >= 0.8 each. The frames differ by one level here and there (YUV to
    /// RGB), and on the faces of these videos (45 pixels) that moves a box by
    /// up to 3 pixels, IoU 0.85; a face scoring within `margin` of the
    /// threshold may also come in or go out. The test videos are encoded by the
    /// FFmpeg of the machine, so where this happens changes with its version.
    /// On identical pixels the boxes are identical (the test above).
    func testDetectionsPerFrame() async throws {
        let det = try Self.detector.get()
        let threshold = try Levels.shared.get(Levels.shared.mostSensitive).confidence
        let margin = 0.05
        func firm(_ b: Box) -> Bool { (b.score ?? 0) >= threshold + margin }
        for (name, ref) in videos() {
            let expected = (ref["detections"] as! [Any]).map { Reference.boxes($0) }
            var worst = 1.0, worstAny = 1.0, near = 0, problems: [String] = [], worstCase = ""
            try await VideoIn.frames(url(name)) { i, rgb, _ in
                let got = try det.detect(rgb)
                let m = match(expected[i], got)
                let missing = m.missing.filter(firm), extra = m.extra.filter(firm)
                if !missing.isEmpty || !extra.isEmpty {
                    problems.append("frame \(i): -\(missing.map { $0.score ?? 0 }) +\(extra.map { $0.score ?? 0 })")
                }
                near += m.missing.count - missing.count + m.extra.count - extra.count
                for r in expected[i] {
                    guard let best = got.map({ r.iou($0) }).max(), best >= 0.5 else { continue }
                    worstAny = min(worstAny, best)
                    if firm(r), best < worst {
                        worst = best
                        let g = got.max { r.iou($0) < r.iou($1) }!
                        worstCase = "frame \(i): \([r.x, r.y, r.w, r.h]) \(r.score ?? 0) -> \([g.x, g.y, g.w, g.h]) \(g.score ?? 0)"
                    }
                }
                return true
            }
            XCTAssertEqual(problems, [], name)
            XCTAssertGreaterThanOrEqual(worst, 0.8, "\(name) \(worstCase)")
            print(String(format: "  %@: min IoU %.3f (%.3f with the faces near the threshold), %d near the threshold differ",
                         name, worst, worstAny, near), worstCase)
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

/// HDR as the iPhone records it (HEVC 10 bit, HLG, BT.2020) comes out as Apple
/// shows it in SDR: not washed out (read as 8-bit BT.601), not blown out (HLG
/// 75 % as white). Field tests of 2026-10-08.
final class HDRVideoTests: XCTestCase {
    func testHLGReadsAsSDR() async throws {
        let source = try ImageIn.load(url: Reference.url("decoded/video-landscape.mp4-0.png")).rgb
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("blurrykit-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let url = dir.appendingPathComponent("hlg.mov")
        try await Self.writeHLG(source, frames: 5, to: url)

        let info = try await VideoIn.probe(url)
        XCTAssertEqual([info.width, info.height], [source.width, source.height])
        var read: RGBImage?
        try await VideoIn.frames(url) { _, rgb, _ in read = rgb; return false }
        let got = try XCTUnwrap(read)
        let apple = try await Self.appleSDR(url)
        let d = Pixels.diff(got.pixels, apple.pixels)
        let (sg, sa) = (Self.saturation(got), Self.saturation(apple))
        let (lg, la) = (Self.lightness(got), Self.lightness(apple))
        print(String(format: "  HLG against Apple's SDR: Δ mean %.2f, saturation %.1f (%.1f), lightness %.1f (%.1f)",
                     d.mean, sg, sa, lg, la))
        XCTAssertLessThan(d.mean, 8)   // 6.4 here: a power curve, not Apple's exact one
        XCTAssertEqual(sg, sa, accuracy: sa * 0.15)
        XCTAssertEqual(lg, la, accuracy: 8)
    }

    /// The first frame as AVFoundation converts it to BT.709 SDR itself.
    static func appleSDR(_ url: URL) async throws -> RGBImage {
        let asset = AVURLAsset(url: url)
        let tracks = try await asset.loadTracks(withMediaType: .video)
        let track = try XCTUnwrap(tracks.first)
        let reader = try AVAssetReader(asset: asset)
        let output = AVAssetReaderTrackOutput(track: track, outputSettings: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
            AVVideoColorPropertiesKey: [
                AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
                AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
                AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2,
            ],
        ])
        reader.add(output)
        reader.startReading()
        let sample = try XCTUnwrap(output.copyNextSampleBuffer())
        let pb = try XCTUnwrap(CMSampleBufferGetImageBuffer(sample))
        CVPixelBufferLockBaseAddress(pb, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pb, .readOnly) }
        let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb), row = CVPixelBufferGetBytesPerRow(pb)
        let base = CVPixelBufferGetBaseAddress(pb)!.assumingMemoryBound(to: UInt8.self)
        var px = [UInt8](repeating: 0, count: w * h * 3)
        for y in 0..<h {
            for x in 0..<w {
                let s = y * row + x * 4, d = (y * w + x) * 3
                px[d] = base[s + 2]; px[d + 1] = base[s + 1]; px[d + 2] = base[s]
            }
        }
        reader.cancelReading()
        return RGBImage(width: w, height: h, pixels: px)
    }

    static func lightness(_ img: RGBImage) -> Double {
        Double(img.pixels.reduce(0) { $0 + Int($1) }) / Double(img.pixels.count)
    }

    /// The clean file is SDR, tagged BT.709, and shows the picture read.
    func testHLGRendersAsSDR() async throws {
        let source = try ImageIn.load(url: Reference.url("decoded/video-landscape.mp4-0.png")).rgb
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("blurrykit-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let hlg = dir.appendingPathComponent("hlg.mov"), out = dir.appendingPathComponent("out.mp4")
        try await Self.writeHLG(source, frames: 5, to: hlg)
        _ = try await VideoOut.render(hlg, to: out, frameCount: 5, keepAudio: false) { _, _ in }

        let tracks = try await AVURLAsset(url: out).loadTracks(withMediaType: .video)
        let track = try XCTUnwrap(tracks.first)
        let formats = try await track.load(.formatDescriptions)
        let format = try XCTUnwrap(formats.first)
        func ext(_ key: CFString) -> String? { CMFormatDescriptionGetExtension(format, extensionKey: key) as? String }
        print("  rendered tags:", ext(kCMFormatDescriptionExtension_ColorPrimaries) ?? "-",
              ext(kCMFormatDescriptionExtension_TransferFunction) ?? "-",
              ext(kCMFormatDescriptionExtension_YCbCrMatrix) ?? "-")
        XCTAssertEqual(ext(kCMFormatDescriptionExtension_ColorPrimaries), kCMFormatDescriptionColorPrimaries_ITU_R_709_2 as String)
        XCTAssertEqual(ext(kCMFormatDescriptionExtension_TransferFunction), kCMFormatDescriptionTransferFunction_ITU_R_709_2 as String)
        XCTAssertEqual(ext(kCMFormatDescriptionExtension_YCbCrMatrix), kCMFormatDescriptionYCbCrMatrix_ITU_R_709_2 as String)

        var read: RGBImage?, written: RGBImage?
        try await VideoIn.frames(hlg) { _, rgb, _ in read = rgb; return false }
        try await VideoIn.frames(out) { _, rgb, _ in written = rgb; return false }
        let d = Pixels.diff(try XCTUnwrap(written).pixels, try XCTUnwrap(read).pixels)
        print(String(format: "  rendered HLG against the frame read: Δ mean %.2f", d.mean))
        XCTAssertLessThan(d.mean, 4)   // H.264 at the export bit rate
    }

    /// Mean of max(R,G,B) - min(R,G,B).
    static func saturation(_ img: RGBImage) -> Double {
        var total = 0
        for i in stride(from: 0, to: img.pixels.count, by: 3) {
            let p = img.pixels[i..<i + 3]
            total += Int(p.max()!) - Int(p.min()!)
        }
        return Double(total) / Double(img.pixels.count / 3)
    }

    static func writeHLG(_ img: RGBImage, frames: Int, to url: URL) async throws {
        let writer = try AVAssetWriter(outputURL: url, fileType: .mov)
        let input = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.hevc,
            AVVideoWidthKey: img.width, AVVideoHeightKey: img.height,
            AVVideoColorPropertiesKey: [
                AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_2020,
                AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_2100_HLG,
                AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_2020,
            ],
            AVVideoCompressionPropertiesKey: [
                AVVideoProfileLevelKey: kVTProfileLevel_HEVC_Main10_AutoLevel as String,
            ],
        ])
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: input, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
            kCVPixelBufferWidthKey as String: img.width, kCVPixelBufferHeightKey as String: img.height,
        ])
        writer.add(input)
        guard writer.startWriting() else { throw XCTSkip("no HEVC 10-bit encoder here: \(String(describing: writer.error))") }
        writer.startSession(atSourceTime: .zero)
        for i in 0..<frames {
            var pb: CVPixelBuffer?
            CVPixelBufferPoolCreatePixelBuffer(nil, adaptor.pixelBufferPool!, &pb)
            let buffer = pb!
            CVBufferSetAttachment(buffer, kCVImageBufferColorPrimariesKey, kCVImageBufferColorPrimaries_ITU_R_709_2, .shouldPropagate)
            CVBufferSetAttachment(buffer, kCVImageBufferTransferFunctionKey, kCVImageBufferTransferFunction_sRGB, .shouldPropagate)
            CVPixelBufferLockBaseAddress(buffer, [])
            let row = CVPixelBufferGetBytesPerRow(buffer)
            let base = CVPixelBufferGetBaseAddress(buffer)!.assumingMemoryBound(to: UInt8.self)
            for y in 0..<img.height {
                for x in 0..<img.width {
                    let s = (y * img.width + x) * 3, d = y * row + x * 4
                    base[d] = img.pixels[s + 2]; base[d + 1] = img.pixels[s + 1]
                    base[d + 2] = img.pixels[s]; base[d + 3] = 255
                }
            }
            CVPixelBufferUnlockBaseAddress(buffer, [])
            while !input.isReadyForMoreMediaData { try await Task.sleep(nanoseconds: 1_000_000) }
            adaptor.append(buffer, withPresentationTime: CMTime(value: CMTimeValue(i), timescale: 15))
        }
        input.markAsFinished()
        await writer.finishWriting()
        if writer.status != .completed { throw XCTSkip("HEVC 10 bit not written here: \(String(describing: writer.error))") }
    }
}
