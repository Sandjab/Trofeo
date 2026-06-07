// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "TrofeoKit",
    platforms: [.macOS(.v12)],
    products: [
        .library(name: "TrofeoKit", targets: ["TrofeoKit"]),
        .executable(name: "trofeo-cli", targets: ["trofeo-cli"]),
    ],
    targets: [
        .target(
            name: "TrofeoKit",
            linkerSettings: [
                .linkedFramework("IOKit"),
                .linkedFramework("CoreGraphics"),
                .linkedFramework("ImageIO"),
                .linkedFramework("CoreText"),
                .linkedFramework("CoreFoundation"),
            ]
        ),
        .executableTarget(name: "trofeo-cli", dependencies: ["TrofeoKit"]),
        .testTarget(name: "TrofeoKitTests", dependencies: ["TrofeoKit"]),
    ]
)
