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
}
