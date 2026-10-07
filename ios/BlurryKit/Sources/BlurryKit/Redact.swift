import Foundation

/// Cover regions as redact.py: solid black (default) or pixelation.
public enum Redact {
    /// (x0, y0, x1, y1) grown by `padding` x long side on every side, clipped.
    public static func paddedRect(_ box: Box, padding: Double, width: Int, height: Int)
        -> (x0: Int, y0: Int, x1: Int, y1: Int) {
        let pad = Int(Double(box.longSide) * padding)
        return (max(0, box.x - pad), max(0, box.y - pad),
                min(width, box.x + box.w + pad), min(height, box.y + box.h + pad))
    }

    /// Cover `boxes` in place, in order. Covered areas become fully opaque, so
    /// that a transparent region cannot hide the outline of a face.
    public static func apply(_ image: inout RGBImage, alpha: inout [UInt8]?, boxes: [Box],
                             mode: CoverMode, padding: Double, blocks: Int) {
        let width = image.width, height = image.height
        for box in boxes {
            let r = paddedRect(box, padding: padding, width: width, height: height)
            guard r.x1 > r.x0, r.y1 > r.y0 else { continue }
            switch mode {
            case .solid:
                image.pixels.withUnsafeMutableBufferPointer { px in
                    for y in r.y0..<r.y1 {
                        let row = (y * width + r.x0) * 3
                        for i in row..<(row + (r.x1 - r.x0) * 3) { px[i] = 0 }
                    }
                }
            case .pixel:
                pixelate(&image, r.x0, r.y0, r.x1 - r.x0, r.y1 - r.y0, blocks: blocks)
            }
            if alpha != nil {
                for y in r.y0..<r.y1 {
                    for x in r.x0..<r.x1 { alpha![y * width + x] = 255 }
                }
            }
        }
    }

    /// A fixed number of blocks on the long side, so near and far faces end up
    /// equally anonymous. Down with OpenCV's INTER_AREA (every pixel of a block
    /// is averaged), up with INTER_NEAREST (hard blocks), as redact.pixelate.
    static func pixelate(_ image: inout RGBImage, _ x0: Int, _ y0: Int, _ w: Int, _ h: Int, blocks: Int) {
        let blockPx = max(1, Int((Double(max(w, h)) / Double(max(2, blocks))).rounded(.toNearestOrEven)))
        let sw = max(1, w / blockPx), sh = max(1, h / blockPx)
        let width = image.width
        // The region, as floats, channel-interleaved.
        var roi = [Float](repeating: 0, count: w * h * 3)
        image.pixels.withUnsafeBufferPointer { px in
            for y in 0..<h {
                for i in 0..<(w * 3) { roi[y * w * 3 + i] = Float(px[((y0 + y) * width + x0) * 3 + i]) }
            }
        }
        let small = areaDownscale(roi, w, h, sw, sh)
        // INTER_NEAREST: source index floor(x * (1 / (dst / src))), clamped.
        let ifx = 1.0 / (Double(w) / Double(sw)), ify = 1.0 / (Double(h) / Double(sh))
        let xo = (0..<w).map { min(Int((Double($0) * ifx).rounded(.down)), sw - 1) }
        image.pixels.withUnsafeMutableBufferPointer { px in
            for y in 0..<h {
                let sy = min(Int((Double(y) * ify).rounded(.down)), sh - 1)
                for x in 0..<w {
                    let s = (sy * sw + xo[x]) * 3, d = ((y0 + y) * width + x0 + x) * 3
                    px[d] = small[s]; px[d + 1] = small[s + 1]; px[d + 2] = small[s + 2]
                }
            }
        }
    }

    /// cv::resize with INTER_AREA when shrinking: the same tables
    /// (computeResizeAreaTab) and the same float accumulation, rounded half to even.
    static func areaDownscale(_ src: [Float], _ w: Int, _ h: Int, _ dw: Int, _ dh: Int) -> [UInt8] {
        let xtab = areaTab(w, dw), ytab = areaTab(h, dh)
        var out = [UInt8](repeating: 0, count: dw * dh * 3)
        var sum = [Float](repeating: 0, count: dw * 3)
        var buf = [Float](repeating: 0, count: dw * 3)
        var current = -1
        func flush(_ dy: Int) {
            for i in 0..<(dw * 3) { out[dy * dw * 3 + i] = UInt8(max(0, min(255, sum[i].rounded(.toNearestOrEven)))) }
        }
        for (dy, sy, beta) in ytab {
            for i in 0..<(dw * 3) { buf[i] = 0 }
            for (dx, sx, a) in xtab {
                for c in 0..<3 { buf[dx * 3 + c] += src[(sy * w + sx) * 3 + c] * a }
            }
            if dy != current {
                if current >= 0 { flush(current) }
                current = dy
                for i in 0..<(dw * 3) { sum[i] = beta * buf[i] }
            } else {
                for i in 0..<(dw * 3) { sum[i] += beta * buf[i] }
            }
        }
        if current >= 0 { flush(current) }
        return out
    }

    /// (destination index, source index, weight).
    static func areaTab(_ ssize: Int, _ dsize: Int) -> [(Int, Int, Float)] {
        let scale = Double(ssize) / Double(dsize)
        var tab: [(Int, Int, Float)] = []
        for dx in 0..<dsize {
            let fsx1 = Double(dx) * scale, fsx2 = fsx1 + scale
            let cellWidth = min(scale, Double(ssize) - fsx1)
            var sx1 = Int(fsx1.rounded(.up))
            var sx2 = Int(fsx2.rounded(.down))
            sx2 = min(sx2, ssize - 1)
            sx1 = min(sx1, sx2)
            if Double(sx1) - fsx1 > 1e-3 {
                tab.append((dx, sx1 - 1, Float((Double(sx1) - fsx1) / cellWidth)))
            }
            for sx in sx1..<max(sx1, sx2) { tab.append((dx, sx, Float(1.0 / cellWidth))) }
            if fsx2 - Double(sx2) > 1e-3 {
                tab.append((dx, sx2, Float(min(min(fsx2 - Double(sx2), 1.0), cellWidth) / cellWidth)))
            }
        }
        return tab
    }
}
