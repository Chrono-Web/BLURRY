import XCTest
@testable import Blurry

/// Same face as the Qt app: these values are shared with tests/test_mascot.py.
final class MascotFaceTests: XCTestCase {
    private func grid(_ pose: MascotFace.Pose) -> [MascotFace.Cell: Double] {
        Dictionary(uniqueKeysWithValues: zip(MascotFace.cells(), MascotFace.values(pose)))
    }

    private func check(_ pose: MascotFace.Pose, _ expected: [(Int, Int, Double)], file: StaticString = #filePath,
                       line: UInt = #line) {
        let g = grid(pose)
        for (col, row, v) in expected {
            XCTAssertEqual(g[MascotFace.Cell(col: col, row: row)] ?? -1, v, accuracy: 0.002,
                           "cell \(col),\(row)", file: file, line: line)
        }
    }

    func testShapeIsTheIconMosaic() {
        XCTAssertEqual(MascotFace.cells().count, 61)
        XCTAssertFalse(MascotFace.inside(col: 0, row: 0))
        XCTAssertTrue(MascotFace.inside(col: 4, row: 0))
    }

    func testGoldenValues() {
        check(MascotFace.Pose(), [(2, 3, 0.799), (4, 3, 0.347), (6, 4, 0.767), (4, 0, 0.358)])
        check(MascotFace.Pose(smile: 1), [(2, 2, 0.808), (1, 3, 0.903), (3, 3, 0.877), (2, 4, 0.356)])
        check(MascotFace.Pose(open: 0), [(2, 3, 0.497), (6, 4, 0.436)])
        check(MascotFace.Pose(gazeX: 0.4), [(4, 3, 1.0), (7, 3, 1.0), (2, 3, 0.346)])
    }

    func testBlinkTiming() {
        XCTAssertEqual(MascotFace.eyeOpen(0, double: false), 1)
        XCTAssertEqual(MascotFace.eyeOpen(MascotFace.blink / 2, double: false), 0, accuracy: 1e-9)
        XCTAssertEqual(MascotFace.eyeOpen(MascotFace.doubleBlinkGap + MascotFace.blink / 2, double: true), 0,
                       accuracy: 1e-9)
    }

    func testAnimatorSleepsWhenStill() {
        let a = MascotFace.Animator()
        XCTAssertFalse(a.frame(0).moving)
        a.blink(1)
        XCTAssertTrue(a.frame(1.05).moving)
        var t = 1.05
        while a.frame(t).moving {
            t += 1.0 / 30
            XCTAssertLessThan(t, 3)
        }
        a.look(t, (0.2, 0))
        let until = a.activeUntil
        a.look(t + 0.1, (0.205, 0))
        XCTAssertEqual(a.activeUntil, until)
    }

    func testGreetingLooksAtViewer() {
        let a = MascotFace.Animator()
        a.look(0, (0.4, 0))
        a.setSmiling(0, true)
        var t = 0.0
        for _ in 0..<40 {
            t += 1.0 / 30
            _ = a.frame(t)
        }
        let pose = a.pose(t)
        XCTAssertEqual(pose.smile, 1, accuracy: 1e-9)
        XCTAssertLessThan(abs(pose.gazeX), 0.01)
    }
}
