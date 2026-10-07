import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

/// Clean writing as image_io.encode: the pixels only. ImageIO encodes, then
/// Containers keeps only what is needed to show the image (see there why).
public enum ImageOut {
    public struct EncodeError: Error, Equatable, CustomStringConvertible {
        public let description: String
    }

    public static func encode(_ rgb: RGBImage, alpha: [UInt8]?, format: OutFormat) throws -> Data {
        let w = rgb.width, h = rgb.height
        let withAlpha = alpha != nil && format == .png
        var pixels: [UInt8]
        if withAlpha, let alpha {
            pixels = [UInt8](repeating: 0, count: w * h * 4)
            for i in 0..<(w * h) {
                pixels[i * 4] = rgb.pixels[i * 3]
                pixels[i * 4 + 1] = rgb.pixels[i * 3 + 1]
                pixels[i * 4 + 2] = rgb.pixels[i * 3 + 2]
                pixels[i * 4 + 3] = alpha[i]
            }
        } else {
            pixels = rgb.pixels
        }
        let channels = withAlpha ? 4 : 3
        let info = withAlpha ? CGImageAlphaInfo.last : CGImageAlphaInfo.none
        guard let provider = CGDataProvider(data: Data(pixels) as CFData),
              let image = CGImage(width: w, height: h, bitsPerComponent: 8, bitsPerPixel: 8 * channels,
                                  bytesPerRow: w * channels, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  bitmapInfo: CGBitmapInfo(rawValue: info.rawValue), provider: provider,
                                  decode: nil, shouldInterpolate: false, intent: .defaultIntent) else {
            throw EncodeError(description: "cannot build the image")
        }
        let out = NSMutableData()
        let type = format == .jpeg ? UTType.jpeg : UTType.png
        guard let dest = CGImageDestinationCreateWithData(out, type.identifier as CFString, 1, nil) else {
            throw EncodeError(description: "cannot encode \(format.rawValue)")
        }
        let props: [CFString: Any] = format == .jpeg ? [kCGImageDestinationLossyCompressionQuality: 0.95] : [:]
        CGImageDestinationAddImage(dest, image, props as CFDictionary)
        guard CGImageDestinationFinalize(dest) else { throw EncodeError(description: "cannot encode \(format.rawValue)") }

        let encoded = [UInt8](out as Data)
        let clean = format == .jpeg ? try Containers.cleanJPEG(encoded) : try Containers.cleanPNG(encoded)
        guard Containers.isClean(clean) else { throw EncodeError(description: "the output still holds metadata") }
        return Data(clean)
    }
}
