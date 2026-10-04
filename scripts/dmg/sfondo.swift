// Disegna lo sfondo della finestra del DMG (660 × 480 pt) in 1x e 2x.
// Stesso impianto di Globy (CANALI/GLOBY/scripts/dmg/sfondo.swift), nei colori
// di Blurry: nero, testi bianco e grigio, freccia verde, angolini HUD.
// Uso: swift scripts/dmg/sfondo.swift <cartella di uscita>
import AppKit

let size = NSSize(width: 660, height: 480)
let out = URL(fileURLWithPath: CommandLine.arguments[1])
let green = NSColor(calibratedRed: 0x49 / 255, green: 0xDC / 255, blue: 0x18 / 255, alpha: 1)

func render(scale: CGFloat, to url: URL) {
    let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(size.width * scale), pixelsHigh: Int(size.height * scale),
                               bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false,
                               colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
    rep.size = size
    NSGraphicsContext.saveGraphicsState()
    let context = NSGraphicsContext(bitmapImageRep: rep)!
    NSGraphicsContext.current = context
    // Coordinate con l'origine in alto, come la finestra del Finder.
    context.cgContext.translateBy(x: 0, y: size.height)
    context.cgContext.scaleBy(x: 1, y: -1)

    let bounds = NSRect(origin: .zero, size: size)
    NSGradient(colors: [NSColor(calibratedWhite: 0.11, alpha: 1), NSColor(calibratedWhite: 0.02, alpha: 1)])!
        .draw(in: bounds, angle: -90)

    func text(_ string: String, size fontSize: CGFloat, weight: NSFont.Weight, color: NSColor, y: CGFloat) {
        let paragraph = NSMutableParagraphStyle()
        paragraph.alignment = .center
        let attributes: [NSAttributedString.Key: Any] = [
            .font: NSFont.systemFont(ofSize: fontSize, weight: weight),
            .foregroundColor: color,
            .paragraphStyle: paragraph,
        ]
        let attributed = NSAttributedString(string: string, attributes: attributes)
        let height = attributed.boundingRect(with: NSSize(width: size.width - 80, height: 200), options: .usesLineFragmentOrigin).height
        // Il testo va disegnato non capovolto: contesto locale riflesso attorno alla riga.
        let cg = context.cgContext
        cg.saveGState()
        cg.translateBy(x: 0, y: y + height)
        cg.scaleBy(x: 1, y: -1)
        attributed.draw(with: NSRect(x: 40, y: 0, width: size.width - 80, height: height), options: .usesLineFragmentOrigin)
        cg.restoreGState()
    }

    text("Installa Blurry", size: 26, weight: .semibold, color: .white, y: 34)
    text("Trascina Blurry nella cartella Applicazioni", size: 14, weight: .regular,
         color: NSColor(calibratedWhite: 0.55, alpha: 1), y: 72)

    // Angolini HUD, come nella finestra di trascinamento dell'app.
    let inset: CGFloat = 18, tick: CGFloat = 22
    let ticks = NSBezierPath()
    for (x, y, dx, dy) in [(inset, inset, 1.0, 1.0), (size.width - inset, inset, -1.0, 1.0),
                           (inset, size.height - inset, 1.0, -1.0), (size.width - inset, size.height - inset, -1.0, -1.0)] {
        ticks.move(to: NSPoint(x: x + dx * tick, y: y))
        ticks.line(to: NSPoint(x: x, y: y))
        ticks.line(to: NSPoint(x: x, y: y + dy * tick))
    }
    ticks.lineWidth = 2
    ticks.lineCapStyle = .round
    green.withAlphaComponent(0.8).setStroke()
    ticks.stroke()

    // Il Finder scrive i nomi sotto le icone in nero (aspetto chiaro) o in bianco
    // (aspetto scuro), mai in base allo sfondo: una pastiglia grigio medio sotto
    // ogni nome li rende leggibili in entrambi i casi.
    NSColor(calibratedWhite: 0.50, alpha: 1).setFill()
    for (x, y, w) in [(170.0, 271.0, 76.0), (490.0, 271.0, 120.0), (330.0, 431.0, 236.0)] {
        NSBezierPath(roundedRect: NSRect(x: x - w / 2, y: y - 11, width: w, height: 22), xRadius: 11, yRadius: 11).fill()
    }

    // Freccia tra le due icone (centri a x 170 e 490, y 200).
    let arrow = NSBezierPath()
    arrow.move(to: NSPoint(x: 262, y: 200))
    arrow.line(to: NSPoint(x: 390, y: 200))
    arrow.lineWidth = 5
    arrow.lineCapStyle = .round
    green.setStroke()
    arrow.stroke()
    let head = NSBezierPath()
    head.move(to: NSPoint(x: 376, y: 186))
    head.line(to: NSPoint(x: 396, y: 200))
    head.line(to: NSPoint(x: 376, y: 214))
    head.lineWidth = 5
    head.lineCapStyle = .round
    head.lineJoinStyle = .round
    head.stroke()

    // Riga sottile sopra le istruzioni.
    NSColor(calibratedWhite: 1, alpha: 0.10).setFill()
    NSRect(x: 60, y: 300, width: size.width - 120, height: 1).fill()

    NSGraphicsContext.restoreGraphicsState()
    try! rep.representation(using: .png, properties: [:])!.write(to: url)
}

render(scale: 1, to: out.appendingPathComponent("sfondo.png"))
render(scale: 2, to: out.appendingPathComponent("sfondo@2x.png"))
