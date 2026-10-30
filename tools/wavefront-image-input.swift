// Deterministic workload preparation, outside all engine timing. macOS only.
import Foundation
import CoreGraphics
import ImageIO

func fail(_ message: String) -> Never {
    fputs(message + "\n", stderr)
    exit(2)
}

guard CommandLine.arguments.count == 5,
      let width = Int(CommandLine.arguments[2]), let height = Int(CommandLine.arguments[3]),
      width > 0, height > 0, width <= 8192, height <= 8192 else {
    fail("usage: wavefront-image-input IMAGE WIDTH HEIGHT OUTPUT.rgba32f")
}
let sourceURL = URL(fileURLWithPath: CommandLine.arguments[1])
guard let source = CGImageSourceCreateWithURL(sourceURL as CFURL, nil),
      let image = CGImageSourceCreateImageAtIndex(source, 0, nil),
      let space = CGColorSpace(name: CGColorSpace.extendedLinearITUR_2020) else {
    fail("image decode or Rec.2020 color space unavailable")
}
let properties = CGImageSourceCopyPropertiesAtIndex(source, 0, nil) as? [CFString: Any]
let orientation = (properties?[kCGImagePropertyOrientation] as? NSNumber)?.intValue ?? 1
guard orientation == 1 else { fail("normalize EXIF orientation before corpus preparation") }
var rgba = [Float](repeating: 0, count: width * height * 4)
rgba.withUnsafeMutableBytes { bytes in
    let info = CGBitmapInfo.floatComponents.rawValue | CGBitmapInfo.byteOrder32Little.rawValue
        | CGImageAlphaInfo.premultipliedLast.rawValue
    guard let context = CGContext(data: bytes.baseAddress, width: width, height: height,
                                  bitsPerComponent: 32, bytesPerRow: width * 16,
                                  space: space, bitmapInfo: info) else { fail("float CGContext unavailable") }
    context.setFillColor(CGColor(gray: 0, alpha: 1))
    context.fill(CGRect(x: 0, y: 0, width: width, height: height))
    context.interpolationQuality = image.width == width && image.height == height ? .none : .high
    // Aspect-cover crop. Small source images are upscaled workload fixtures,
    // not native-resolution quality evidence or recovered scene-linear HDR.
    let scale = max(Double(width) / Double(image.width), Double(height) / Double(image.height))
    let drawWidth = Double(image.width) * scale, drawHeight = Double(image.height) * scale
    context.draw(image, in: CGRect(x: (Double(width)-drawWidth)/2, y: (Double(height)-drawHeight)/2,
                                  width: drawWidth, height: drawHeight))
}
guard rgba.allSatisfy({ $0.isFinite }) else { fail("non-finite converted input") }
for i in stride(from: 3, to: rgba.count, by: 4) {
    guard rgba[i] == 1 else { fail("the photo corpus must be opaque") }
}
let data = rgba.withUnsafeBytes { Data($0) }
do { try data.write(to: URL(fileURLWithPath: CommandLine.arguments[4]), options: .atomic) }
catch { fail("input write failed: \(error.localizedDescription)") }
print("linear Rec.2020 float RGBA; source=\(image.width)x\(image.height); workload=\(width)x\(height)")
