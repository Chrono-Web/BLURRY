import SwiftUI

/// The app icon, 1024 × 1024, drawn in code like Globy's: a dark tile with
/// macOS corners and, in the middle, a face made of pixel blocks (what Blurry
/// does to faces), inside the green corner ticks of the drop window. Rendered with `--render-icon` (Debug only).
struct AppIconArt: View {
    private static let corner: CGFloat = 186

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: Self.corner, style: .continuous)
                .fill(LinearGradient(colors: [Color(white: 0.20), Color(white: 0.07)],
                                     startPoint: .top, endPoint: .bottom))
                .overlay {
                    RoundedRectangle(cornerRadius: Self.corner, style: .continuous)
                        .strokeBorder(.white.opacity(0.12), lineWidth: 4)
                }
                .frame(width: 824, height: 824)
                .shadow(color: .black.opacity(0.28), radius: 18, y: 10)
            CornerTicks(length: 92)
                .stroke(accent, style: StrokeStyle(lineWidth: 20, lineCap: .round, lineJoin: .round))
                .frame(width: 600, height: 600)
            Mosaic()
                .frame(width: 520, height: 520)
        }
        .frame(width: 1024, height: 1024)
    }
}

/// The pixelated face. Blocks are grey, lighter towards the top left as if
/// lit from there, with a fixed pseudo-random variation so it reads as a mosaic.
private struct Mosaic: View {
    var body: some View {
        Canvas { ctx, size in
            let n = 7
            let cell = size.width / CGFloat(n)
            let gap: CGFloat = 9
            for row in 0..<n {
                for col in 0..<n {
                    guard inside(col: col, row: row, n: n) else { continue }
                    let light = 0.66 - 0.045 * Double(row + col) + noise(col, row) * 0.08
                    let rect = CGRect(x: CGFloat(col) * cell + gap / 2, y: CGFloat(row) * cell + gap / 2,
                                      width: cell - gap, height: cell - gap)
                    ctx.fill(Path(roundedRect: rect, cornerRadius: 16), with: .color(Color(white: max(0.20, light))))
                }
            }
        }
    }

    /// Which cells make the face.
    private func inside(col: Int, row: Int, n: Int) -> Bool {
        let x = Double(col) + 0.5 - Double(n) / 2
        let y = Double(row) + 0.5 - Double(n) / 2
        // A rounded square: full rows, with the corners taken away.
        return !(abs(x) == 3 && abs(y) >= 2) && !(abs(x) == 2 && abs(y) == 3)
    }

    private func noise(_ c: Int, _ r: Int) -> Double {
        let v = sin(Double(c * 12_9898 + r * 78_233)) * 43_758.5453
        return v - v.rounded(.down) - 0.5
    }
}

#if DEBUG
/// `Blurry --render-icon FILE` writes the 1024 px PNG and quits.
enum IconRenderer {
    @MainActor
    static func runIfAsked() {
        let args = CommandLine.arguments
        guard let i = args.firstIndex(of: "--render-icon"), i + 1 < args.count else { return }
        let renderer = ImageRenderer(content: AppIconArt())
        renderer.scale = 1
        if let cg = renderer.cgImage,
           let png = NSBitmapImageRep(cgImage: cg).representation(using: .png, properties: [:]) {
            try? png.write(to: URL(fileURLWithPath: args[i + 1]))
        }
        exit(0)
    }
}
#endif
