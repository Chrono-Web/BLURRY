// YuNet through Core ML from Swift, with FaceDetectorYN's decode + NMS ported.
// usage: yunet <model.mlmodelc> <cpu|all> <data dir> <out.json> [fixtures dir]
// With a fixtures dir, the original files are also decoded with ImageIO
// (EXIF orientation applied, converted to sRGB) instead of using the dumped pixels.

import CoreGraphics
import CoreML
import Foundation
import ImageIO

var predictionTime = 0.0   // Core ML alone, without decode and NMS
let strides = [8, 16, 32]
let scoreThreshold: Float = 0.5   // levels.MOST_SENSITIVE
let nmsThreshold = 0.3            // levels.YUNET_NMS
let topK = 5000                   // levels.YUNET_TOPK

struct Rect { var x, y, w, h: Int }

func iou(_ a: Rect, _ b: Rect) -> Double {
    let iw = min(a.x + a.w, b.x + b.w) - max(a.x, b.x)
    let ih = min(a.y + a.h, b.y + b.h) - max(a.y, b.y)
    let inter = iw > 0 && ih > 0 ? iw * ih : 0
    let union = a.w * a.h + b.w * b.h - inter
    return union > 0 ? Double(inter) / Double(union) : 0
}

/// Runs the model on BGR uint8 pixels and returns [x, y, w, h, score] like FaceDetector.detect.
func detect(_ model: MLModel, bgr: [UInt8], w: Int, h: Int) throws -> [[Double]] {
    let pw = (w - 1) / 32 * 32 + 32, ph = (h - 1) / 32 * 32 + 32
    var chw = [Float](repeating: 0, count: 3 * pw * ph)   // zero padding right/bottom
    for y in 0..<h {
        for x in 0..<w {
            let s = (y * w + x) * 3
            for c in 0..<3 { chw[c * pw * ph + y * pw + x] = Float(bgr[s + c]) }
        }
    }
    let input = MLMultiArray(MLShapedArray<Float>(scalars: chw, shape: [1, 3, ph, pw]))
    let t0 = Date()
    let out = try model.prediction(from: MLDictionaryFeatureProvider(dictionary: ["input": input]))
    predictionTime += Date().timeIntervalSince(t0)
    func arr(_ n: String) -> [Float] {
        MLShapedArray<Float>(converting: out.featureValue(for: n)!.multiArrayValue!).scalars
    }

    var rects: [Rect] = [], faces: [[Float]] = [], scores: [Float] = []
    for s in strides {
        let cols = pw / s
        let cls = arr("cls_\(s)"), obj = arr("obj_\(s)"), bbox = arr("bbox_\(s)")
        let fs = Float(s)
        for i in 0..<cls.count {
            let score = (min(max(cls[i], 0), 1) * min(max(obj[i], 0), 1)).squareRoot()
            let c = Float(i % cols), r = Float(i / cols)
            let cx = (c + bbox[i * 4]) * fs, cy = (r + bbox[i * 4 + 1]) * fs
            let bw = expf(bbox[i * 4 + 2]) * fs, bh = expf(bbox[i * 4 + 3]) * fs
            let f = [cx - bw / 2, cy - bh / 2, bw, bh, score]
            faces.append(f)
            scores.append(score)
            rects.append(Rect(x: Int(f[0]), y: Int(f[1]), w: Int(f[2]), h: Int(f[3])))
        }
    }
    // cv::dnn::NMSBoxes: score > thr, stable sort descending, top_k, keep if IoU <= nms.
    var cand = scores.indices.filter { scores[$0] > scoreThreshold }
    cand = cand.enumerated().sorted { a, b in
        scores[a.element] != scores[b.element] ? scores[a.element] > scores[b.element] : a.offset < b.offset
    }.map(\.element)
    if cand.count > topK { cand = Array(cand[..<topK]) }
    var keep: [Int] = []
    for i in cand where keep.allSatisfy({ iou(rects[i], rects[$0]) <= nmsThreshold }) { keep.append(i) }

    return keep.compactMap { i in
        let f = faces[i]
        var x = Int(f[0]), y = Int(f[1]), bw = Int(f[2]), bh = Int(f[3])
        x = max(0, x); y = max(0, y)
        bw = min(w - x, bw); bh = min(h - y, bh)
        return bw > 0 && bh > 0 ? [Double(x), Double(y), Double(bw), Double(bh), Double(f[4])] : nil
    }
}

