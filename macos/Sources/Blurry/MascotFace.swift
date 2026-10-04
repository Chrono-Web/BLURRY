import Foundation

/// Blurry's face: a 9 × 9 mosaic whose cells are recomputed while it moves.
///
/// Every cell is the average of a few samples of a small sphere with two eyes,
/// so gaze, blinks and the greeting show up as cells fading between greys.
/// Port of `src/blurry_opsec/gui/mascot_face.py`: MascotFaceTests checks the
/// same values as `tests/test_mascot.py`.
enum MascotFace {
    static let grid = 9
    static let samples = 5

    // Sphere and eyes, angles in radians. The axis leans towards the viewer.
    static let tilt = 0.32
    static let eyeLon = 0.38
    static let eyeLat = 0.08 + tilt
    static let halfWidth = 0.115 * 1.25
    static let halfStraight = 0.19 * 1.25
    static let minOpen = 0.12  // a closed eye is still a thin slit

    // Greeting: eyes shut into wide arcs (^ ^), a little further apart.
    static let smileWidth = 2.5
    static let smileSpread = 0.14
    static let smileArch = 0.042 * 6
    static let smileSlit = 0.35

    static let glow = 0.45
    static let body = 0.7  // body greys relative to the app icon's
    static let turn = 0.3  // how much the shading follows the gaze

    // Timing.
    static let blink = 0.18
    static let doubleBlinkGap = 0.28
    static let blinkEvery: TimeInterval = 4
    static let smileDuration = 0.5
    static let gazeRate = 9.0
    static let fadeRate = 31.0
    static let gazeWake = 0.012

    struct Pose: Equatable {
        var gazeX = 0.0  // head turned right (radians)
        var gazeY = 0.0  // head turned up (radians)
        var open = 1.0   // 1 open, 0 shut by a blink
        var smile = 0.0  // 0 normal eyes, 1 greeting arcs
    }

    struct Cell: Hashable {
        let col: Int, row: Int
    }

    /// Whether a cell belongs to the round face (the corners stay empty).
    static func inside(col: Int, row: Int, n: Int = MascotFace.grid) -> Bool {
        let x = Double(col) + 0.5 - Double(n) / 2
        let y = Double(row) + 0.5 - Double(n) / 2
        return hypot(x, y) <= Double(n) / 2 - 0.2
    }

    /// The face's cells, row by row from the top left.
    static func cells(_ n: Int = MascotFace.grid) -> [Cell] {
        var out: [Cell] = []
        for row in 0..<n {
            for col in 0..<n where inside(col: col, row: row, n: n) {
                out.append(Cell(col: col, row: row))
            }
        }
        return out
    }

    /// Fixed per-cell variation in -0.5...0.5, as in the app icon.
    static func noise(_ col: Int, _ row: Int) -> Double {
        let v = sin(Double(col * 129_898 + row * 78_233)) * 43_758.5453
        return v - v.rounded(.down) - 0.5
    }

    private static func eyeCentres(_ pose: Pose) -> [(x: Double, y: Double)] {
        [-1.0, 1.0].map { side in
            let vx = cos(eyeLat) * sin(side * eyeLon)
            let vy = sin(eyeLat)
            let vz = cos(eyeLat) * cos(side * eyeLon)
            let x = vx * cos(pose.gazeX) + vz * sin(pose.gazeX)
            let z = -vx * sin(pose.gazeX) + vz * cos(pose.gazeX)
            let pitch = tilt - pose.gazeY
            return (x: x + side * smileSpread * pose.smile, y: vy * cos(pitch) - z * sin(pitch))
        }
    }

    private static func bodyTone(_ x: Double, _ y: Double, _ pose: Pose, _ nz: Double) -> Double {
        let k = turn * 1.6
        let g = min(2, max(0, ((x - pose.gazeX * k) - (y - pose.gazeY * k)) / 2 + 1)) / 2
        return max(0.2, 0.66 - 0.54 * g + nz * 0.08) * body
    }

    /// Grey (0 black … 1 white) of every cell, in the order of `cells(n)`.
    static func values(_ pose: Pose, n: Int = MascotFace.grid, samples: Int = MascotFace.samples) -> [Double] {
        let s = pose.smile
        let opened = pose.open * (1 - s)
        let w = halfWidth * max(1 + (smileWidth - 1) * s, 0.5)
        let squash = max(opened, minOpen + (smileSlit - minOpen) * s)
        let h = (halfStraight + halfWidth) * squash
        let arch = smileArch * s
        let rc = min(w, h)
        let centres = eyeCentres(pose)
        let side = 2 / Double(n)
        let count = Double(samples * samples)
        return cells(n).map { cell in
            let x0 = -1 + Double(cell.col) * side
            let y0 = 1 - Double(cell.row) * side
            let tone = bodyTone(x0 + side / 2, y0 - side / 2, pose, noise(cell.col, cell.row))
            var total = 0.0
            for j in 0..<samples {
                let y = y0 - (Double(j) + 0.5) / Double(samples) * side
                for i in 0..<samples {
                    let x = x0 + (Double(i) + 0.5) / Double(samples) * side
                    total += shade(x, y, tone, centres, w, h, rc, arch)
                }
            }
            return total / count
        }
    }

