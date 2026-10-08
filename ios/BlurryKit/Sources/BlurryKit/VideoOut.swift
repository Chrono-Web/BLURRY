import AVFoundation
import CoreGraphics
import Foundation

/// Clean video writing, as video_io.render: one H.264 video track (VideoToolbox)
/// and, only if asked, one AAC audio track. No container or track metadata,
/// chapters, subtitles, data tracks or cover art; the original timestamps,
/// so the sound stays in sync. Containers.cleanMovie then checks the file.
public enum VideoOut {
    public struct RenderError: Error, Equatable, CustomStringConvertible {
        public let description: String
    }

    /// Bits per pixel per frame for H.264: about what libx264 at CRF 18 gives.
    static let bitsPerPixel = 0.25

    /// Re-encode `url` into `output` (an MP4 that must not exist yet), passing
    /// every display-oriented frame through `process`. The frames must be
    /// exactly those analysed: one more is an error, never an uncovered frame.
    /// Returns whether audio was written.
    @discardableResult
    public static func render(_ url: URL, to output: URL, frameCount: Int, keepAudio: Bool,
                              progress: (@Sendable (Int, Int) -> Void)? = nil,
                              cancelled: @escaping @Sendable () -> Bool = { false },
                              process: @escaping @Sendable (Int, inout RGBImage) -> Void) async throws -> Bool {
        let (asset, video) = try await VideoIn.open(url)
        let (natural, transform, rate, formats) = try await video.load(.naturalSize, .preferredTransform,
                                                                         .nominalFrameRate, .formatDescriptions)
        let orient = Orientation(natural: natural, transform: transform, format: formats.first)
        let audioTrack = keepAudio ? try await asset.loadTracks(withMediaType: .audio).first : nil

        let reader = try AVAssetReader(asset: asset)
        let videoOut = AVAssetReaderTrackOutput(track: video, outputSettings: orient.readerSettings)
        videoOut.alwaysCopiesSampleData = false
        reader.add(videoOut)

        // yuv420p needs even sizes: crop the last row or column, as video_io does.
        let w = orient.width - orient.width % 2, h = orient.height - orient.height % 2
        let fps = rate > 0 ? Double(rate) : 30
        let writer = try AVAssetWriter(outputURL: output, fileType: .mp4)
        writer.shouldOptimizeForNetworkUse = true   // moov first, like +faststart
        writer.metadata = []
        let videoIn = AVAssetWriterInput(mediaType: .video, outputSettings: [
            AVVideoCodecKey: AVVideoCodecType.h264,
            AVVideoWidthKey: w,
            AVVideoHeightKey: h,
            // SDR, said so: with no tags a player may guess, and a phone shown
            // the frames of an HDR original guessed wrong (field test 2026-10-08).
            AVVideoColorPropertiesKey: [
                AVVideoColorPrimariesKey: AVVideoColorPrimaries_ITU_R_709_2,
                AVVideoTransferFunctionKey: AVVideoTransferFunction_ITU_R_709_2,
                AVVideoYCbCrMatrixKey: AVVideoYCbCrMatrix_ITU_R_709_2,
            ],
            AVVideoCompressionPropertiesKey: [
                AVVideoAverageBitRateKey: max(1_000_000, Int(Double(w * h) * fps * bitsPerPixel)),
                AVVideoProfileLevelKey: AVVideoProfileLevelH264HighAutoLevel,
                AVVideoExpectedSourceFrameRateKey: fps,
            ] as [String: Any],
        ])
        videoIn.expectsMediaDataInRealTime = false
        videoIn.metadata = []
        let adaptor = AVAssetWriterInputPixelBufferAdaptor(assetWriterInput: videoIn, sourcePixelBufferAttributes: [
            kCVPixelBufferPixelFormatTypeKey as String: kCVPixelFormatType_32BGRA,
            kCVPixelBufferWidthKey as String: w,
            kCVPixelBufferHeightKey as String: h,
        ])
        writer.add(videoIn)

        var audioOut: AVAssetReaderTrackOutput?
        var audioIn: AVAssetWriterInput?
        if let audioTrack {
            let formats = try await audioTrack.load(.formatDescriptions)
            let asbd = formats.first.flatMap { CMAudioFormatDescriptionGetStreamBasicDescription($0)?.pointee }
            let rate = asbd.map { $0.mSampleRate } ?? 48_000
            let channels = min(2, Int(asbd?.mChannelsPerFrame ?? 2))   // more than stereo is mixed down
            let o = AVAssetReaderTrackOutput(track: audioTrack, outputSettings: [
                AVFormatIDKey: kAudioFormatLinearPCM,
                AVSampleRateKey: rate,
                AVNumberOfChannelsKey: channels,
                AVLinearPCMBitDepthKey: 16,
                AVLinearPCMIsFloatKey: false,
                AVLinearPCMIsNonInterleaved: false,
                AVLinearPCMIsBigEndianKey: false,
            ])
            reader.add(o)
            let i = AVAssetWriterInput(mediaType: .audio, outputSettings: [
                AVFormatIDKey: kAudioFormatMPEG4AAC,
                AVSampleRateKey: rate,
                AVNumberOfChannelsKey: channels,
                AVEncoderBitRateKey: 64_000 * channels,
            ])
            i.expectsMediaDataInRealTime = false
            i.metadata = []
            writer.add(i)
            audioOut = o
            audioIn = i
        }

        guard reader.startReading() else { throw RenderError(description: "the video cannot be read") }
        guard writer.startWriting() else { throw RenderError(description: "the clean video cannot be written") }
        writer.startSession(atSourceTime: .zero)

        let state = RenderState()
        let group = DispatchGroup()
        group.enter()
        let videoQueue = DispatchQueue(label: "blurry.render.video")
        videoIn.requestMediaDataWhenReady(on: videoQueue) {
            while videoIn.isReadyForMoreMediaData {
                if cancelled() { state.fail("cancelled") }
                guard !state.failed, let sample = videoOut.copyNextSampleBuffer() else {
                    videoIn.markAsFinished()
                    group.leave()
                    return
                }
                guard let pixels = CMSampleBufferGetImageBuffer(sample) else { continue }
                let index = state.frames
                if index >= frameCount {
                    state.fail("decoded more frames than were analysed")
                    continue
                }
                var rgb = orient.rgb(pixels)
                process(index, &rgb)
                guard let pool = adaptor.pixelBufferPool, let buffer = Self.bgra(rgb, w, h, pool) else {
                    state.fail("the clean video cannot be written")
                    continue
                }
                var pts = CMSampleBufferGetPresentationTimeStamp(sample)
                if let last = state.lastPTS, pts <= last { pts = CMTimeAdd(last, CMTime(value: 1, timescale: pts.timescale)) }
                state.lastPTS = pts
                if !adaptor.append(buffer, withPresentationTime: pts) {
                    state.fail("the clean video cannot be written")
                    continue
                }
                state.frames = index + 1
                progress?(index + 1, frameCount)
            }
        }
        if let audioIn, let audioOut {
            group.enter()
            let audioQueue = DispatchQueue(label: "blurry.render.audio")
            audioIn.requestMediaDataWhenReady(on: audioQueue) {
                while audioIn.isReadyForMoreMediaData {
                    guard !state.failed, let sample = audioOut.copyNextSampleBuffer() else {
                        audioIn.markAsFinished()
                        group.leave()
                        return
                    }
                    if !audioIn.append(sample) { state.fail("the clean video cannot be written") }
                }
            }
        }
        await withCheckedContinuation { (done: CheckedContinuation<Void, Never>) in
            group.notify(queue: .global()) { done.resume() }
        }

        if state.failed || reader.status == .failed {
            reader.cancelReading()
            writer.cancelWriting()
            try? FileManager.default.removeItem(at: output)
            if state.message == "cancelled" { throw CancellationError() }
            throw RenderError(description: state.message ?? "the video is damaged")
        }
        await writer.finishWriting()
        guard writer.status == .completed else {
            try? FileManager.default.removeItem(at: output)
            throw RenderError(description: "the clean video cannot be written")
        }
        if state.frames != frameCount {
            try? FileManager.default.removeItem(at: output)
            throw RenderError(description: "decoded fewer frames than were analysed")
        }
        do {
            try Containers.cleanMovie(output)
        } catch {
            try? FileManager.default.removeItem(at: output)
            throw RenderError(description: "the output still holds metadata")
        }
        return audioIn != nil
    }

