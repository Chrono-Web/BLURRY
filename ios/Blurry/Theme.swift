import SwiftUI

// The same colours as the Mac app (macos/Sources/Blurry/Views.swift): Chrono's
// green and hairlines. Buttons are the system's own
// (bordered, bordered prominent, toolbar items), tinted green.
let accent = Color(red: 0x49 / 255, green: 0xDC / 255, blue: 0x18 / 255)
let hairline = Color.white.opacity(0.10)

/// Four L-shaped corner marks.
struct CornerTicks: Shape {
    var length: CGFloat = 12

    func path(in r: CGRect) -> Path {
        var p = Path()
        for (x, y, dx, dy) in [(r.minX, r.minY, 1.0, 1.0), (r.maxX, r.minY, -1.0, 1.0),
                               (r.minX, r.maxY, 1.0, -1.0), (r.maxX, r.maxY, -1.0, -1.0)] {
            p.move(to: CGPoint(x: x + dx * length, y: y))
            p.addLine(to: CGPoint(x: x, y: y))
            p.addLine(to: CGPoint(x: x, y: y + dy * length))
        }
        return p
    }
}

extension View {
    /// The one main action of a screen: the system's prominent button, large.
    /// Blurry's green is light, so the label is black for contrast.
    func primaryAction() -> some View {
        buttonStyle(.borderedProminent).controlSize(.large).foregroundStyle(.black)
    }

    /// The action beside it: the system's bordered button, large.
    func secondaryAction() -> some View {
        buttonStyle(.bordered).controlSize(.large)
    }
}

/// A label that fills the button's width, for the large actions at the bottom.
struct Wide: View {
    let text: String
    var symbol: String?

    init(_ text: String, systemImage: String? = nil) {
        self.text = text
        symbol = systemImage
    }

    var body: some View {
        Group {
            if let symbol { Label(text, systemImage: symbol) } else { Text(text) }
        }
        .fontWeight(.semibold)
        .frame(maxWidth: .infinity)
    }
}

/// One option of a choice.
struct Choice: Identifiable {
    let id: String
    let title: String
    let detail: String
    var symbol: String?
}

/// A choice as iOS shows it in Settings: an inset grouped list, one row per
/// option with its explanation, a checkmark on the chosen one.
struct ChoiceList: View {
    let choices: [Choice]
    let selected: String
    let select: (String) -> Void

    var body: some View {
        VStack(spacing: 0) {
            ForEach(Array(choices.enumerated()), id: \.element.id) { i, choice in
                Button { select(choice.id) } label: {
                    HStack(spacing: 12) {
                        if let symbol = choice.symbol {
                            Image(systemName: symbol)
                                .foregroundStyle(accent)
                                .frame(width: 24)
                        }
                        VStack(alignment: .leading, spacing: 2) {
                            Text(choice.title).foregroundStyle(.primary)
                            Text(choice.detail)
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 8)
                        if choice.id == selected {
                            Image(systemName: "checkmark")
                                .fontWeight(.semibold)
                                .foregroundStyle(accent)
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
                }
                .buttonStyle(RowButtonStyle())
                .accessibilityAddTraits(choice.id == selected ? .isSelected : [])
                if i < choices.count - 1 {
                    Divider().padding(.leading, choice.symbol == nil ? 16 : 52)
                }
            }
        }
        .background(Color(.secondarySystemGroupedBackground))
        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
    }
}

/// A list row's own highlight while pressed.
private struct RowButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.background(configuration.isPressed ? Color(.systemGray4) : Color.clear)
    }
}
