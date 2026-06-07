// Protocole filaire du Trofeo Vision (HID « Type 2 »).
//
// Pur : aucune E/S, aucun IOKit. Port direct de `python/trofeo/protocol.py`, à
// partir des faits documentés dans `docs/PROTOCOL.md` (clean-room, MIT). C'est la
// couche entièrement testable du port Swift.

import Foundation

public enum TrofeoProtocol {

    // MARK: Constantes filaires

    public static let magic: [UInt8] = [0xDA, 0xDB, 0xDC, 0xDD]
    public static let initPacketSize = 512
    public static let usbAlign = 512
    public static let cmdDeviceInfo: UInt8 = 0x01
    public static let cmdPicture: UInt8 = 0x02
    public static let modeJPEG: UInt8 = 0x00
    public static let modeRGB565: UInt8 = 0x01

    public static func looksLikeJPEG(_ data: [UInt8]) -> Bool {
        data.count >= 2 && data[0] == 0xFF && data[1] == 0xD8
    }

    static func ceilToAlign(_ n: Int, _ align: Int) -> Int {
        ((n + align - 1) / align) * align
    }

    static func le16(_ v: UInt16) -> [UInt8] { [UInt8(v & 0xFF), UInt8((v >> 8) & 0xFF)] }
    static func le32(_ v: UInt32) -> [UInt8] {
        [UInt8(v & 0xFF), UInt8((v >> 8) & 0xFF), UInt8((v >> 16) & 0xFF), UInt8((v >> 24) & 0xFF)]
    }

    // MARK: Handshake / init

    /// Paquet d'init (512 o) : MAGIC | 8 zéros | cmd=1 (LE) | 4 zéros | padding.
    public static func buildInitPacket() -> [UInt8] {
        var h = magic
        h += [UInt8](repeating: 0, count: 8)
        h += [cmdDeviceInfo, 0, 0, 0]
        h += [UInt8](repeating: 0, count: 4)
        h += [UInt8](repeating: 0, count: initPacketSize - h.count)
        return h
    }

    /// PM byte → résolution. 128 et 68 → Trofeo Vision 1280×480 (confirmé : 128).
    static let pmResolution: [UInt8: (width: Int, height: Int)] = [
        128: (1280, 480),
        68: (1280, 480),
        69: (1920, 440),
    ]

    public struct Handshake {
        public let valid: Bool
        public let pm: UInt8?
        public let sub: UInt8?
        public let serial: String
        public let resolution: (width: Int, height: Int)?
        public let rawLen: Int
    }

    /// Valide et décode la réponse d'init. Critère : len ≥ 20, magic, resp[12]==1.
    /// Le serial occupe resp[20..<36] → il faut len ≥ 36 (pas > 36).
    public static func parseHandshake(_ resp: [UInt8]) -> Handshake {
        let valid = resp.count >= 20 && Array(resp[0..<4]) == magic && resp[12] == cmdDeviceInfo
        guard valid else {
            return Handshake(valid: false, pm: nil, sub: nil, serial: "", resolution: nil, rawLen: resp.count)
        }
        let pm = resp[5]
        let sub = resp[4]
        let hasSerial = resp.count >= 36 && resp[16] == 0x10
        let serial = hasSerial
            ? resp[20..<36].map { String(format: "%02X", $0) }.joined()
            : ""
        return Handshake(valid: true, pm: pm, sub: sub, serial: serial,
                         resolution: pmResolution[pm], rawLen: resp.count)
    }

    // MARK: Frame image

    /// Frame complète (header 20 o + image), paddée sur 512 o. Mode déduit du
    /// contenu : JPEG (FF D8) ou RGB565. Champs entiers en little-endian.
    public static func buildFrame(_ imageData: [UInt8], width: Int, height: Int) -> [UInt8] {
        let isJPEG = looksLikeJPEG(imageData)

        var header: [UInt8] = []
        header += magic
        header += [cmdPicture, 0x00]
        if isJPEG {
            header += [modeJPEG, 0x00]
            header += le16(UInt16(width))
            header += le16(UInt16(height))
        } else {
            header += [modeRGB565, 0x00]
            header += le16(240)
            header += le16(320)
        }
        header += [0x02, 0x00, 0x00, 0x00]
        header += le32(UInt32(imageData.count))

        var raw = header + imageData
        let target = ceilToAlign(raw.count, usbAlign)
        if target > raw.count {
            raw += [UInt8](repeating: 0, count: target - raw.count)
        }
        return raw
    }
}
