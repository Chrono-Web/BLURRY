import Accelerate
import CoreGraphics
import Foundation
import ImageIO

/// The input cannot be processed. Messages never contain paths, and are the
/// same as the Python engine's (files.InputError).
public struct InputError: Error, Equatable, CustomStringConvertible {
    public let description: String
    init(_ message: String) { description = message }
}

public enum OutFormat: String, Sendable {
    case jpeg = "JPEG", png = "PNG"

    public var ext: String { self == .jpeg ? "jpg" : "png" }
}

public struct LoadedImage: Sendable {
    public var rgb: RGBImage           // display orientation, sRGB
    public var alpha: [UInt8]?         // only if some pixel is not opaque, and only for PNG output
    public var sourceFormat: String    // JPEG, PNG, WEBP, HEIF (Pillow's names)
    public var outFormat: OutFormat
    public var metadataFound: [String] // sorted, names as image_io._metadata_found
}

/// Reading as image_io.load: EXIF orientation applied to the pixels, colour
/// profile converted to sRGB, everything in memory.
public enum ImageIn {
    public static let extensions: Set<String> = ["jpg", "jpeg", "png", "webp", "heic", "heif"]
    public static let maxPixels = 120_000_000
    public static let maxFileBytes = 300 * 1024 * 1024

    private static let formats: [String: (name: String, out: OutFormat)] = [
        "public.jpeg": ("JPEG", .jpeg),
        "public.heic": ("HEIF", .jpeg),
        "public.heif": ("HEIF", .jpeg),
        "org.webmproject.webp": ("WEBP", .jpeg),
        "public.png": ("PNG", .png),
    ]

    /// A local file. Checks as files.check_regular_file, then reads it into memory.
    public static func load(url: URL) throws -> LoadedImage {
        guard extensions.contains(url.pathExtension.lowercased()) else {
            throw InputError("unsupported image type (accepted: JPEG, PNG, WebP, HEIC)")
        }
        guard url.isFileURL else { throw InputError("URLs are not accepted: Blurry only reads local files") }
        let values: URLResourceValues
        do {
            values = try url.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
        } catch let error as CocoaError where error.code == .fileReadNoSuchFile {
            throw InputError("file not found (check the name and the folder)")
        } catch let error as CocoaError where error.code == .fileReadNoPermission {
            throw InputError("permission denied: the file cannot be read")
        } catch {
            throw InputError("the file cannot be read")
        }
        guard values.isRegularFile == true else { throw InputError("not a regular file") }
        try checkSize(values.fileSize ?? 0)
        let data: Data
        do { data = try Data(contentsOf: url) } catch { throw InputError("the file cannot be read") }
        return try load(data: data, fileExtension: url.pathExtension)
    }

    /// Bytes already in memory (from a photo picker or a shared file).
    public static func load(data: Data, fileExtension: String) throws -> LoadedImage {
        guard extensions.contains(fileExtension.lowercased()) else {
            throw InputError("unsupported image type (accepted: JPEG, PNG, WebP, HEIC)")
        }
        try checkSize(data.count)
        guard let src = CGImageSourceCreateWithData(data as CFData, [kCGImageSourceShouldCache: false] as CFDictionary),
              let type = CGImageSourceGetType(src) as String? else {
            throw InputError("not a readable image")
        }
        if type == "com.compuserve.gif" { throw InputError("GIF is not supported") }
        guard let format = formats[type] else {
            throw InputError("unsupported image format (accepted: JPEG, PNG, WebP, HEIC)")
        }
        if (format.name == "PNG" || format.name == "WEBP") && CGImageSourceGetCount(src) > 1 {
            throw InputError("animated images are not supported")
        }
        let index = format.name == "HEIF" ? CGImageSourceGetPrimaryImageIndex(src) : 0
        guard let props = CGImageSourceCopyPropertiesAtIndex(src, index, nil) as? [CFString: Any],
              let pw = props[kCGImagePropertyPixelWidth] as? Int,
              let ph = props[kCGImagePropertyPixelHeight] as? Int else {
            throw InputError("not a readable image")
        }
        if pw * ph > maxPixels { throw InputError("image too large") }

        let bytes = [UInt8](data)
        let found = metadataFound(bytes, format: format.name, src: src, index: index, props: props)
        guard let cg = CGImageSourceCreateImageAtIndex(src, index, [kCGImageSourceShouldCacheImmediately: true] as CFDictionary) else {
            throw InputError("image is damaged or too large")
        }
        let orientation = (props[kCGImagePropertyOrientation] as? NSNumber)?.intValue ?? 1
        var (rgb, alpha) = try decode(cg, orientation: orientation)
        if format.out == .jpeg, let a = alpha {
            // JPEG has no transparency: flatten on white, like most viewers show it.
            rgb.pixels.withUnsafeMutableBufferPointer { px in
                for i in 0..<a.count {
                    let f = Float(a[i]) / 255
                    for c in 0..<3 {
                        let v = Float(px[i * 3 + c]) * f + 255 * (1 - f) + 0.5
                        px[i * 3 + c] = UInt8(min(255, v))
                    }
                }
            }
            alpha = nil
        }
        return LoadedImage(rgb: rgb, alpha: alpha, sourceFormat: format.name, outFormat: format.out,
                           metadataFound: found.sorted())
    }