    private static func shade(_ x: Double, _ y: Double, _ tone: Double, _ centres: [(x: Double, y: Double)],
                              _ w: Double, _ h: Double, _ rc: Double, _ arch: Double) -> Double {
        guard x * x + y * y < 1 else { return tone }
        var fill = 0.0, halo = 0.0
        for e in centres {
            let u = x - e.x
            let un = min(1, max(-1, u / w))
            let dl = y - e.y - arch * (1 - un * un)
            // Rounded rectangle: width and height are independent, so a wider
            // greeting does not make the eyes taller.
            let qx = abs(u) - (w - rc), qy = abs(dl) - (h - rc)
            let sd = hypot(max(qx, 0), max(qy, 0)) + min(max(qx, qy), 0) - rc
            if sd <= 0 { fill = 1 }
            let d = max(0, sd) / 0.13
            halo = max(halo, exp(-(d * d)))
        }
        let v = tone * (1 - fill) + fill
        return v + (1 - v) * glow * 0.6 * halo * (1 - fill)
    }

    /// How open the eyes are `elapsed` seconds after a blink starts.
    static func eyeOpen(_ elapsed: Double, double: Bool) -> Double {
        func one(_ start: Double) -> Double {
            let d = elapsed - start
            guard d >= 0, d < blink else { return 1 }
            return abs(d - blink / 2) / (blink / 2)
        }
        return min(one(0), double ? one(doubleBlinkGap) : 1)
    }

    /// Head turn towards a point `dx`, `dy` points away (y grows downwards).
    static func gazeGoal(dx: Double, dy: Double, falloff: Double = 500, reach: Double = 0.45) -> (Double, Double) {
        let dist = max(hypot(dx, dy), 1)
        let a = min(dist / falloff, 1) * reach
        return (dx / dist * a, -dy / dist * a * 0.7)
    }

    /// Blinks, greeting and a damped gaze, driven by the caller's clock. It only
    /// says what to draw at time `t` and how long drawing must go on
    /// (`activeUntil`); the view decides when to repaint, and stops when idle.
    final class Animator {
        let n: Int
        var blinkStart = -1e9
        var double = false
        var blinks = 0
        var smileFrom = 0.0, smileTo = 0.0, smileStart = -1e9
        private(set) var smiling = false
        var gaze = (x: 0.0, y: 0.0)
        var goal = (x: 0.0, y: 0.0)
        private var lastGoal: (x: Double, y: Double)?
        var lastT: Double?
        private(set) var shown: [Double]?
        private(set) var settling = false
        private(set) var activeUntil = 0.0
        var reduceMotion = false

        init(n: Int = MascotFace.grid) { self.n = n }

        func wake(_ t: Double, _ duration: Double) {
            activeUntil = max(activeUntil, t + duration)
        }

        func blink(_ t: Double, double: Bool = false) {
            guard !reduceMotion else { return }
            blinkStart = t
            self.double = double
            wake(t, double ? 0.5 : 0.25)
        }

        /// The regular blink: every third one is double.
        func tickBlink(_ t: Double) {
            blinks += 1
            blink(t, double: blinks % 3 == 0)
        }

        func smileAmount(_ t: Double) -> Double {
            let u = min(1, max(0, (t - smileStart) / MascotFace.smileDuration))
            return smileFrom + (smileTo - smileFrom) * u * u * (3 - 2 * u)
        }

        func setSmiling(_ t: Double, _ on: Bool) {
            smileFrom = smileAmount(t)
            smileTo = on ? 1 : 0
            smileStart = t
            smiling = on
            wake(t, MascotFace.smileDuration + 0.15)
        }

        /// New gaze target; wakes the view only if the change is visible.
        func look(_ t: Double, _ target: (Double, Double)) {
            goal = (target.0, target.1)
            if let last = lastGoal, hypot(target.0 - last.x, target.1 - last.y) < MascotFace.gazeWake { return }
            lastGoal = (target.0, target.1)
            wake(t, 0.8)
        }

        func pose(_ t: Double) -> Pose {
            let dt = min(t - (lastT ?? t), 0.1)
            lastT = t
            if reduceMotion { return Pose(smile: smiling ? 1 : 0) }
            let smile = smileAmount(t)
            let target = smile > 0.12 ? (x: 0.0, y: 0.0) : goal
            let k = min(1, dt * MascotFace.gazeRate)
            gaze = (gaze.x + (target.x - gaze.x) * k, gaze.y + (target.y - gaze.y) * k)
            return Pose(gazeX: gaze.x, gazeY: gaze.y, open: MascotFace.eyeOpen(t - blinkStart, double: double),
                        smile: smile)
        }

        /// Greys to draw now, and whether anything is still moving.
        func frame(_ t: Double) -> (greys: [Double], moving: Bool) {
            let dt = min(t - (lastT ?? t), 0.1)
            let target = MascotFace.values(pose(t), n: n)
            guard let old = shown, !reduceMotion else {
                shown = target
                settling = false
                return (target, t < activeUntil)
            }
            let a = min(1, dt * MascotFace.fadeRate)
            var moving = false
            let next = zip(old, target).map { was, new -> Double in
                let v = was + (new - was) * a
                if abs(new - v) > 0.003 { moving = true; return v }
                return new
            }
            shown = next
            settling = moving
            return (next, moving || t < activeUntil)
        }
    }
}
