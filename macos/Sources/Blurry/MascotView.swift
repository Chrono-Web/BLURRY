import AppKit
import Observation
import SwiftUI

/// Blurry as a small character: the app icon's mosaic, alive. It blinks,
/// follows the pointer and greets when it appears. The render loop runs only
/// while something moves, and Reduce Motion keeps it still.
@MainActor
@Observable
final class MascotModel {
    private(set) var animating = false
    let animator = MascotFace.Animator()
    @ObservationIgnored weak var anchor: NSView?
    @ObservationIgnored private var blinkTimer: Timer?
    @ObservationIgnored private var sleepWork: DispatchWorkItem?
    @ObservationIgnored private var ungreetWork: DispatchWorkItem?
    @ObservationIgnored private var monitors: [Any] = []

    private var now: Double { Date.timeIntervalSinceReferenceDate }

    func start(greet: Bool) {
        guard blinkTimer == nil else { return }
        animator.lastT = nil
        blinkTimer = Timer.scheduledTimer(withTimeInterval: MascotFace.blinkEvery, repeats: true) { [weak self] _ in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.animator.tickBlink(self.now)
                self.wake()
            }
        }
        let handler: (NSEvent) -> Void = { [weak self] _ in
            MainActor.assumeIsolated { self?.pointerMoved() }
        }
        if let global = NSEvent.addGlobalMonitorForEvents(matching: [.mouseMoved, .leftMouseDragged], handler: handler) {
            monitors.append(global)
        }
        if let local = NSEvent.addLocalMonitorForEvents(matching: [.mouseMoved, .leftMouseDragged],
                                                        handler: { handler($0); return $0 }) {
            monitors.append(local)
        }
        if greet {
            setSmiling(true)
            let work = DispatchWorkItem { [weak self] in MainActor.assumeIsolated { self?.setSmiling(false) } }
            ungreetWork = work
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.4, execute: work)
        }
        wake(1)
    }

    func stop() {
        blinkTimer?.invalidate()
        blinkTimer = nil
        monitors.forEach(NSEvent.removeMonitor)
        monitors = []
        sleepWork?.cancel()
        sleepWork = nil
        ungreetWork?.cancel()
        if animator.smiling { animator.setSmiling(now, false) }
        animating = false
    }

    func setSmiling(_ on: Bool) {
        animator.setSmiling(now, on)
        wake()
    }

    /// A small reaction, for example when the page beside it changes.
    func nudge() {
        animator.blink(now, double: true)
        wake()
    }

    func frame(at t: Double) -> [Double] {
        animator.frame(t).greys
    }

    private func pointerMoved() {
        guard let view = anchor, let window = view.window else { return }
        let frame = window.convertToScreen(view.convert(view.bounds, to: nil))
        let mouse = NSEvent.mouseLocation
        // Screen coordinates grow upwards; the gaze wants y growing downwards.
        animator.look(now, MascotFace.gazeGoal(dx: mouse.x - frame.midX, dy: frame.midY - mouse.y))
        wake()
    }

    /// Keeps the render loop on for `duration` seconds, or for as long as the
    /// animator asked; then pauses it once every cell has settled.
    func wake(_ duration: Double = 0) {
        let t = now
        if duration > 0 { animator.wake(t, duration) }
        guard animator.activeUntil > t else { return }
        if !animating { animating = true }
        if sleepWork == nil { scheduleSleep() }
    }

    private func scheduleSleep() {
        let delay = max(animator.activeUntil - now, 0) + 0.05
        let work = DispatchWorkItem { [weak self] in
            MainActor.assumeIsolated {
                guard let self else { return }
                self.sleepWork = nil
                if self.animator.activeUntil > self.now || self.animator.settling {
                    self.scheduleSleep()
                } else {
                    self.animating = false
                }
            }
        }
        sleepWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: work)
    }
}

@MainActor
struct MascotView: View {
    var greet = true
    /// Changing this value makes Blurry blink twice.
    var nudge = 0
    @State private var model = MascotModel()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private static let cells = MascotFace.cells()

    var body: some View {
        // With ProMotion the loop would run at 120 Hz: 30 are enough for gaze and blinks.
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: !model.animating)) { context in
            let greys = model.frame(at: context.date.timeIntervalSinceReferenceDate)
            let cells = Self.cells
            Canvas { ctx, size in
                let cell = size.width / CGFloat(MascotFace.grid)
                let gap = cell * 9 / 74.3, radius = cell * 16 / 74.3
                for (c, v) in zip(cells, greys) {
                    let rect = CGRect(x: CGFloat(c.col) * cell + gap / 2, y: CGFloat(c.row) * cell + gap / 2,
                                      width: cell - gap, height: cell - gap)
                    let grey = Color(white: min(1, max(0, v)))
                    ctx.fill(Path(roundedRect: rect, cornerRadius: radius), with: .color(grey))
                }
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .background(MascotAnchor(model: model))
        .accessibilityElement()
        .accessibilityLabel("Blurry")
        .onAppear {
            model.animator.reduceMotion = reduceMotion
            model.start(greet: greet)
        }
        .onDisappear { model.stop() }
        .onChange(of: reduceMotion) { _, on in
            model.animator.reduceMotion = on
            model.wake(0.1)
        }
        .onChange(of: nudge) { _, _ in model.nudge() }
    }
}

/// Gives the model the view's place on screen, so the eyes can find the pointer.
private struct MascotAnchor: NSViewRepresentable {
    let model: MascotModel

    func makeNSView(context: Context) -> NSView {
        let view = NSView()
        model.anchor = view
        return view
    }

    func updateNSView(_ nsView: NSView, context: Context) {
        model.anchor = nsView
    }
}
