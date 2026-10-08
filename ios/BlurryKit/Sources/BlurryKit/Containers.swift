import Foundation

/// The structure of JPEG, PNG and WebP files, at the level of segments and
/// chunks: what metadata an input carries, and an allowlist filter for outputs.
///
/// ImageIO writes an EXIF block (size, colour space) and an empty IPTC block
/// into every JPEG, and eXIf/sRGB chunks into every PNG, even when asked for
/// no properties. Nothing personal, but R3 means the file holds only what we
/// chose: so outputs keep only the segments and chunks needed to show the
/// pixels, and `isClean` checks it again before anything is written.
enum Containers {
    struct ContainerError: Error, Equatable, CustomStringConvertible {
        let description: String
    }

    // MARK: JPEG

    struct Segment {
        let marker: UInt8
        let range: Range<Int>     // marker included; for SOS also its scan data
        let payload: Range<Int>   // after the length field
    }

    static func isJPEG(_ d: [UInt8]) -> Bool { d.count >= 3 && d[0] == 0xFF && d[1] == 0xD8 && d[2] == 0xFF }

    static func jpegSegments(_ d: [UInt8]) throws -> [Segment] {
        guard isJPEG(d) else { throw ContainerError(description: "not a JPEG") }
        var segs = [Segment(marker: 0xD8, range: 0..<2, payload: 2..<2)]
        var i = 2
        while i < d.count {
            guard d[i] == 0xFF else { throw ContainerError(description: "JPEG: expected a marker") }
            let start = i
            while i < d.count && d[i] == 0xFF { i += 1 }   // fill bytes
            guard i < d.count else { break }
            let m = d[i]
            i += 1
            if m == 0xD9 {
                segs.append(Segment(marker: m, range: start..<i, payload: i..<i))
                return segs
            }
            if (0xD0...0xD7).contains(m) || m == 0x01 {
                segs.append(Segment(marker: m, range: start..<i, payload: i..<i))
                continue
            }
            guard i + 2 <= d.count else { throw ContainerError(description: "JPEG: truncated") }
            let len = Int(d[i]) << 8 | Int(d[i + 1])
            guard len >= 2, i + len <= d.count else { throw ContainerError(description: "JPEG: bad length") }
            var end = i + len
            let payload = (i + 2)..<end
            if m == 0xDA {
                // Entropy-coded data runs to the next marker that is not a
                // stuffed byte (FF 00) or a restart marker.
                while end + 1 < d.count {
                    if d[end] == 0xFF && d[end + 1] != 0 && !(0xD0...0xD7).contains(d[end + 1]) { break }
                    end += 1
                }
                if end + 1 >= d.count { end = d.count }
            }
            segs.append(Segment(marker: m, range: start..<end, payload: payload))
            i = end
        }
        throw ContainerError(description: "JPEG: no end of image")
    }

    /// Markers needed to decode the image: SOI, EOI, tables, frame and scan headers.
    private static func jpegNeeded(_ m: UInt8) -> Bool {
        switch m {
        case 0xD8, 0xD9, 0xDB, 0xC4, 0xCC, 0xDD, 0xDA, 0x01, 0xD0...0xD7: true
        case 0xC0...0xCF: m != 0xC8   // SOFn (C4 DHT, CC DAC above; C8 is reserved)
        default: false
        }
    }

    private static func isJFIF(_ d: [UInt8], _ s: Segment) -> Bool {
        s.marker == 0xE0 && Array(d[s.payload].prefix(5)) == Array("JFIF\0".utf8)
    }

    /// Keep what decodes the image and the JFIF header; drop APPn and COM.
    /// Any other marker is unexpected in a file ImageIO just wrote: refuse.
    static func cleanJPEG(_ d: [UInt8]) throws -> [UInt8] {
        var out: [UInt8] = []
        out.reserveCapacity(d.count)
        for s in try jpegSegments(d) {
            if jpegNeeded(s.marker) || isJFIF(d, s) {
                out += d[s.range]
            } else if (0xE0...0xEF).contains(s.marker) || s.marker == 0xFE {
                continue
            } else {
                throw ContainerError(description: String(format: "JPEG: unexpected marker %02X", s.marker))
            }
        }
        return out
    }

    // MARK: PNG

