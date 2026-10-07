// swift-tools-version:5.10
// BlurryKit: the engine of the iOS app, in Swift. The Python engine
// (src/blurry_opsec) stays the reference: the parity tests compare the two
// (prepare them with scripts/coreml/test-kit.sh).
import PackageDescription

let package = Package(
    name: "BlurryKit",
    platforms: [.iOS(.v17), .macOS(.v14)],   // macOS only for tests and bk-probe
    products: [
        .library(name: "BlurryKit", targets: ["BlurryKit"]),
    ],
    targets: [
        .target(
            name: "BlurryKit",
            resources: [
                .copy("Resources/YuNet.mlmodelc"),
                .copy("Resources/YuNet-LICENSE"),
                .copy("Resources/levels.json"),
            ]
        ),
        // Detection time and peak memory on one image (PIANO_BLURRY 5a, VERIFICA memoria).
        .executableTarget(name: "bk-probe", dependencies: ["BlurryKit"]),
        .testTarget(name: "BlurryKitTests", dependencies: ["BlurryKit"]),
    ]
)