    private static func checkSize(_ size: Int) throws {
        if size == 0 { throw InputError("empty file") }
        if size > maxFileBytes { throw InputError("file too large (limit \(maxFileBytes / (1024 * 1024)) MB)") }
    }

    /// The pixels as RGBA without premultiplication, converted to sRGB by
    /// vImage, then put in display orientation. Alpha is kept only if some
    /// pixel is not fully opaque.
    static func decode(_ cg: CGImage, orientation: Int) throws -> (RGBImage, [UInt8]?) {
        guard var format = vImage_CGImageFormat(
            bitsPerComponent: 8, bitsPerPixel: 32,
            colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!,
            bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.last.rawValue)
        ) else { throw InputError("image is damaged or too large") }
        var buffer: vImage_Buffer
        do {
            buffer = try vImage_Buffer(cgImage: cg, format: format)
        } catch {
            throw InputError("image is damaged or too large")
        }
        defer { buffer.free() }
        _ = format

        let sw = Int(buffer.width), sh = Int(buffer.height), rowBytes = buffer.rowBytes
        let swapped = orientation >= 5 && orientation <= 8
        let w = swapped ? sh : sw, h = swapped ? sw : sh
        let hasAlpha = ![.none, .noneSkipFirst, .noneSkipLast].contains(cg.alphaInfo)
        var rgb = [UInt8](repeating: 0, count: w * h * 3)
        var alpha = hasAlpha ? [UInt8](repeating: 255, count: w * h) : nil
        var opaque = true
        let src = buffer.data.assumingMemoryBound(to: UInt8.self)
        rgb.withUnsafeMutableBufferPointer { out in
            for dy in 0..<h {
                for dx in 0..<w {
                    // Where the display pixel (dx, dy) is in the stored image (EXIF orientation).
                    let (sx, sy): (Int, Int)
                    switch orientation {
                    case 2: (sx, sy) = (sw - 1 - dx, dy)
                    case 3: (sx, sy) = (sw - 1 - dx, sh - 1 - dy)
                    case 4: (sx, sy) = (dx, sh - 1 - dy)
                    case 5: (sx, sy) = (dy, dx)
                    case 6: (sx, sy) = (dy, sh - 1 - dx)
                    case 7: (sx, sy) = (sw - 1 - dy, sh - 1 - dx)
                    case 8: (sx, sy) = (sw - 1 - dy, dx)
                    default: (sx, sy) = (dx, dy)
                    }
                    let s = sy * rowBytes + sx * 4, d = (dy * w + dx) * 3
                    out[d] = src[s]
                    out[d + 1] = src[s + 1]
                    out[d + 2] = src[s + 2]
                    if hasAlpha {
                        alpha![dy * w + dx] = src[s + 3]
                        if src[s + 3] != 255 { opaque = false }
                    }
                }
            }
        }
        return (RGBImage(width: w, height: h, pixels: rgb), opaque ? nil : alpha)
    }

    /// The same names as image_io._metadata_found, read from the file's own
    /// structure (Containers) where ImageIO would mix them up.
    static func metadataFound(_ bytes: [UInt8], format: String, src: CGImageSource, index: Int,
                              props: [CFString: Any]) -> Set<String> {
        var found: Set<String>
        switch format {
        case "JPEG": found = Containers.jpegMetadata(bytes)
        case "PNG": found = Containers.pngMetadata(bytes)
        case "WEBP": found = Containers.webpMetadata(bytes)
        default: found = Containers.heifMetadata(bytes)
        }
        if found.contains("exif") {
            if let gps = props[kCGImagePropertyGPSDictionary] as? [CFString: Any], !gps.isEmpty {
                found.insert("gps")
            }
            // HEIF rotation is applied by the decoder (pi-heif), not reported as EXIF.
            if format != "HEIF", let o = (props[kCGImagePropertyOrientation] as? NSNumber)?.intValue, o != 1 {
                found.insert("orientation")
            }
        }
        if format == "HEIF" {
            for type in [kCGImageAuxiliaryDataTypeDepth, kCGImageAuxiliaryDataTypeDisparity]
            where CGImageSourceCopyAuxiliaryDataInfoAtIndex(src, index, type) != nil {
                found.insert("depth_map")
            }
        }
        return found
    }
}
