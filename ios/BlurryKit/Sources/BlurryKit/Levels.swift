import Foundation

/// A detection level. The numbers come from src/blurry_opsec/levels.py, the
/// single source, through Resources/levels.json (scripts/coreml/levels_json.py).
public struct Level: Decodable, Equatable, Sendable {
    public let name: String
    public let confidence: Double
    /// Pixelation strength: blocks on the long side of the face.
    public let blocks: Int
    public let label: [String: String]
    public let description: [String: String]
}

public struct Levels: Decodable, Sendable {
    public let levels: [Level]
    public let defaultLevel: String
    public let mostSensitive: String
    public let defaultMode: String
    public let defaultPadding: Double
    public let modes: [String]
    public let yunetNms: Double
    public let yunetTopk: Int
    public let nearThresholdMargin: Double
    public let smallFacePx: Int

    public static let shared: Levels = {
        // A missing or broken resource is a build error, not a runtime condition.
        let url = Bundle.module.url(forResource: "levels", withExtension: "json")!
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try! decoder.decode(Levels.self, from: Data(contentsOf: url))
    }()

    public func get(_ name: String) throws -> Level {
        guard let level = levels.first(where: { $0.name == name }) else {
            throw LevelError.unknown(name)
        }
        return level
    }
}

public enum LevelError: Error, Equatable {
    case unknown(String)
}

/// How a face is covered.
public enum CoverMode: String, Sendable, CaseIterable {
    case solid   // black box (default)
    case pixel   // pixelation with the level's blocks
}
