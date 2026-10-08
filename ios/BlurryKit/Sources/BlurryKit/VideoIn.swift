import AVFoundation
import CoreGraphics
import Foundation

/// What a video is, before analysis (video_io.VideoInfo).
public struct VideoInfo: Equatable, Sendable {
    public let width: Int           // display orientation
    public let height: Int
    public let fps: Double
    public let estimatedFrames: Int
    public let hasAudio: Bool
    public let metadataFound: [String]   // names as video_io._metadata_found
}

/// Reading videos with AVFoundation, as video_io.py does with PyAV: frames in
/// display orientation (the track's transform applied before detection, or a
/// phone's vertical video reaches YuNet sideways), in presentation order.
/// Only MP4, MOV and M4V: AVFoundation does not read MKV, WebM or AVI.
public enum VideoIn {
    public static let extensions: Set<String> = ["mp4", "mov", "m4v"]
    public static let maxFileBytes: Int64 = 20 * 1024 * 1024 * 1024
    public static let maxDuration = 3.0 * 3600
    public static let maxFramePixels = 8192 * 4352

    /// The checks of video_io.open_input, then the main video track.
    static func open(_ url: URL) async throws -> (AVURLAsset, AVAssetTrack) {
        guard extensions.contains(url.pathExtension.lowercased()) else {
            throw InputError("unsupported video type (accepted: MP4, MOV, M4V)")
        }
        guard url.isFileURL else { throw InputError("URLs are not accepted: Blurry only reads local files") }
        let values: URLResourceValues
        do {
            values = try url.resourceValues(forKeys: [.isRegularFileKey, .fileSizeKey])
        } catch {
            throw InputError("file not found (check the name and the folder)")
        }
        guard values.isRegularFile == true else { throw InputError("not a regular file") }
        let size = Int64(values.fileSize ?? 0)
        if size == 0 { throw InputError("empty file") }
        if size > maxFileBytes { throw InputError("file too large (limit \(maxFileBytes / (1024 * 1024)) MB)") }

        // Local files only: no AVAsset resource loader, no network (R1).
        let asset = AVURLAsset(url: url, options: [AVURLAssetPreferPreciseDurationAndTimingKey: true])
        let tracks: [AVAssetTrack]
        let duration: CMTime
        do {
            tracks = try await asset.loadTracks(withMediaType: .video)
            duration = try await asset.load(.duration)
        } catch {
            throw InputError("not a readable video, or a container type that is not accepted")
        }
        guard let video = tracks.first else { throw InputError("no video track") }
        if duration.seconds > maxDuration {
            throw InputError("video too long (limit \(Int(maxDuration) / 3600) h)")
        }
        return (asset, video)
    }

    public static func probe(_ url: URL) async throws -> VideoInfo {
        let (asset, video) = try await open(url)
        let (natural, transform, rate, range) = try await video.load(.naturalSize, .preferredTransform,
                                                                     .nominalFrameRate, .timeRange)
        let display = CGRect(origin: .zero, size: natural).applying(transform).standardized
        let w = Int(display.width.rounded()), h = Int(display.height.rounded())
        if w * h > maxFramePixels { throw InputError("video resolution too large") }
        let fps = rate > 0 ? Double(rate) : 30
        let audio = try await asset.loadTracks(withMediaType: .audio)
        var found = Containers.movMetadata(url)
        if !transform.isIdentity { found.insert("rotation") }
        return VideoInfo(width: w, height: h, fps: fps,
                         estimatedFrames: Int((range.duration.seconds * fps).rounded()),
                         hasAudio: !audio.isEmpty, metadataFound: found.sorted())
    }

