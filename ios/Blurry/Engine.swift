import BlurryKit
import CoreGraphics
import Darwin
import Foundation

/// The settings a preview and an export use.
struct Settings: Equatable, Sendable {
    var level: String
    var mode: CoverMode
    var padding: Double
}

/// What one analysis gives: a plan per level from a single detection at the
/// most sensitive one (engine.image_plan_at), as the Mac app gets from the worker.
struct Analysis: @unchecked Sendable {
    let plans: [String: ImagePlan]
    let outFormat: OutFormat
    let thumb: CGImage
}

/// BlurryKit off the main thread. Only the file on screen stays decoded; the
/// others are kept as their original bytes and decoded again when needed.
actor Engine {
    static let previewMaxSide = 1600   // as the Mac app asks the worker

    private var detector: FaceDetector?
    private var current: (id: UUID, image: LoadedImage, small: RGBImage, scale: Double)?

    private func faceDetector() throws -> FaceDetector {
        if let detector { return detector }
        let d = try FaceDetector(level: Levels.shared.mostSensitive)
        detector = d
        return d
    }

    /// The model check (R5) at launch: a broken install is told at once.
    func prepare() throws { _ = try faceDetector() }

    func analyze(_ source: Source) throws -> Analysis {
        let entry = try load(source)
        let detector = try faceDetector()
        let boxes = try detector.detect(entry.image.rgb)
        let base = ImagePlan(width: entry.image.rgb.width, height: entry.image.rgb.height, boxes: boxes)
        var plans: [String: ImagePlan] = [:]
        for level in Levels.shared.levels {
            plans[level.name] = Review.imagePlan(base, at: level.confidence)
        }
        return Analysis(plans: plans, outFormat: entry.image.outFormat,
                        thumb: try Pictures.cgImage(entry.small))
    }

    /// The picture for the current step: faces outlined while choosing the
    /// sensitivity, the original for the editor, otherwise covered exactly as
    /// the export will be (worker.covered).
    func preview(_ source: Source, plan: ImagePlan, settings: Settings, outline: Bool, plain: Bool) throws -> CGImage {
        let entry = try load(source)
        var small = entry.small
        if plain { return try Pictures.cgImage(small) }
        let s = entry.scale
        let scaled = plan.boxes.map { b in
            Box(x: Int(Double(b.x) * s), y: Int(Double(b.y) * s),
                w: max(1, Int((Double(b.w) * s).rounded())), h: max(1, Int((Double(b.h) * s).rounded())),
                score: b.score, source: b.source)
        }
        if outline { return try Pictures.outlined(small, scaled) }
        var alpha: [UInt8]? = nil
        let blocks = try Levels.shared.get(settings.level).blocks
        Redact.apply(&small, alpha: &alpha, boxes: scaled, mode: settings.mode, padding: settings.padding,
                     blocks: blocks)
        return try Pictures.cgImage(small)
    }

    /// The clean file, at full resolution, in memory (engine.render_image).
    func render(_ source: Source, plan: ImagePlan, settings: Settings) throws -> Data {
        let entry = try load(source)
        var rgb = entry.image.rgb
        var alpha = entry.image.alpha
        let blocks = try Levels.shared.get(settings.level).blocks
        Redact.apply(&rgb, alpha: &alpha, boxes: plan.boxes, mode: settings.mode, padding: settings.padding,
                     blocks: blocks)
        return try ImageOut.encode(rgb, alpha: alpha, format: entry.image.outFormat)
    }

    /// Forget the decoded picture (a file removed, or the app in the background).
    func forget(_ id: UUID? = nil) {
        if id == nil || current?.id == id { current = nil }
    }

    private func load(_ source: Source) throws -> (image: LoadedImage, small: RGBImage, scale: Double) {
        if let c = current, c.id == source.id { return (c.image, c.small, c.scale) }
        current = nil   // one decoded picture at a time
        let image = try ImageIn.load(data: source.data, fileExtension: source.ext)
        let (small, scale) = try Pictures.downscale(image.rgb, maxSide: Self.previewMaxSide)
        current = (source.id, image, small, scale)
        return (image, small, scale)
    }
}

/// A file as it arrived: its bytes, never a path.
struct Source: Sendable {
    let id: UUID
    let data: Data
    let ext: String
}

enum Pictures {
    struct Failure: Error {}

    static func cgImage(_ rgb: RGBImage) throws -> CGImage {
        guard let provider = CGDataProvider(data: Data(rgb.pixels) as CFData),
              let image = CGImage(width: rgb.width, height: rgb.height, bitsPerComponent: 8, bitsPerPixel: 24,
                                  bytesPerRow: rgb.width * 3, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGBitmapInfo(rawValue: CGImageAlphaInfo.none.rawValue),
                                  provider: provider, decode: nil, shouldInterpolate: true,
                                  intent: .defaultIntent) else { throw Failure() }
        return image
    }

    /// A display copy no larger than `maxSide`, and the scale used (worker.downscale).
    static func downscale(_ rgb: RGBImage, maxSide: Int) throws -> (RGBImage, Double) {
        let scale = min(1.0, Double(maxSide) / Double(max(rgb.width, rgb.height)))
        guard scale < 1 else { return (rgb, 1) }
        let w = max(1, Int(Double(rgb.width) * scale)), h = max(1, Int(Double(rgb.height) * scale))
        var rgba = [UInt8](repeating: 0, count: w * h * 4)
        let source = try cgImage(rgb)
        let drawn: Bool = rgba.withUnsafeMutableBytes { buf in
            guard let ctx = CGContext(data: buf.baseAddress, width: w, height: h, bitsPerComponent: 8,
                                      bytesPerRow: w * 4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                      bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return false }
            ctx.interpolationQuality = .high
            ctx.draw(source, in: CGRect(x: 0, y: 0, width: w, height: h))
            return true
        }
        guard drawn else { throw Failure() }
        var out = [UInt8](repeating: 0, count: w * h * 3)
        for i in 0..<(w * h) {
            out[i * 3] = rgba[i * 4]; out[i * 3 + 1] = rgba[i * 4 + 1]; out[i * 3 + 2] = rgba[i * 4 + 2]
        }
        return (RGBImage(width: w, height: h, pixels: out), scale)
    }

    /// The detected faces outlined in green, 2 px, on the original.
    static func outlined(_ rgb: RGBImage, _ boxes: [Box]) throws -> CGImage {
        let w = rgb.width, h = rgb.height
        guard let ctx = CGContext(data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                                  space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { throw Failure() }
        ctx.draw(try cgImage(rgb), in: CGRect(x: 0, y: 0, width: w, height: h))
        ctx.translateBy(x: 0, y: CGFloat(h))
        ctx.scaleBy(x: 1, y: -1)   // image coordinates: y grows downwards
        ctx.setStrokeColor(red: 0x49 / 255, green: 0xDC / 255, blue: 0x18 / 255, alpha: 1)
        ctx.setLineWidth(2)
        for b in boxes { ctx.stroke(CGRect(x: b.x, y: b.y, width: b.w, height: b.h)) }
        guard let image = ctx.makeImage() else { throw Failure() }
        return image
    }

    /// The process's highest physical footprint so far: what iOS watches before
    /// closing an app for using too much memory (PIANO_BLURRY 5b).
    static func peakMemory() -> UInt64 {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let kr = withUnsafeMutablePointer(to: &info) {
            $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        return kr == KERN_SUCCESS ? UInt64(max(0, info.ledger_phys_footprint_peak)) : 0
    }
}
