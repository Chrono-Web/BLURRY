import XCTest
@testable import BlurryKit

/// PIANO_BLURRY 5a, test (d) and the R3/R5/R6 rules on images.
final class ImageTests: XCTestCase {
    /// Keys that must never survive, as tests/test_image.py.
    static let privateKeys = ["GPS", "XMP", "IPTC", "ICC", "Thumbnail", "Orientation", "Make", "Model",
                              "DateTimeOriginal", "Creator", "Comment", "Description", "Copyright"]

    /// Reading the extra files (orientation, colour profiles, alpha, refusals)
    /// gives what image_io.load gives.
    func testReadingLikeEngine() throws {
        let extra = Reference.extra()
        XCTAssertFalse(extra.isEmpty)
        for (name, ref) in extra {
            let url = Reference.url("extra/\(name)")
            if let message = ref["error"] as? String {
                XCTAssertThrowsError(try ImageIn.load(url: url), name) { error in
                    XCTAssertEqual((error as? InputError)?.description, message, name)
                }
                continue
            }
            let loaded = try ImageIn.load(url: url)
            XCTAssertEqual(loaded.rgb.width, ref["width"] as? Int, name)
            XCTAssertEqual(loaded.rgb.height, ref["height"] as? Int, name)
            XCTAssertEqual(loaded.outFormat.rawValue, ref["out_format"] as? String, name)
            XCTAssertEqual(loaded.alpha != nil, ref["has_alpha"] as? Bool, name)
            XCTAssertEqual(loaded.metadataFound, ref["metadata_found"] as? [String], name)

            let engine = try ImageIn.load(url: Reference.url(ref["decoded"] as! String))
            if let a = loaded.alpha, let b = engine.alpha {
                XCTAssertEqual(a, b, "\(name): alpha")
                // Under transparent pixels the colour is invisible and may differ.
                let d = Pixels.diff(loaded.rgb.pixels, engine.rgb.pixels, mask: { a[$0 / 3] == 255 })
                XCTAssertLessThanOrEqual(d.mean, Pixels.decoderNoise, "\(name): Δ mean \(d.mean)")
            } else {
                let d = Pixels.diff(loaded.rgb.pixels, engine.rgb.pixels)
                XCTAssertLessThanOrEqual(d.mean, Pixels.decoderNoise, "\(name): Δ mean \(d.mean)")
                print(String(format: "  %@: pixels Δ mean %.2f max %d", name, d.mean, d.max))
            }
        }
    }

    /// R3: written files hold the pixels and nothing else, checked by our own
    /// parser and, when available, by exiftool.
    func testOutputsHoldNoMetadata() throws {
        let sources = [Reference.url("extra/poisoned.jpg"), Reference.url("extra/alpha_text.png"),
                       Reference.root.appendingPathComponent("tests/fixtures/public/sts125_gps.heic")]
        let dir = FileManager.default.temporaryDirectory.appendingPathComponent("blurrykit-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        for src in sources {
            let loaded = try ImageIn.load(url: src)
            let data = try ImageOut.encode(loaded.rgb, alpha: loaded.alpha, format: loaded.outFormat)
            XCTAssertTrue(Containers.isClean([UInt8](data)), src.lastPathComponent)
            let out = dir.appendingPathComponent("out.\(loaded.outFormat.ext)")
            try data.write(to: out)

            let back = try ImageIn.load(url: out)
            XCTAssertEqual(back.metadataFound, [], src.lastPathComponent)
            XCTAssertEqual(back.rgb.width, loaded.rgb.width)
            XCTAssertEqual(back.rgb.height, loaded.rgb.height)
            XCTAssertEqual(back.alpha, loaded.alpha, "alpha survives in PNG")
            XCTAssertLessThanOrEqual(Pixels.diff(back.rgb.pixels, loaded.rgb.pixels).mean, 3.0)

            guard let tags = try exiftool(out) else { continue }
            let leaked = tags.keys.filter { k in Self.privateKeys.contains { k.lowercased().contains($0.lowercased()) } }
            XCTAssertEqual(leaked, [], src.lastPathComponent)
        }
    }

    /// The allowlist filter on a file full of metadata.
    func testCleanJPEGDropsEveryAppSegment() throws {
        let bytes = [UInt8](try Data(contentsOf: Reference.url("extra/poisoned.jpg")))
        XCTAssertFalse(Containers.isClean(bytes))
        let clean = try Containers.cleanJPEG(bytes)
        XCTAssertTrue(Containers.isClean(clean))
        XCTAssertEqual(Containers.jpegMetadata(clean), [])
        XCTAssertNoThrow(try ImageIn.load(data: Data(clean), fileExtension: "jpg"))
    }

    func testCleanPNGDropsAncillaryChunks() throws {
        let bytes = [UInt8](try Data(contentsOf: Reference.url("extra/alpha_text.png")))
        XCTAssertEqual(Containers.pngMetadata(bytes), ["text_chunks"])
        let clean = try Containers.cleanPNG(bytes)
        XCTAssertTrue(Containers.isClean(clean))
        XCTAssertEqual(try Containers.pngChunks(clean).map(\.type).filter { $0 != "IDAT" }, ["IHDR", "IEND"])
    }

    /// R5: the pinned hash matches the bundled model, and any change is refused.
    func testModelHash() throws {
        let url = try XCTUnwrap(Model.url)
        XCTAssertEqual(try Model.folderHash(url), Model.sha256)
        let copy = FileManager.default.temporaryDirectory.appendingPathComponent("yunet-\(UUID().uuidString).mlmodelc")
        try FileManager.default.copyItem(at: url, to: copy)
        defer { try? FileManager.default.removeItem(at: copy) }
        let weights = copy.appendingPathComponent("weights/weight.bin")
        var data = try Data(contentsOf: weights)
        data[data.count / 2] ^= 1
        try data.write(to: weights)
        XCTAssertNotEqual(try Model.folderHash(copy), Model.sha256)
    }

    func testRefusals() {
        XCTAssertThrowsError(try ImageIn.load(data: Data("x".utf8), fileExtension: "gif")) {
            XCTAssertEqual(($0 as? InputError)?.description, "unsupported image type (accepted: JPEG, PNG, WebP, HEIC)")
        }
        XCTAssertThrowsError(try ImageIn.load(data: Data(), fileExtension: "jpg")) {
            XCTAssertEqual(($0 as? InputError)?.description, "empty file")
        }
    }

    /// exiftool -j -a -G1 without the groups that describe the file itself, or
    /// nil when it is missing (in CI, BLURRY_REQUIRE_TOOLS=1 makes that a failure).
    private func exiftool(_ url: URL) throws -> [String: Any]? {
        let candidates = ["/opt/homebrew/bin/exiftool", "/usr/local/bin/exiftool", "/usr/bin/exiftool"]
        guard let tool = candidates.first(where: { FileManager.default.isExecutableFile(atPath: $0) }) else {
            if ProcessInfo.processInfo.environment["BLURRY_REQUIRE_TOOLS"] == "1" { XCTFail("exiftool missing") }
            return nil
        }
        let p = Process()
        p.executableURL = URL(fileURLWithPath: tool)
        p.arguments = ["-j", "-a", "-G1", url.path]
        let pipe = Pipe()
        p.standardOutput = pipe
        try p.run()
        let out = pipe.fileHandleForReading.readDataToEndOfFile()
        p.waitUntilExit()
        let all = (try JSONSerialization.jsonObject(with: out) as? [[String: Any]])?.first ?? [:]
        return all.filter { !$0.key.hasPrefix("System:") && !$0.key.hasPrefix("ExifTool:") && $0.key != "SourceFile" }
    }
}
