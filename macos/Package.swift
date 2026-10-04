// swift-tools-version:5.10
// The macOS app: a SwiftUI shell over the Python engine, which runs as a
// separate worker process (blurry __worker, JSON lines over pipes).
import PackageDescription

let package = Package(
    name: "Blurry",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(name: "Blurry", path: "Sources/Blurry"),
    ]
)