    struct Chunk {
        let type: String
        let range: Range<Int>   // length, type, data, CRC
        let data: Range<Int>
    }

    static let pngSignature: [UInt8] = [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]

    static func isPNG(_ d: [UInt8]) -> Bool { d.count >= 8 && Array(d[0..<8]) == pngSignature }

    static func pngChunks(_ d: [UInt8]) throws -> [Chunk] {
        guard isPNG(d) else { throw ContainerError(description: "not a PNG") }
        var chunks: [Chunk] = []
        var i = 8
        while i + 12 <= d.count {
            let len = Int(d[i]) << 24 | Int(d[i + 1]) << 16 | Int(d[i + 2]) << 8 | Int(d[i + 3])
            guard len >= 0, i + 12 + len <= d.count else { throw ContainerError(description: "PNG: bad length") }
            let type = String(decoding: d[(i + 4)..<(i + 8)], as: UTF8.self)
            chunks.append(Chunk(type: type, range: i..<(i + 12 + len), data: (i + 8)..<(i + 8 + len)))
            i += 12 + len
            if type == "IEND" { return chunks }
        }
        throw ContainerError(description: "PNG: no IEND")
    }

    private static let pngKept: Set<String> = ["IHDR", "PLTE", "tRNS", "IDAT", "IEND"]

    /// Keep the critical chunks and transparency; drop every other ancillary
    /// chunk (text, eXIf, iCCP, sRGB, gAMA, pHYs, tIME...). An unknown
    /// critical chunk is unexpected: refuse.
    static func cleanPNG(_ d: [UInt8]) throws -> [UInt8] {
        var out = pngSignature
        out.reserveCapacity(d.count)
        for c in try pngChunks(d) {
            if pngKept.contains(c.type) {
                out += d[c.range]
            } else if c.type.first?.isLowercase != true {
                throw ContainerError(description: "PNG: unexpected critical chunk \(c.type)")
            }
        }
        return out
    }

    /// The final check before writing: only allowed segments or chunks remain.
    static func isClean(_ d: [UInt8]) -> Bool {
        if isJPEG(d) {
            guard let segs = try? jpegSegments(d) else { return false }
            return segs.allSatisfy { jpegNeeded($0.marker) || isJFIF(d, $0) }
        }
        if isPNG(d) {
            guard let chunks = try? pngChunks(d) else { return false }
            return chunks.allSatisfy { pngKept.contains($0.type) }
        }
        return false
    }

    // MARK: Metadata in inputs (names as image_io._metadata_found)

    /// Whether a TIFF-structured EXIF block has a second IFD (IFD1), which holds
    /// the thumbnail: Pillow's exif.get_ifd(IFD1). Accepts an "Exif\0\0" prefix.
    static func exifHasThumbnailIFD(_ block: ArraySlice<UInt8>) -> Bool {
        var t = Array(block)
        if t.starts(with: Array("Exif\0\0".utf8)) { t.removeFirst(6) }
        guard t.count >= 8 else { return false }
        let little = t[0] == 0x49 && t[1] == 0x49
        guard little || (t[0] == 0x4D && t[1] == 0x4D) else { return false }
        func u16(_ i: Int) -> Int? {
            guard i >= 0, i + 2 <= t.count else { return nil }
            return little ? Int(t[i]) | Int(t[i + 1]) << 8 : Int(t[i]) << 8 | Int(t[i + 1])
        }
        func u32(_ i: Int) -> Int? {
            guard let a = u16(i), let b = u16(i + 2) else { return nil }
            return little ? a | b << 16 : a << 16 | b
        }
        guard let ifd0 = u32(4), let n0 = u16(ifd0),
              let ifd1 = u32(ifd0 + 2 + 12 * n0), ifd1 != 0, let n1 = u16(ifd1) else { return false }
        return n1 > 0
    }

    static func jpegMetadata(_ d: [UInt8]) -> Set<String> {
        var found: Set<String> = []
        guard let segs = try? jpegSegments(d) else { return found }
        for s in segs {
            let p = d[s.payload]
            switch s.marker {
            case 0xE1 where p.starts(with: Array("Exif\0".utf8)):
                found.insert("exif")
                if exifHasThumbnailIFD(p) { found.insert("exif_thumbnail") }
            case 0xE1 where p.starts(with: Array("http://ns.adobe.com/xap/1.0/\0".utf8)): found.insert("xmp")
            case 0xED: found.insert("iptc")
            case 0xE2 where p.starts(with: Array("ICC_PROFILE\0".utf8)): found.insert("icc_profile")
            case 0xFE: found.insert("comment")
            default: break
            }
        }
        return found
    }

