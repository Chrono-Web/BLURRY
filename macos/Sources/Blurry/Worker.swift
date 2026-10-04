import Foundation

/// The Python engine as a child process: `blurry __worker`, one JSON object
/// per line in each direction (protocol in src/blurry_opsec/worker.py).
/// Requests are processed one at a time, in order.
@MainActor
final class Worker {
    enum Event {
        case progress(done: Int, total: Int)
        case frame(index: Int, preview: String)
        case result([String: Any])
        case error(String)
        case cancelled
    }

    private var process: Process?
    private var input: FileHandle?
    private var buffer = Data()
    private var handlers: [Int: (Event) -> Void] = [:]
    private var nextID = 1
    private var quitting = false
    private var restarts = 0
    private static let maxRestarts = 3

    /// Set when the engine cannot be started at all.
    private(set) var unavailable = false
    var onCrash: (() -> Void)?

    var busy: Bool { !handlers.isEmpty }

    init() { start() }

    /// In development BLURRY_PYTHON points at the project's interpreter; the
    /// packaged app carries the frozen engine in Resources/engine/blurry.
    ///
    /// Never look the engine up by name next to the app's own executable: the
    /// disk is case-insensitive, so "blurry" would find "Blurry", the app would
    /// start copies of itself as its engine and each copy two more (this
    /// happened on 2026-10-04 and exhausted the Mac's processes).
    private static func command() -> (URL, [String])? {
        if let python = ProcessInfo.processInfo.environment["BLURRY_PYTHON"] {
            return (URL(fileURLWithPath: python), ["-m", "blurry_opsec", "__worker"])
        }
        guard let engine = Bundle.main.resourceURL?.appendingPathComponent("engine/blurry"),
              FileManager.default.isExecutableFile(atPath: engine.path),
              !isSelf(engine) else { return nil }
        return (engine, ["__worker"])
    }

    private static func isSelf(_ url: URL) -> Bool {
        guard let me = Bundle.main.executableURL else { return true }
        let key: Set<URLResourceKey> = [.fileResourceIdentifierKey]
        let a = try? url.resolvingSymlinksInPath().resourceValues(forKeys: key).fileResourceIdentifier
        let b = try? me.resolvingSymlinksInPath().resourceValues(forKeys: key).fileResourceIdentifier
        guard let a, let b else { return true }
        return a.isEqual(b)
    }

    private func start() {
        guard let (exe, args) = Self.command() else {
            unavailable = true
            return
        }
        let proc = Process()
        proc.executableURL = exe
        proc.arguments = args
        let stdout = Pipe(), stdin = Pipe()
        proc.standardOutput = stdout
        proc.standardInput = stdin
        proc.standardError = FileHandle.standardError
        stdout.fileHandleForReading.readabilityHandler = { [weak self] handle in
            let data = handle.availableData
            if data.isEmpty { handle.readabilityHandler = nil }
            DispatchQueue.main.async { MainActor.assumeIsolated { self?.receive(data) } }
        }
        proc.terminationHandler = { [weak self] _ in
            DispatchQueue.main.async { MainActor.assumeIsolated { self?.terminated() } }
        }
        do {
            try proc.run()
        } catch {
            unavailable = true
            return
        }
        process = proc
        input = stdin.fileHandleForWriting
        buffer = Data()
        // A healthy start resets the count after a while.
        DispatchQueue.main.asyncAfter(deadline: .now() + 30) { [weak self] in
            MainActor.assumeIsolated { if self?.process === proc { self?.restarts = 0 } }
        }
    }

    @discardableResult
    func request(_ cmd: String, _ payload: [String: Any], _ handler: @escaping (Event) -> Void) -> Int {
        let id = nextID
        nextID += 1
        handlers[id] = handler
        var msg = payload
        msg["id"] = id
        msg["cmd"] = cmd
        send(msg)
        return id
    }

    func cancel() { send(["cmd": "cancel"]) }

    func shutdown() {
        quitting = true
        guard let proc = process, proc.isRunning else { return }
        send(["cmd": "cancel"])
        send(["cmd": "quit"])
        try? input?.close()
        let deadline = Date().addingTimeInterval(3)
        while proc.isRunning && Date() < deadline { usleep(20_000) }
        if proc.isRunning { proc.terminate() }
    }

    private func send(_ msg: [String: Any]) {
        guard let input, var data = try? JSONSerialization.data(withJSONObject: msg) else { return }
        data.append(0x0A)
        try? input.write(contentsOf: data)
    }

    private func receive(_ data: Data) {
        buffer.append(data)
        while let nl = buffer.firstIndex(of: 0x0A) {
            let line = buffer[buffer.startIndex..<nl]
            buffer = Data(buffer[buffer.index(after: nl)...])
            guard let obj = try? JSONSerialization.jsonObject(with: line) as? [String: Any] else { continue }
            dispatch(obj)
        }
    }

    private func dispatch(_ msg: [String: Any]) {
        guard let id = msg["id"] as? Int, let handler = handlers[id] else { return }
        switch msg["event"] as? String {
        case "progress":
            handler(.progress(done: msg["done"] as? Int ?? 0, total: msg["total"] as? Int ?? 0))
            return
        case "frame":
            handler(.frame(index: msg["index"] as? Int ?? 0, preview: msg["preview"] as? String ?? ""))
            return
        case "result":
            handlers[id] = nil
            handler(.result(msg))
        case "error":
            handlers[id] = nil
            handler(.error(msg["message"] as? String ?? "error"))
        case "cancelled":
            handlers[id] = nil
            handler(.cancelled)
        default:
            return
        }
    }

    private func terminated() {
        process = nil
        input = nil
        if quitting { return }
        let pending = handlers
        handlers = [:]
        for handler in pending.values { handler(.error("worker")) }
        onCrash?()
        // Restart a few times, waiting longer each time; then give up and say so,
        // instead of starting processes forever.
        guard restarts < Self.maxRestarts else {
            unavailable = true
            return
        }
        restarts += 1
        let delay = pow(2.0, Double(restarts - 1))
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { MainActor.assumeIsolated { self.start() } }
    }
}
