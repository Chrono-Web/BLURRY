import SwiftUI

/// The app icon, 1024 × 1024, drawn in code like Globy's: a dark tile with
/// macOS corners and, in the middle, a face made of pixel blocks (what Blurry
/// does to faces), inside the green corner ticks of the drop window. Rendered with `--render-icon` (Debug only).
///
/// `fullBleed` is the iOS variant (`--render-icon-ios`): the tile fills the
/// square and has no shadow nor transparency, because iOS draws the rounded
/// corners itself; ticks and face keep their size relative to the tile.
@MainActor
struct AppIconArt: View {
    var fullBleed = false
    private static let corner: CGFloat = 186
    private static let tile: CGFloat = 824

    private var k: CGFloat { fullBleed ? 1024 / Self.tile : 1 }

    var body: some View {
        ZStack {
            if fullBleed {
                Rectangle()
                    .fill(LinearGradient(colors: [Color(white: 0.20), Color(white: 0.07)],
                                         startPoint: .top, endPoint: .bottom))
            } else {
                RoundedRectangle(cornerRadius: Self.corner, style: .continuous)
                    .fill(LinearGradient(colors: [Color(white: 0.20), Color(white: 0.07)],
                                         startPoint: .top, endPoint: .bottom))
                    .overlay {
                        RoundedRectangle(cornerRadius: Self.corner, style: .continuous)
                            .strokeBorder(.white.opacity(0.12), lineWidth: 4)
                    }
                    .frame(width: Self.tile, height: Self.tile)
                    .shadow(color: .black.opacity(0.28), radius: 18, y: 10)
            }
            CornerTicks(length: 92 * k)
                .stroke(accent, style: StrokeStyle(lineWidth: 20 * k, lineCap: .round, lineJoin: .round))
                .frame(width: 600 * k, height: 600 * k)
            Mosaic()
                .frame(width: 520 * k, height: 520 * k)
        }
        .frame(width: 1024, height: 1024)
    }
}

/// Blurry's face at rest (eyes open, looking ahead): the same 9 × 9 mosaic
/// the animated mascot draws (MascotFace), so icon and onboarding match.
@MainActor
private struct Mosaic: View {
    var body: some View {
        Canvas { ctx, size in
            let n = MascotFace.grid
            let cell = size.width / CGFloat(n)
            // Gap and corner radius keep the proportions of the original 7 × 7 blocks.
            let gap = cell * 9 / 74.3, radius = cell * 16 / 74.3
            let values = MascotFace.values(MascotFace.Pose())
            for (c, v) in zip(MascotFace.cells(n), values) {
                let rect = CGRect(x: CGFloat(c.col) * cell + gap / 2, y: CGFloat(c.row) * cell + gap / 2,
                                  width: cell - gap, height: cell - gap)
                ctx.fill(Path(roundedRect: rect, cornerRadius: radius), with: .color(Color(white: min(1, max(0, v)))))
            }
        }
    }
}

#if DEBUG
/// `Blurry --render-icon FILE` writes the 1024 px PNG and quits;
/// `--render-icon-ios FILE` writes the opaque, full-bleed iOS one.
enum IconRenderer {
    @MainActor
    static func runIfAsked() {
        let args = CommandLine.arguments
        let ios = args.contains("--render-icon-ios")
        guard let i = args.firstIndex(of: ios ? "--render-icon-ios" : "--render-icon"), i + 1 < args.count else { return }
        let renderer = ImageRenderer(content: AppIconArt(fullBleed: ios))
        renderer.scale = 1
        renderer.isOpaque = ios
        if let cg = renderer.cgImage,
           let png = NSBitmapImageRep(cgImage: cg).representation(using: .png, properties: [:]) {
            try? png.write(to: URL(fileURLWithPath: args[i + 1]))
        }
        exit(0)
    }
}
#endif