    static func pngMetadata(_ d: [UInt8]) -> Set<String> {
        var found: Set<String> = []
        guard let chunks = try? pngChunks(d) else { return found }
        for c in chunks {
            switch c.type {
            case "eXIf":
                found.insert("exif")
                if exifHasThumbnailIFD(d[c.data]) { found.insert("exif_thumbnail") }
            case "iCCP": found.insert("icc_profile")
            case "tEXt", "zTXt", "iTXt":
                found.insert("text_chunks")
                if d[c.data].starts(with: Array("XML:com.adobe.xmp\0".utf8)) { found.insert("xmp") }
            default: break
            }
        }
        return found
    }

    static func isWebP(_ d: [UInt8]) -> Bool {
        d.count >= 12 && Array(d[0..<4]) == Array("RIFF".utf8) && Array(d[8..<12]) == Array("WEBP".utf8)
    }

    static func webpMetadata(_ d: [UInt8]) -> Set<String> {
        var found: Set<String> = []
        guard isWebP(d) else { return found }
        var i = 12
        while i + 8 <= d.count {
            let fourcc = String(decoding: d[i..<(i + 4)], as: UTF8.self)
            let len = Int(d[i + 4]) | Int(d[i + 5]) << 8 | Int(d[i + 6]) << 16 | Int(d[i + 7]) << 24
            switch fourcc {
            case "EXIF":
                found.insert("exif")
                if exifHasThumbnailIFD(d[(i + 8)..<min(d.count, i + 8 + len)]) { found.insert("exif_thumbnail") }
            case "XMP ": found.insert("xmp")
            case "ICCP": found.insert("icc_profile")
            default: break
            }
            i += 8 + len + (len & 1)
        }
        return found
    }

    // MARK: HEIF (ISO BMFF)

    struct BMFFBox {
        let type: String
        let body: Range<Int>   // after the header
    }

    static func bmffBoxes(_ d: [UInt8], in range: Range<Int>) -> [BMFFBox] {
        var boxes: [BMFFBox] = []
        var i = range.lowerBound
        while i + 8 <= range.upperBound {
            var size = Int(d[i]) << 24 | Int(d[i + 1]) << 16 | Int(d[i + 2]) << 8 | Int(d[i + 3])
            let type = String(decoding: d[(i + 4)..<(i + 8)], as: UTF8.self)
            var header = 8
            if size == 1 {
                guard i + 16 <= range.upperBound else { break }
                size = d[(i + 8)..<(i + 16)].reduce(0) { $0 << 8 | Int($1) }
                header = 16
            } else if size == 0 {
                size = range.upperBound - i
            }
            guard size >= header, i + size <= range.upperBound else { break }
            boxes.append(BMFFBox(type: type, body: (i + header)..<(i + size)))
            i += size
        }
        return boxes
    }

    private static func cString(_ d: [UInt8], from i: inout Int, to end: Int) -> String {
        let start = i
        while i < end && d[i] != 0 { i += 1 }
        defer { i += 1 }
        return String(decoding: d[start..<i], as: UTF8.self)
    }

