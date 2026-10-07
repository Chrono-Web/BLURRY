import CoreML
import CryptoKit
import Foundation

/// The bundled YuNet model (MIT, Shiqi Yu, OpenCV Zoo), converted to Core ML fp32
/// by scripts/coreml/modello.sh. Requirement R5: the hash is pinned here and
/// checked before the model is loaded. There is no fallback detector.
public enum Model {
    /// scripts/coreml/model_hash.py prints it after a new conversion.
    static let sha256 = "0ecfe261dcb767670a571cda97476cd2bc2d7dfef622cc535e8514130a8bbb99"

    static var url: URL? { Bundle.module.url(forResource: "YuNet", withExtension: "mlmodelc") }

    /// For every file, in order of relative path: the path, a zero byte, the
    /// size as 8 bytes little-endian, the contents (same as model_hash.py).
    static func folderHash(_ folder: URL) throws -> String {
        let root = folder.standardizedFileURL.resolvingSymlinksInPath()
        var files: [(String, URL)] = []
        let walker = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.isRegularFileKey])
        while let url = walker?.nextObject() as? URL {
            guard try url.resourceValues(forKeys: [.isRegularFileKey]).isRegularFile == true else { continue }
            let path = url.standardizedFileURL.resolvingSymlinksInPath().path
            files.append((String(path.dropFirst(root.path.count + 1)), url))
        }
        var hasher = SHA256()
        for (rel, url) in files.sorted(by: { $0.0 < $1.0 }) {
            let data = try Data(contentsOf: url)
            hasher.update(data: Data(rel.utf8) + [0])
            withUnsafeBytes(of: UInt64(data.count).littleEndian) { hasher.update(bufferPointer: $0) }
            hasher.update(data: data)
        }
        return hasher.finalize().map { String(format: "%02x", $0) }.joined()
    }

    public static func loadVerified(computeUnits: MLComputeUnits = .all) throws -> MLModel {
        guard let url, FileManager.default.fileExists(atPath: url.path) else {
            throw ModelIntegrityError.missing
        }
        guard try folderHash(url) == sha256 else { throw ModelIntegrityError.mismatch }
        let config = MLModelConfiguration()
        config.computeUnits = computeUnits
        return try MLModel(contentsOf: url, configuration: config)
    }
}

public enum ModelIntegrityError: Error, Equatable, CustomStringConvertible {
    case missing, mismatch

    public var description: String {
        switch self {
        case .missing: "the face detection model is missing; reinstall Blurry"
        case .mismatch: "the face detection model does not match the expected SHA-256; "
            + "reinstall Blurry from a verified download"
        }
    }
}
