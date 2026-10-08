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
        let output = AVAssetReaderTrackOutput(track: video, outputSettings: Orientation.readerSettings)
        output.alwaysCopiesSampleData = false
        reader.add(output)
        guard reader.startReading() else { throw InputError("not a readable video, or a container type that is not accepted") }
        defer { reader.cancelReading() }
        let orient = Orientation(natural: natural, transform: transform, format: formats.first)
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
struct Orientation {
    static let readerSettings: [String: Any] = [
        kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_420YpCbCr8BiPlanarVideoRange,
    ]

    let storedWidth: Int, storedHeight: Int
    let width: Int, height: Int
    private let inverse: CGAffineTransform
    private let bt709: Bool

    init(natural: CGSize, transform: CGAffineTransform, format: CMFormatDescription? = nil) {
        let declared = format.flatMap {
            CMFormatDescriptionGetExtension($0, extensionKey: kCMFormatDescriptionExtension_YCbCrMatrix) as? String
        }
        bt709 = declared == (kCMFormatDescriptionYCbCrMatrix_ITU_R_709_2 as String)
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
}
