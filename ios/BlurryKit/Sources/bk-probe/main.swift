// Time and peak memory of reading and detecting one image (PIANO_BLURRY 5a,
// VERIFICA memoria). The peak is the process's physical footprint, the number
// iOS uses to decide when to kill an app.
//
//   swift run -c release bk-probe <image> [cpu|all]
import BlurryKit
import CoreML
import Darwin
import Foundation

func footprint() -> (now: UInt64, peak: UInt64) {
    var info = task_vm_info_data_t()
    var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
    let kr = withUnsafeMutablePointer(to: &info) {
        $0.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
            task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
        }
    }
    return kr == KERN_SUCCESS ? (info.phys_footprint, UInt64(max(0, info.ledger_phys_footprint_peak))) : (0, 0)
}

func mb(_ bytes: UInt64) -> String { String(format: "%.0f MB", Double(bytes) / 1_048_576) }

let args = CommandLine.arguments
guard args.count >= 2 else {
    FileHandle.standardError.write(Data("usage: bk-probe <image> [cpu|all]\n".utf8))
    exit(2)
}
let units: MLComputeUnits = args.count > 2 && args[2] == "cpu" ? .cpuOnly : .all
do {
    let detector = try FaceDetector(level: Levels.shared.mostSensitive, computeUnits: units)
    let base = footprint()
    var t = Date()
    let loaded = try ImageIn.load(url: URL(fileURLWithPath: args[1]))
    let loadTime = Date().timeIntervalSince(t)
    let afterLoad = footprint()
    t = Date()
    let boxes = try detector.detect(loaded.rgb)
    let detectTime = Date().timeIntervalSince(t)
    let end = footprint()
    let mp = Double(loaded.rgb.width * loaded.rgb.height) / 1e6
    print(String(format: "%dx%d (%.0f MP), %d faces | read %.2fs, detect %.2fs | ",
                 loaded.rgb.width, loaded.rgb.height, mp, boxes.count, loadTime, detectTime)
          + "footprint: start \(mb(base.now)), after read \(mb(afterLoad.now)), peak \(mb(end.peak))")
} catch {
    FileHandle.standardError.write(Data("bk-probe: \(error)\n".utf8))
    exit(1)
}