    /// Exif and XMP items, colour profiles and thumbnails in the meta box.
    /// GPS and depth come from ImageIO (see ImageIn).
    static func heifMetadata(_ d: [UInt8]) -> Set<String> {
        var found: Set<String> = []
        guard let meta = bmffBoxes(d, in: 0..<d.count).first(where: { $0.type == "meta" }),
              meta.body.count > 4 else { return found }
        let inner = bmffBoxes(d, in: (meta.body.lowerBound + 4)..<meta.body.upperBound)   // FullBox
        for box in inner {
            switch box.type {
            case "iinf":
                guard box.body.count > 6 else { continue }
                let version = d[box.body.lowerBound]
                let first = box.body.lowerBound + 4 + (version == 0 ? 2 : 4)
                for infe in bmffBoxes(d, in: first..<box.body.upperBound) where infe.type == "infe" {
                    let v = d[infe.body.lowerBound]
                    guard v >= 2 else { continue }
                    var i = infe.body.lowerBound + 4 + (v == 2 ? 2 : 4) + 2
                    guard i + 4 <= infe.body.upperBound else { continue }
                    let itemType = String(decoding: d[i..<(i + 4)], as: UTF8.self)
                    i += 4
                    _ = cString(d, from: &i, to: infe.body.upperBound)   // item name
                    if itemType == "Exif" { found.insert("exif") }
                    if itemType == "mime",
                       cString(d, from: &i, to: infe.body.upperBound) == "application/rdf+xml" {
                        found.insert("xmp")
                    }
                }
            case "iprp":
                for ipco in bmffBoxes(d, in: box.body) where ipco.type == "ipco" {
                    for colr in bmffBoxes(d, in: ipco.body) where colr.type == "colr" && colr.body.count >= 4 {
                        let kind = String(decoding: d[colr.body.prefix(4)], as: UTF8.self)
                        if kind == "prof" || kind == "rICC" { found.insert("icc_profile") }
                    }
                }
            case "iref":
                let refs = bmffBoxes(d, in: (box.body.lowerBound + 4)..<box.body.upperBound)
                if refs.contains(where: { $0.type == "thmb" }) { found.insert("embedded_thumbnails") }
            default:
                break
            }
        }
        return found
    }

    // MARK: MOV / MP4

    /// The moov box of a file that can be gigabytes long: walk the top-level
    /// box headers and read only moov (capped at 256 MB).
    static func moovBytes(_ url: URL) -> [UInt8]? { moovLocation(url)?.1 }

    /// Tags as FFmpeg names them, for the rules of video_io._metadata_found.
    private static let udtaNames: [String: String] = [
        "\u{A9}xyz": "location", "loci": "location", "\u{A9}day": "date", "\u{A9}nam": "title",
        "\u{A9}too": "encoder", "\u{A9}mak": "make", "\u{A9}mod": "model", "\u{A9}cmt": "comment",
        "\u{A9}ART": "artist", "\u{A9}alb": "album", "\u{A9}swr": "encoder", "\u{A9}des": "description",
    ]
    /// Container tags that describe the file format itself, not the recording.
    private static let technicalTags: Set<String> = [
        "major_brand", "minor_version", "compatible_brands", "handler_name", "vendor_id", "language",
        "duration", "encoder",
    ]