    /// Every frame of the main video track from `start`, in display orientation,
    /// with its presentation time. `body` returns false to stop early.
    @discardableResult
    public static func frames(_ url: URL, from start: Int = 0, startTime: CMTime? = nil,
                              body: (Int, RGBImage, CMTime) throws -> Bool) async throws -> Int {
        let (asset, video) = try await open(url)
        let (natural, transform, formats) = try await video.load(.naturalSize, .preferredTransform, .formatDescriptions)
        let reader = try AVAssetReader(asset: asset)
        if let startTime { reader.timeRange = CMTimeRange(start: startTime, duration: .positiveInfinity) }
        let orient = Orientation(natural: natural, transform: transform, format: formats.first)
        let output = AVAssetReaderTrackOutput(track: video, outputSettings: orient.readerSettings)
        output.alwaysCopiesSampleData = false
        reader.add(output)
        guard reader.startReading() else { throw InputError("not a readable video, or a container type that is not accepted") }
        defer { reader.cancelReading() }
        var index = startTime == nil ? 0 : start
        while let sample = output.copyNextSampleBuffer() {
            guard let pixels = CMSampleBufferGetImageBuffer(sample) else { continue }
            let pts = CMSampleBufferGetPresentationTimeStamp(sample)
            if index >= start {
                if try !body(index, orient.rgb(pixels), pts) { return index + 1 }
            }
            index += 1
        }
        if reader.status == .failed { throw InputError("the video is damaged") }
        return index
    }

    /// One frame by index. With the timestamps recorded during analysis the
    /// reader starts at that time instead of decoding from the beginning.
    public static func frame(_ url: URL, at index: Int, pts: [CMTime]? = nil) async throws -> RGBImage {
        var found: RGBImage?
        let time = pts.flatMap { index < $0.count ? $0[index] : nil }
        try await frames(url, from: index, startTime: time) { i, rgb, _ in
            if i == index { found = rgb; return false }
            return true
        }
        guard let found else { throw InputError("frame out of range") }
        return found
    }
}

/// From a decoded frame, as stored, to RGB in display orientation.
///
/// The reader hands over the YUV planes and the conversion to RGB is done
/// here, as FFmpeg's swscale does it for the Python engine: each chroma sample
/// covers 2 × 2 pixels, and the matrix is the one the file declares in its
/// format description (BT.601 when it declares none, as FFmpeg assumes; the
/// buffers' own attachment says BT.709 even then), limited or full range.
/// AVFoundation's BGRA output differs from FFmpeg's by about 4 levels on
/// average (VERIFICA 5c).
///
/// HDR is the exception. Read as 8-bit BT.601 it looks washed out (field test
/// 2026-10-08). HLG, what the iPhone records, is read at 10 bits and converted
/// here the way Apple's own HDR -> SDR conversion does it, measured on a grey
/// ramp: BT.2020 matrix, inverse HLG OETF with the peak as white, BT.2020 ->
/// BT.709 primaries, then a 1/2.57 power (3 levels from Apple's curve, RMS).
/// Taking HLG 75 % as white instead (BT.2408) blew real iPhone videos out:
/// they keep much of the picture above it. PQ and other BT.2020 video is left
/// to the reader's own conversion to BT.709.
struct Orientation {
    let readerSettings: [String: Any]

    let storedWidth: Int, storedHeight: Int
    let width: Int, height: Int
    private let inverse: CGAffineTransform
    private let bt709: Bool
    private let hlg: Bool

    init(natural: CGSize, transform: CGAffineTransform, format: CMFormatDescription? = nil) {
        let declared = format.flatMap {
            CMFormatDescriptionGetExtension($0, extensionKey: kCMFormatDescriptionExtension_YCbCrMatrix) as? String
        }
        func ext(_ key: CFString) -> String? {
            format.flatMap { CMFormatDescriptionGetExtension($0, extensionKey: key) as? String }
        }
        let transfer = ext(kCMFormatDescriptionExtension_TransferFunction)
        let wide = ext(kCMFormatDescriptionExtension_ColorPrimaries) == (kCMFormatDescriptionColorPrimaries_ITU_R_2020 as String)
            || declared == (kCMFormatDescriptionYCbCrMatrix_ITU_R_2020 as String)
            || transfer == (kCMFormatDescriptionTransferFunction_ITU_R_2100_HLG as String)
            || transfer == (kCMFormatDescriptionTransferFunction_SMPTE_ST_2084_PQ as String)
        hlg = transfer == (kCMFormatDescriptionTransferFunction_ITU_R_2100_HLG as String)
        var settings: [String: Any] = [
            kCVPixelBufferPixelFormatTypeKey as String: hlg ? kCVPixelFormatType_420YpCbCr10BiPlanarVideoRange
                                                            : kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,
        ]
        if wide && !hlg {
            settings[AVVideoColorPropertiesKey] = [
                AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
                AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
                AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2,
            ]
        }
        readerSettings = settings
        bt709 = wide || declared == (kCMFormatDescriptionYCbCrMatrix_ITU_R_709_2 as String)
        storedWidth = Int(natural.width.rounded())
        storedHeight = Int(natural.height.rounded())
        let rect = CGRect(origin: .zero, size: natural).applying(transform).standardized
        width = Int(rect.width.rounded())
        height = Int(rect.height.rounded())
        // Display point -> stored point: undo the transform, after moving the
        // transformed rectangle back to the origin.
        inverse = transform.concatenating(CGAffineTransform(translationX: -rect.minX, y: -rect.minY)).inverted()
    }

