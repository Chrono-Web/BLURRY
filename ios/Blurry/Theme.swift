import SwiftUI

// The same look as the Mac app (macos/Sources/Blurry/Views.swift): Chrono's
// green, hairlines, small monospace capitals, one white primary button.
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

struct SectionLabel: View {
    let text: String

    var body: some View {
        Text(text)
            .font(.system(size: 10, weight: .medium, design: .monospaced))
            .tracking(1.5)
            .foregroundStyle(.secondary)
    }
}

/// White button with black text: the one primary action.
struct PrimaryButtonStyle: ButtonStyle {
    @Environment(\.isEnabled) private var enabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.semibold))
            .frame(maxWidth: .infinity)
            .padding(.vertical, 13)
            .foregroundStyle(enabled ? Color.black : Color.white.opacity(0.35))
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(enabled ? Color.white.opacity(configuration.isPressed ? 0.8 : 1) : Color.white.opacity(0.08))
            )
    }
}

/// The secondary action beside it.
struct SecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.body.weight(.medium))
            .padding(.vertical, 13)
            .padding(.horizontal, 18)
            .foregroundStyle(.white)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.white.opacity(configuration.isPressed ? 0.16 : 0.08))
            )
    }
}

/// One choice in a step: a card, green when chosen.
struct OptionCard: View {
    let title: String
    let hint: String
    var symbol: String?
    let selected: Bool
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(alignment: .top, spacing: 10) {
                if let symbol {
                    Image(systemName: symbol)
                        .font(.system(size: 15))
                        .foregroundStyle(selected ? accent : .secondary)
                        .frame(width: 20)
                }
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).font(.callout.weight(.medium))
                    Text(hint)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }
            .padding(12)
            .frame(maxWidth: .infinity, minHeight: 64, alignment: .topLeading)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.white.opacity(selected ? 0.07 : 0.025))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(selected ? accent.opacity(0.85) : hairline, lineWidth: 1)
            )
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
        .animation(.easeOut(duration: 0.12), value: selected)
    }
}