    /// video_io._metadata_found from the file's boxes (AVFoundation hides the
    /// names of FFmpeg-written keys). Rotation is added by VideoIn.probe.
    static func movMetadata(_ url: URL) -> Set<String> {
        guard let d = moovBytes(url) else { return [] }
        var found: Set<String> = []
        var tags: [String] = []
        let moov = bmffBoxes(d, in: 8..<d.count)
        func latin(_ r: Range<Int>) -> String { String(bytes: d[r], encoding: .isoLatin1) ?? "" }

        // ilst under a meta box: with a keys box, items are numbered keys;
        // without, they are four-character codes.
        func readMeta(_ meta: BMFFBox, fullBox: Bool) {
            let inner = bmffBoxes(d, in: (meta.body.lowerBound + (fullBox ? 4 : 0))..<meta.body.upperBound)
            var keys: [String] = []
            if let k = inner.first(where: { $0.type == "keys" }) {
                var i = k.body.lowerBound + 8
                while i + 8 <= k.body.upperBound {
                    let size = Int(d[i]) << 24 | Int(d[i + 1]) << 16 | Int(d[i + 2]) << 8 | Int(d[i + 3])
                    guard size >= 8, i + size <= k.body.upperBound else { break }
                    keys.append(String(decoding: d[(i + 8)..<(i + size)], as: UTF8.self))
                    i += size
                }
            }
            for ilst in inner where ilst.type == "ilst" {
                for item in bmffBoxes(d, in: ilst.body) {
                    let code = latin(item.range4(d))
                    if !keys.isEmpty, let n = item.index(d), n >= 1, n <= keys.count {
                        tags.append(keys[n - 1])
                    } else if code == "covr" {
                        tags.append("cover")
                    } else {
                        tags.append(udtaNames[code] ?? code)
                    }
                }
            }
        }

        for box in moov {
            switch box.type {
            case "mvhd":
                // FFmpeg turns a non-zero creation time into a creation_time tag.
                let v = d[box.body.lowerBound]
                let start = box.body.lowerBound + 4
                let n = v == 1 ? 8 : 4
                if start + n <= box.body.upperBound, d[start..<(start + n)].contains(where: { $0 != 0 }) {
                    tags.append("creation_time")
                }
            case "udta":
                for child in bmffBoxes(d, in: box.body) {
                    let code = latin(child.body.lowerBound - 4..<child.body.lowerBound)
                    switch code {
                    case "chpl": found.insert("chapters")
                    case "meta": readMeta(child, fullBox: true)
                    default:
                        if let name = udtaNames[code] { tags.append(name) } else if code.hasPrefix("\u{A9}") { tags.append(code) }
                    }
                }
            case "meta":
                readMeta(box, fullBox: false)
            default:
                break
            }
        }

        var videoTracks = 0, audioTracks = 0
        var chapterTracks: Set<Int> = []
        var trackKinds: [(id: Int, handler: String)] = []
        for trak in moov where trak.type == "trak" {
            let parts = bmffBoxes(d, in: trak.body)
            var id = 0
            if let tkhd = parts.first(where: { $0.type == "tkhd" }) {
                let v = d[tkhd.body.lowerBound]
                let at = tkhd.body.lowerBound + 4 + (v == 1 ? 16 : 8)
                if at + 4 <= tkhd.body.upperBound {
                    id = Int(d[at]) << 24 | Int(d[at + 1]) << 16 | Int(d[at + 2]) << 8 | Int(d[at + 3])
                }
            }
            if let tref = parts.first(where: { $0.type == "tref" }) {
                for ref in bmffBoxes(d, in: tref.body) where ref.type == "chap" {
                    var i = ref.body.lowerBound
                    while i + 4 <= ref.body.upperBound {
                        chapterTracks.insert(Int(d[i]) << 24 | Int(d[i + 1]) << 16 | Int(d[i + 2]) << 8 | Int(d[i + 3]))
                        i += 4
                    }
                }
            }
            if let udta = parts.first(where: { $0.type == "udta" }), !bmffBoxes(d, in: udta.body).isEmpty {
                found.insert("track_tags")
            }
            if let mdia = parts.first(where: { $0.type == "mdia" }),
               let hdlr = bmffBoxes(d, in: mdia.body).first(where: { $0.type == "hdlr" }),
               hdlr.body.count >= 12 {
                let handler = latin((hdlr.body.lowerBound + 8)..<(hdlr.body.lowerBound + 12))
                trackKinds.append((id, handler))
            }
        }
        for (id, handler) in trackKinds {
            switch handler {
            case "vide": videoTracks += 1
            case "soun": audioTracks += 1
            case "text", "sbtl", "subt", "clcp":
                // A track that holds chapter titles is not a subtitle track for FFmpeg.
                if chapterTracks.contains(id) { found.insert("chapters") } else { found.insert("subtitle_track") }
            case "tmcd", "meta", "data", "gpmd", "camm":
                found.insert("data_track")
            default:
                break
            }
        }
        if videoTracks > 1 { found.insert("extra_video_track") }
        if audioTracks > 1 { found.insert("extra_audio_track") }

        for tag in tags {
            let k = tag.lowercased()
            if k == "cover" { found.insert("cover_art"); continue }
            if !technicalTags.contains(k) { found.insert("container_tags") }
            if k.contains("location") || k == "com.apple.quicktime.location.iso6709" || k == "gps" {
                found.insert("location")
            }
            if k.contains("creation_time") || k == "date" { found.insert("creation_time") }
            if k.hasPrefix("com.apple.quicktime.") && (k.contains("make") || k.contains("model")) {
                found.insert("device")
            }
        }
        return found
    }
}