    /// YCbCr -> RGB coefficients: (luma scale, luma offset, Cr->R, Cb->G, Cr->G, Cb->B).
    private static func coefficients(bt709: Bool, full: Bool) -> (Float, Float, Float, Float, Float, Float) {
        // Kr, Kb of the matrix; the rest follows.
        let (kr, kb): (Float, Float) = bt709 ? (0.2126, 0.0722) : (0.299, 0.114)
        let kg = 1 - kr - kb
        let ys: Float = full ? 1 : 255 / 219, yo: Float = full ? 0 : 16
        let cs: Float = full ? 1 : 255 / 224
        return (ys, yo, 2 * (1 - kr) * cs, 2 * (1 - kb) * kb / kg * cs, 2 * (1 - kr) * kr / kg * cs, 2 * (1 - kb) * cs)
    }

    func rgb(_ buffer: CVPixelBuffer) -> RGBImage {
        if CVPixelBufferGetPixelFormatType(buffer) == kCVPixelFormatType_420YpCbCr10BiPlanarVideoRange {
            return rgbHLG(buffer)
        }
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        let bw = CVPixelBufferGetWidth(buffer), bh = CVPixelBufferGetHeight(buffer)
        let format = CVPixelBufferGetPixelFormatType(buffer)
        let full = format == kCVPixelFormatType_420YpCbCr8BiPlanarFullRange
        let yRow = CVPixelBufferGetBytesPerRowOfPlane(buffer, 0), cRow = CVPixelBufferGetBytesPerRowOfPlane(buffer, 1)
        let yp = CVPixelBufferGetBaseAddressOfPlane(buffer, 0)!.assumingMemoryBound(to: UInt8.self)
        let cp = CVPixelBufferGetBaseAddressOfPlane(buffer, 1)!.assumingMemoryBound(to: UInt8.self)
        let (ys, yo, rv, gu, gv, bu) = Self.coefficients(bt709: bt709, full: full)
        // A buffer of another size than the track says (rare): show it as it is.
        let identity = inverse.isIdentity || bw != storedWidth || bh != storedHeight
        let w = identity ? bw : width, h = identity ? bh : height
        var out = [UInt8](repeating: 0, count: w * h * 3)
        let t = inverse
        // Truncated, like swscale's fixed-point tables: 0.2 levels from FFmpeg on average, 1 at most.
        @inline(__always) func clamp(_ v: Float) -> UInt8 { UInt8(max(0, min(255, v.rounded(.down)))) }
        out.withUnsafeMutableBufferPointer { o in
            for dy in 0..<h {
                for dx in 0..<w {
                    let sx: Int, sy: Int
                    if identity {
                        sx = dx; sy = dy
                    } else {
                        // A multiple of 90° (with or without a mirror), sampled at pixel centres.
                        let px = Double(dx) + 0.5, py = Double(dy) + 0.5
                        sx = min(bw - 1, max(0, Int((t.a * px + t.c * py + t.tx).rounded(.down))))
                        sy = min(bh - 1, max(0, Int((t.b * px + t.d * py + t.ty).rounded(.down))))
                    }
                    let y = (Float(yp[sy * yRow + sx]) - yo) * ys
                    let c = (sy / 2) * cRow + (sx / 2) * 2
                    let cb = Float(cp[c]) - 128, cr = Float(cp[c + 1]) - 128
                    let d = (dy * w + dx) * 3
                    o[d] = clamp(y + rv * cr)
                    o[d + 1] = clamp(y - gu * cb - gv * cr)
                    o[d + 2] = clamp(y + bu * cb)
                }
            }
        }
        return RGBImage(width: w, height: h, pixels: out)
    }

