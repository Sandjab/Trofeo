// Rendu d'image (CoreGraphics + CoreText) et encodage JPEG (ImageIO).
//
// Équivalent Swift de `python/trofeo/render.py`. Produit des octets JPEG prêts pour
// `TrofeoProtocol.buildFrame`. Aucune dépendance AppKit : texte via CoreText,
// couleur de texte prise du contexte (kCTForegroundColorFromContextAttributeName).

import CoreGraphics
import CoreText
import Foundation
import ImageIO
import UniformTypeIdentifiers

public enum Render {

    public static let width = 1280
    public static let height = 480

    // MARK: Couleurs & contexte

    static func rgb(_ r: Int, _ g: Int, _ b: Int) -> CGColor {
        CGColor(srgbRed: CGFloat(r) / 255, green: CGFloat(g) / 255, blue: CGFloat(b) / 255, alpha: 1)
    }

    static func makeContext(_ w: Int, _ h: Int) -> CGContext {
        let ctx = CGContext(
            data: nil, width: w, height: h, bitsPerComponent: 8, bytesPerRow: 0,
            space: CGColorSpaceCreateDeviceRGB(),
            bitmapInfo: CGImageAlphaInfo.premultipliedLast.rawValue)!
        ctx.interpolationQuality = .high
        return ctx
    }

    enum TextAlign { case left, center, right }

    /// Dessine du texte. `topBaseline` = position de la ligne de base mesurée depuis
    /// le HAUT (sémantique PIL) ; on convertit vers le repère CG (origine bas-gauche).
    static func text(_ ctx: CGContext, _ s: String, x: CGFloat, topBaseline: CGFloat,
                     size: CGFloat, color: CGColor, align: TextAlign = .left) {
        let font = CTFontCreateWithName("HelveticaNeue" as CFString, size, nil)
        let attrs: [NSAttributedString.Key: Any] = [
            NSAttributedString.Key(kCTFontAttributeName as String): font,
            NSAttributedString.Key(kCTForegroundColorFromContextAttributeName as String): true,
        ]
        let line = CTLineCreateWithAttributedString(NSAttributedString(string: s, attributes: attrs))
        let w = CGFloat(CTLineGetTypographicBounds(line, nil, nil, nil))
        var penX = x
        switch align {
        case .left: penX = x
        case .center: penX = x - w / 2
        case .right: penX = x - w
        }
        ctx.setFillColor(color)
        ctx.textPosition = CGPoint(x: penX, y: CGFloat(height) - topBaseline)
        CTLineDraw(line, ctx)
    }

    static func fillRectTop(_ ctx: CGContext, x: CGFloat, top: CGFloat, w: CGFloat, h: CGFloat, _ color: CGColor) {
        ctx.setFillColor(color)
        ctx.fill(CGRect(x: x, y: CGFloat(height) - top - h, width: w, height: h))
    }

    // MARK: JPEG

    public static func jpeg(_ image: CGImage, quality: CGFloat = 0.9) -> Data {
        let out = NSMutableData()
        guard let dest = CGImageDestinationCreateWithData(
            out, UTType.jpeg.identifier as CFString, 1, nil) else { return Data() }
        CGImageDestinationAddImage(dest, image, [
            kCGImageDestinationLossyCompressionQuality: quality
        ] as CFDictionary)
        CGImageDestinationFinalize(dest)
        return out as Data
    }

    // MARK: Mire de test (sans texte garanti)

    public static func testPattern(_ w: Int = width, _ h: Int = height) -> CGImage {
        let ctx = makeContext(w, h)
        ctx.setFillColor(rgb(8, 8, 12)); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))

        let size = 90
        fillRectTop(ctx, x: 0, top: 0, w: CGFloat(size), h: CGFloat(size), rgb(255, 0, 0))            // TL rouge
        fillRectTop(ctx, x: CGFloat(w - size), top: 0, w: CGFloat(size), h: CGFloat(size), rgb(0, 255, 0))   // TR vert
        fillRectTop(ctx, x: 0, top: CGFloat(h - size), w: CGFloat(size), h: CGFloat(size), rgb(0, 0, 255))   // BL bleu
        fillRectTop(ctx, x: CGFloat(w - size), top: CGFloat(h - size), w: CGFloat(size), h: CGFloat(size), rgb(255, 255, 0)) // BR jaune

        // Triangle « HAUT » : apex vers le haut de l'écran (top).
        let cx = CGFloat(w) / 2
        ctx.setFillColor(rgb(255, 210, 0))
        ctx.beginPath()
        ctx.move(to: CGPoint(x: cx, y: CGFloat(height) - 150))      // apex (haut)
        ctx.addLine(to: CGPoint(x: cx - 70, y: CGFloat(height) - 300))
        ctx.addLine(to: CGPoint(x: cx + 70, y: CGFloat(height) - 300))
        ctx.closePath(); ctx.fillPath()

        text(ctx, "TROFEO \(w)x\(h)", x: cx, topBaseline: 40, size: 40, color: rgb(255, 255, 255), align: .center)
        return ctx.makeImage()!
    }

    // MARK: Dashboard

    static func barColor(_ frac: Double) -> CGColor {
        if frac < 0.75 { return rgb(90, 200, 140) }
        if frac < 0.90 { return rgb(230, 175, 70) }
        return rgb(230, 90, 90)
    }

    public static func dashboard(clock: String, date: String,
                                 bars: [(String, Double)] = [],
                                 lines: [(String, String)] = [],
                                 w: Int = width, h: Int = height) -> CGImage {
        let ctx = makeContext(w, h)
        ctx.setFillColor(rgb(12, 14, 22)); ctx.fill(CGRect(x: 0, y: 0, width: w, height: h))

        // Gauche : horloge + date.
        text(ctx, clock, x: 300, topBaseline: 255, size: 150, color: rgb(240, 242, 255), align: .center)
        text(ctx, date, x: 300, topBaseline: 335, size: 46, color: rgb(150, 165, 200), align: .center)

        // Séparateur.
        ctx.setStrokeColor(rgb(40, 44, 60)); ctx.setLineWidth(2)
        ctx.move(to: CGPoint(x: 600, y: CGFloat(height) - 50))
        ctx.addLine(to: CGPoint(x: 600, y: 50)); ctx.strokePath()

        // Droite : jauges puis lignes.
        let rx0: CGFloat = 650
        let rx1 = CGFloat(w - 50)
        var y: CGFloat = 88
        for (label, fracRaw) in bars {
            let frac = max(0.0, min(1.0, fracRaw))
            text(ctx, label, x: rx0, topBaseline: y, size: 40, color: rgb(170, 185, 215), align: .left)
            text(ctx, "\(Int(frac * 100))%", x: rx1, topBaseline: y, size: 40, color: rgb(240, 242, 255), align: .right)
            let barTop = y + 12
            fillRectTop(ctx, x: rx0, top: barTop, w: rx1 - rx0, h: 22, rgb(30, 34, 48))
            fillRectTop(ctx, x: rx0, top: barTop, w: (rx1 - rx0) * CGFloat(frac), h: 22, barColor(frac))
            y += 96
        }
        for (label, value) in lines {
            text(ctx, label, x: rx0, topBaseline: y, size: 40, color: rgb(170, 185, 215), align: .left)
            text(ctx, value, x: rx1, topBaseline: y, size: 40, color: rgb(220, 225, 240), align: .right)
            y += 58
        }
        return ctx.makeImage()!
    }
}
