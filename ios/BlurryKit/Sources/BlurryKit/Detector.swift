import CoreML
import Foundation

/// 8-bit RGB pixels, interleaved, display orientation, sRGB.
public struct RGBImage: Equatable, Sendable {
    public let width: Int
    public let height: Int
    public var pixels: [UInt8]   // width * height * 3

    public init(width: Int, height: Int, pixels: [UInt8]) {
        precondition(pixels.count == width * height * 3, "RGB buffer size")
        self.width = width; self.height = height; self.pixels = pixels
    }
}

/// Face detection with YuNet through Core ML, as detect.FaceDetector does with
/// cv2.FaceDetectorYN: same padding, same decoding, same NMS, same rounding.
/// scripts/coreml/prova-yunet.sh and the parity tests check that the boxes and
/// scores are identical to the engine's.
public final class FaceDetector {
    public let level: Level
    private let model: MLModel
    private let levels: Levels
    private static let strides = [8, 16, 32]

    public init(level: String? = nil, computeUnits: MLComputeUnits = .all, levels: Levels = .shared) throws {
        self.levels = levels
        self.level = try levels.get(level ?? levels.defaultLevel)
        model = try Model.loadVerified(computeUnits: computeUnits)
    }

    public var confidence: Double { level.confidence }

    /// Boxes clipped to the image, scores included.
    public func detect(_ image: RGBImage) throws -> [Box] {
        let w = image.width, h = image.height
        guard w > 0, h > 0 else { return [] }
        // Zero padding right and bottom up to a multiple of 32, like FaceDetectorYN.
        let pw = (w - 1) / 32 * 32 + 32, ph = (h - 1) / 32 * 32 + 32
        let input = try MLMultiArray(shape: [1, 3, NSNumber(value: ph), NSNumber(value: pw)], dataType: .float32)
        input.withUnsafeMutableBufferPointer(ofType: Float.self) { ptr, strides in
            let cs = strides[1], ys = strides[2], xs = strides[3]
            ptr.initialize(repeating: 0)
            image.pixels.withUnsafeBufferPointer { px in
                for y in 0..<h {
                    var s = y * w * 3
                    var d = y * ys
                    for _ in 0..<w {
                        // Planes in BGR order, values 0...255, no mean or scale (blobFromImage).
                        ptr[d] = Float(px[s + 2])
                        ptr[d + cs] = Float(px[s + 1])
                        ptr[d + 2 * cs] = Float(px[s])
                        s += 3
                        d += xs
                    }
                }
            }
        }
        let out = try model.prediction(from: MLDictionaryFeatureProvider(dictionary: ["input": input]))
        let faces = try decode(out, paddedWidth: pw)
        return faces.compactMap { f in
            // int() then clip, as detect.py: YuNet can return boxes past the edges.
            var x = f.x, y = f.y, bw = f.w, bh = f.h
            x = max(0, x); y = max(0, y)
            bw = min(w - x, bw); bh = min(h - y, bh)
            return bw > 0 && bh > 0 ? Box(x: x, y: y, w: bw, h: bh, score: Double(f.score)) : nil
        }
    }

    private struct Candidate { var x, y, w, h: Int; var score: Float }

    /// FaceDetectorYN::postProcess followed by cv::dnn::NMSBoxes on Rect2i.
    private func decode(_ out: MLFeatureProvider, paddedWidth pw: Int) throws -> [Candidate] {
        let threshold = Float(level.confidence)
        var cands: [Candidate] = []
        for s in Self.strides {
            let cols = pw / s, fs = Float(s)
            let cls = try floats(out, "cls_\(s)"), obj = try floats(out, "obj_\(s)")
            let bbox = try floats(out, "bbox_\(s)")
            for i in 0..<cls.count {
                let score = (min(max(cls[i], 0), 1) * min(max(obj[i], 0), 1)).squareRoot()
                // NMSBoxes keeps only scores strictly above the threshold.
                guard score > threshold else { continue }
                let c = Float(i % cols), r = Float(i / cols)
                let cx = (c + bbox[i * 4]) * fs, cy = (r + bbox[i * 4 + 1]) * fs
                let bw = expf(bbox[i * 4 + 2]) * fs, bh = expf(bbox[i * 4 + 3]) * fs
                let x1 = cx - bw / 2, y1 = cy - bh / 2
                // A non-finite box is garbage from the network; C++ would not
                // define int() on it. Skip it rather than crash.
                guard x1.isFinite, y1.isFinite, bw.isFinite, bh.isFinite,
                      abs(x1) < 1e9, abs(y1) < 1e9, bw < 1e9, bh < 1e9 else { continue }
                cands.append(Candidate(x: Int(x1), y: Int(y1), w: Int(bw), h: Int(bh), score: score))
            }
        }
        // Stable sort by descending score: equal scores keep the decoding order.
        let order = cands.indices.sorted { a, b in
            cands[a].score != cands[b].score ? cands[a].score > cands[b].score : a < b
        }.prefix(levels.yunetTopk)
        var keep: [Candidate] = []
        let nms = levels.yunetNms
        for i in order {
            let c = cands[i]
            if keep.allSatisfy({ Self.iou($0, c) <= nms }) { keep.append(c) }
        }
        return keep
    }

    private static func iou(_ a: Candidate, _ b: Candidate) -> Double {
        let iw = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
        let ih = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
        let inter = iw > 0 && ih > 0 ? iw * ih : 0
        let union = a.w * a.h + b.w * b.h - inter
        return union > 0 ? Double(inter) / Double(union) : 0
    }

    private func floats(_ out: MLFeatureProvider, _ name: String) throws -> [Float] {
        guard let array = out.featureValue(for: name)?.multiArrayValue else {
            throw DetectorError.missingOutput(name)
        }
        if array.dataType == .float32 {
            // Shape [1, N, k]: copy row by row, whatever the strides.
            let n = array.shape[1].intValue, k = array.shape[2].intValue
            return array.withUnsafeBufferPointer(ofType: Float.self) { ptr in
                let rs = array.strides[1].intValue, es = array.strides[2].intValue
                var out = [Float](repeating: 0, count: n * k)
                for i in 0..<n {
                    for j in 0..<k { out[i * k + j] = ptr[i * rs + j * es] }
                }
                return out
            }
        }
        return MLShapedArray<Float>(converting: array).scalars
    }
}

public enum DetectorError: Error, Equatable {
    case missingOutput(String)
}