    /// Display pixel -> stored pixel, for every pixel of the output.
    @inline(__always)
    private func source(_ dx: Int, _ dy: Int, identity: Bool, bw: Int, bh: Int) -> (Int, Int) {
        if identity { return (dx, dy) }
        let px = Double(dx) + 0.5, py = Double(dy) + 0.5, t = inverse
        return (min(bw - 1, max(0, Int((t.a * px + t.c * py + t.tx).rounded(.down)))),
                min(bh - 1, max(0, Int((t.b * px + t.d * py + t.ty).rounded(.down)))))
    }

    /// Inverse HLG OETF (BT.2100) on a non-linear value: scene light, 1.0 at the peak.
    private static let hlgLinear: [Float] = (0...4095).map { i in
        let e = Double(i) / 4095
        let a = 0.17883277, b = 1 - 4 * a, c = 0.5 - a * log(4 * a)
        return Float(e <= 0.5 ? e * e / 3 : (exp((e - c) / a) + b) / 12)
    }

    /// Scene light (1.0 = white) -> 8 bit, as Apple's conversion: a 1/2.57 power.
    private static let srgb: [UInt8] = (0...16383).map { i in
        UInt8(max(0, min(255, (pow(Double(i) / 16383, 1 / 2.57) * 255).rounded())))
    }

    private func rgbHLG(_ buffer: CVPixelBuffer) -> RGBImage {
        CVPixelBufferLockBaseAddress(buffer, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(buffer, .readOnly) }
        let bw = CVPixelBufferGetWidth(buffer), bh = CVPixelBufferGetHeight(buffer)
        let yRow = CVPixelBufferGetBytesPerRowOfPlane(buffer, 0) / 2, cRow = CVPixelBufferGetBytesPerRowOfPlane(buffer, 1) / 2
        let yp = CVPixelBufferGetBaseAddressOfPlane(buffer, 0)!.assumingMemoryBound(to: UInt16.self)
        let cp = CVPixelBufferGetBaseAddressOfPlane(buffer, 1)!.assumingMemoryBound(to: UInt16.self)
        let identity = inverse.isIdentity || bw != storedWidth || bh != storedHeight
        let w = identity ? bw : width, h = identity ? bh : height
        var out = [UInt8](repeating: 0, count: w * h * 3)
        let toLinear = Self.hlgLinear, toSRGB = Self.srgb
        @inline(__always) func lin(_ v: Float) -> Float { toLinear[Int(max(0, min(1, v)) * 4095 + 0.5)] }
        @inline(__always) func enc(_ v: Float) -> UInt8 { toSRGB[Int(max(0, min(1, v)) * 16383 + 0.5)] }
        out.withUnsafeMutableBufferPointer { o in
            for dy in 0..<h {
                for dx in 0..<w {
                    let (sx, sy) = source(dx, dy, identity: identity, bw: bw, bh: bh)
                    // 10 bits in the high bits of 16; limited range.
                    let y = (Float(yp[sy * yRow + sx] >> 6) - 64) / 876
                    let c = (sy / 2) * cRow + (sx / 2) * 2
                    let cb = (Float(cp[c] >> 6) - 512) / 896, cr = (Float(cp[c + 1] >> 6) - 512) / 896
                    // BT.2020 non-constant luminance.
                    let r = lin(y + 1.4746 * cr), g = lin(y - 0.16455 * cb - 0.57135 * cr), b = lin(y + 1.8814 * cb)
                    // BT.2020 -> BT.709 primaries (BT.2087).
                    let d = (dy * w + dx) * 3
                    o[d] = enc(1.6605 * r - 0.5876 * g - 0.0728 * b)
                    o[d + 1] = enc(-0.1246 * r + 1.1329 * g - 0.0083 * b)
                    o[d + 2] = enc(-0.0182 * r - 0.1006 * g + 1.1187 * b)
                }
            }
        }
        return RGBImage(width: w, height: h, pixels: out)
    }
}
