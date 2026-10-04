import SwiftUI

/// The app icon, 1024 × 1024, drawn in code like Globy's: a dark tile with
/// macOS corners and, in the middle, a face made of pixel blocks (what Blurry
/// does to faces), inside the green corner ticks of the drop window. Rendered with `--render-icon` (Debug only).
@MainActor
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

/// The pixelated face, on the same 9 × 9 grid as the animated mascot
/// (MascotFace). Blocks are grey, lighter towards the top left as if lit from
/// there, with a fixed pseudo-random variation so it reads as a mosaic.
@MainActor
private struct Mosaic: View {
    var body: some View {
        Canvas { ctx, size in
            let n = MascotFace.grid
            let cell = size.width / CGFloat(n)
            // Gap and corner radius keep the proportions of the original 7 × 7 blocks.
            let gap = cell * 9 / 74.3, radius = cell * 16 / 74.3
            for c in MascotFace.cells(n) {
                let diagonal = Double(c.row + c.col) / Double(2 * (n - 1))
                let light = 0.66 - 0.54 * diagonal + MascotFace.noise(c.col, c.row) * 0.08
                let rect = CGRect(x: CGFloat(c.col) * cell + gap / 2, y: CGFloat(c.row) * cell + gap / 2,
                                  width: cell - gap, height: cell - gap)
                ctx.fill(Path(roundedRect: rect, cornerRadius: radius), with: .color(Color(white: max(0.20, light))))
            }
        }
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