/// ImageIO decode with EXIF orientation, drawn into sRGB, returned as BGR.
func loadImageIO(_ url: URL) -> (bgr: [UInt8], w: Int, h: Int)? {
    guard let src = CGImageSourceCreateWithURL(url as CFURL, nil),
          let props = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as? [CFString: Any],
          let pw = props[kCGImagePropertyPixelWidth] as? Int,
          let ph = props[kCGImagePropertyPixelHeight] as? Int else { return nil }
    let opts: [CFString: Any] = [
        kCGImageSourceCreateThumbnailFromImageAlways: true,
        kCGImageSourceCreateThumbnailWithTransform: true,
        kCGImageSourceThumbnailMaxPixelSize: max(pw, ph),
        kCGImageSourceShouldCacheImmediately: true,
    ]
    guard let img = CGImageSourceCreateThumbnailAtIndex(src, 0, opts as CFDictionary) else { return nil }
    let w = img.width, h = img.height
    var rgba = [UInt8](repeating: 0, count: w * h * 4)
    guard let ctx = CGContext(data: &rgba, width: w, height: h, bitsPerComponent: 8, bytesPerRow: w * 4,
                              space: CGColorSpace(name: CGColorSpace.sRGB)!,
                              bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else { return nil }
    ctx.draw(img, in: CGRect(x: 0, y: 0, width: w, height: h))
    var bgr = [UInt8](repeating: 0, count: w * h * 3)
    for p in 0..<(w * h) {
        bgr[p * 3] = rgba[p * 4 + 2]; bgr[p * 3 + 1] = rgba[p * 4 + 1]; bgr[p * 3 + 2] = rgba[p * 4]
    }
    return (bgr, w, h)
}

let args = CommandLine.arguments
let config = MLModelConfiguration()
config.computeUnits = args[2] == "cpu" ? .cpuOnly : .all
let model = try MLModel(contentsOf: URL(fileURLWithPath: args[1]), configuration: config)
let dir = URL(fileURLWithPath: args[3])
let index = try JSONSerialization.jsonObject(with: Data(contentsOf: dir.appendingPathComponent("index.json"))) as! [[String: Any]]
let fixtures = args.count > 5 ? URL(fileURLWithPath: args[5]) : nil

var results: [String: Any] = [:]
var total = 0.0
for item in index {
    let name = item["name"] as! String
    var bgr: [UInt8], w: Int, h: Int
    if let fixtures {
        // Only the original files: derived images exist only as dumped pixels.
        let url = ["public", "private"].map { fixtures.appendingPathComponent($0).appendingPathComponent(name) }
            .first { FileManager.default.fileExists(atPath: $0.path) }
        guard let url, let loaded = loadImageIO(url) else { continue }
        (bgr, w, h) = loaded
    } else {
        w = item["w"] as! Int; h = item["h"] as! Int
        bgr = [UInt8](try Data(contentsOf: dir.appendingPathComponent(item["file"] as! String)))
    }
    let t0 = Date()
    results[name] = try detect(model, bgr: bgr, w: w, h: h)
    total += Date().timeIntervalSince(t0)
}
try JSONSerialization.data(withJSONObject: results).write(to: URL(fileURLWithPath: args[4]))
print(String(format: "%d images in %.2fs, Core ML prediction %.2fs", results.count, total, predictionTime))