extension Containers {
    /// The writer's own traces in a video Blurry just wrote, checked and removed.
    ///
    /// AVAssetWriter stamps the export time as creation and modification time
    /// in mvhd, tkhd and mdhd (VERIFICA 5c, 2026-10-07): not when the video was
    /// shot, but still when it was prepared. Those fields are zeroed in place,
    /// so no offset moves. Then the structure is checked: only video and audio
    /// tracks, at most two, and no udta, meta or tref anywhere; anything else
    /// fails the export rather than leave a trace.
    static func cleanMovie(_ url: URL) throws {
        guard let (offset, d) = moovLocation(url) else { throw ContainerError(description: "MP4: no moov") }
        var zero: [Range<Int>] = []   // byte ranges inside moov
        let allowedTop: Set<String> = ["mvhd", "trak", "iods"]
        let allowedTrak: Set<String> = ["tkhd", "edts", "mdia"]
        func times(_ box: BMFFBox) {
            let v = d[box.body.lowerBound]
            let n = v == 1 ? 8 : 4
            let start = box.body.lowerBound + 4
            if start + 2 * n <= box.body.upperBound { zero.append(start..<(start + 2 * n)) }
        }
        let top = bmffBoxes(d, in: 8..<d.count)
        var tracks = 0
        for box in top {
            guard allowedTop.contains(box.type) else { throw ContainerError(description: "MP4: unexpected \(box.type)") }
            if box.type == "mvhd" { times(box) }
            guard box.type == "trak" else { continue }
            tracks += 1
            for part in bmffBoxes(d, in: box.body) {
                guard allowedTrak.contains(part.type) else {
                    throw ContainerError(description: "MP4: unexpected \(part.type) in a track")
                }
                if part.type == "tkhd" { times(part) }
                guard part.type == "mdia" else { continue }
                for m in bmffBoxes(d, in: part.body) {
                    if m.type == "mdhd" { times(m) }
                    if m.type == "hdlr", m.body.count >= 12 {
                        let handler = String(bytes: d[(m.body.lowerBound + 8)..<(m.body.lowerBound + 12)], encoding: .isoLatin1)
                        guard handler == "vide" || handler == "soun" else {
                            throw ContainerError(description: "MP4: unexpected track \(handler ?? "?")")
                        }
                    }
                    if m.type == "udta" || m.type == "meta" { throw ContainerError(description: "MP4: metadata in a track") }
                }
            }
        }
        guard tracks >= 1 && tracks <= 2 else { throw ContainerError(description: "MP4: \(tracks) tracks") }
        let fh = try FileHandle(forUpdating: url)
        defer { try? fh.close() }
        for r in zero {
            try fh.seek(toOffset: offset + UInt64(r.lowerBound))
            try fh.write(contentsOf: Data(count: r.count))
        }
        try fh.synchronize()
    }

    /// Where moov starts in the file, and its bytes.
    static func moovLocation(_ url: URL) -> (UInt64, [UInt8])? {
        guard let fh = try? FileHandle(forReadingFrom: url) else { return nil }
        defer { try? fh.close() }
        var offset: UInt64 = 0
        while true {
            guard (try? fh.seek(toOffset: offset)) != nil,
                  let head = try? fh.read(upToCount: 16), head.count >= 8 else { return nil }
            let h = [UInt8](head)
            var size = UInt64(h[0]) << 24 | UInt64(h[1]) << 16 | UInt64(h[2]) << 8 | UInt64(h[3])
            if size == 1, h.count >= 16 { size = h[8..<16].reduce(0) { $0 << 8 | UInt64($1) } }
            guard size >= 8 else { return nil }
            if String(decoding: h[4..<8], as: UTF8.self) == "moov" {
                guard size <= 256 * 1024 * 1024, (try? fh.seek(toOffset: offset)) != nil,
                      let data = try? fh.read(upToCount: Int(size)) else { return nil }
                return (offset, [UInt8](data))
            }
            offset += size
        }
    }
}

private extension Containers.BMFFBox {
    /// The four bytes of the box type, just before its body.
    func range4(_ d: [UInt8]) -> Range<Int> { (body.lowerBound - 4)..<body.lowerBound }

    /// An ilst item whose type is a number: the index into the keys box.
    func index(_ d: [UInt8]) -> Int? {
        let r = range4(d)
        let n = Int(d[r.lowerBound]) << 24 | Int(d[r.lowerBound + 1]) << 16 | Int(d[r.lowerBound + 2]) << 8
            | Int(d[r.lowerBound + 3])
        return n > 0 && n < 0x10000 ? n : nil
    }
}

