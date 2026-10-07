import Observation
import SwiftUI

/// Blurry as a small character, as on the Mac (macos/Sources/Blurry/MascotView.swift)
/// but without a pointer to follow: it greets, blinks and reacts to a nudge.
/// The face itself is the Mac's MascotFace.swift, compiled into this app as is.
@MainActor
@Observable
final class MascotModel {
    private(set) var animating = false
    let animator = MascotFace.Animator()
    @ObservationIgnored private var blinkTimer: Timer?
    @ObservationIgnored private var sleepWork: DispatchWorkItem?
    @ObservationIgnored private var ungreetWork: DispatchWorkItem?

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
        if greet {
            animator.setSmiling(now, true)
            wake()
            let work = DispatchWorkItem { [weak self] in
                MainActor.assumeIsolated {
                    guard let self else { return }
                    self.animator.setSmiling(self.now, false)
                    self.wake()
                }
            }
            ungreetWork = work
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.2, execute: work)
        }
    }

    func stop() {
        blinkTimer?.invalidate()
        blinkTimer = nil
        sleepWork?.cancel()
        sleepWork = nil
        ungreetWork?.cancel()
        animating = false
    }

    func nudge() {
        animator.blink(now, double: true)
        wake()
    }

    func frame(at t: Double) -> [Double] { animator.frame(t).greys }

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

struct MascotView: View {
    var greet = true
    var nudge = 0
    @State private var model = MascotModel()
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private static let cells = MascotFace.cells()

    var body: some View {
        TimelineView(.animation(minimumInterval: 1.0 / 30, paused: !model.animating)) { context in
            let greys = model.frame(at: context.date.timeIntervalSinceReferenceDate)
            Canvas { ctx, size in
                let cell = size.width / CGFloat(MascotFace.grid)
                let gap = cell * 9 / 74.3, radius = cell * 16 / 74.3
                for (c, v) in zip(Self.cells, greys) {
                    let rect = CGRect(x: CGFloat(c.col) * cell + gap / 2, y: CGFloat(c.row) * cell + gap / 2,
                                      width: cell - gap, height: cell - gap)
                    ctx.fill(Path(roundedRect: rect, cornerRadius: radius), with: .color(Color(white: min(1, max(0, v)))))
                }
            }
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityElement()
        .accessibilityLabel("Blurry")
        .onAppear {
            model.animator.reduceMotion = reduceMotion
            model.start(greet: greet)
        }
        .onDisappear { model.stop() }
        .onChange(of: nudge) { _, _ in model.nudge() }
    }
}