    /// RGB into a BGRA buffer from the writer's pool, cropped to w × h.
    static func bgra(_ rgb: RGBImage, _ w: Int, _ h: Int, _ pool: CVPixelBufferPool) -> CVPixelBuffer? {
        var out: CVPixelBuffer?
        guard CVPixelBufferPoolCreatePixelBuffer(nil, pool, &out) == kCVReturnSuccess, let buffer = out else { return nil }
        CVPixelBufferLockBaseAddress(buffer, [])
        defer { CVPixelBufferUnlockBaseAddress(buffer, []) }
        let row = CVPixelBufferGetBytesPerRow(buffer)
        let base = CVPixelBufferGetBaseAddress(buffer)!.assumingMemoryBound(to: UInt8.self)
        rgb.pixels.withUnsafeBufferPointer { px in
            for y in 0..<h {
                for x in 0..<w {
                    let s = (y * rgb.width + x) * 3, d = y * row + x * 4
                    base[d] = px[s + 2]; base[d + 1] = px[s + 1]; base[d + 2] = px[s]; base[d + 3] = 255
                }
            }
        }
        return buffer
    }
}

/// Shared between the writer's two queues.
private final class RenderState: @unchecked Sendable {
    private let lock = NSLock()
    private var _frames = 0, _failed = false, _message: String?, _lastPTS: CMTime?

    var frames: Int { get { lock.withLock { _frames } } set { lock.withLock { _frames = newValue } } }
    var lastPTS: CMTime? { get { lock.withLock { _lastPTS } } set { lock.withLock { _lastPTS = newValue } } }
    var failed: Bool { lock.withLock { _failed } }
    var message: String? { lock.withLock { _message } }

    func fail(_ message: String) {
        lock.withLock {
            if !_failed { _message = message }
            _failed = true
        }
    }
}
