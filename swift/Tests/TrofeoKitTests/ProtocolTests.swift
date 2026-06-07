// Tests du protocole filaire — purs, sans matériel. Miroir de
// python/tests/test_protocol.py. Chaque test encode *pourquoi* l'octet compte.

import XCTest
@testable import TrofeoKit

final class ProtocolTests: XCTestCase {

    // MARK: Init / handshake

    func testInitPacketShape() {
        let pkt = TrofeoProtocol.buildInitPacket()
        XCTAssertEqual(pkt.count, TrofeoProtocol.initPacketSize)
        XCTAssertEqual(Array(pkt[0..<4]), TrofeoProtocol.magic)
        XCTAssertEqual(pkt[12], TrofeoProtocol.cmdDeviceInfo)
        XCTAssertEqual(Array(pkt[16...]), [UInt8](repeating: 0, count: TrofeoProtocol.initPacketSize - 16))
    }

    private func fakeResponse(pm: UInt8 = 128, sub: UInt8 = 0, serial: [UInt8]? = nil) -> [UInt8] {
        var resp = [UInt8](repeating: 0, count: 512)
        resp[0] = TrofeoProtocol.magic[0]; resp[1] = TrofeoProtocol.magic[1]
        resp[2] = TrofeoProtocol.magic[2]; resp[3] = TrofeoProtocol.magic[3]
        resp[4] = sub
        resp[5] = pm
        resp[12] = TrofeoProtocol.cmdDeviceInfo
        if let serial {
            resp[16] = 0x10
            for (i, b) in serial.enumerated() { resp[20 + i] = b }
        }
        return resp
    }

    func testParseHandshakeValidPM128() {
        let hs = TrofeoProtocol.parseHandshake(fakeResponse(pm: 128))
        XCTAssertTrue(hs.valid)
        XCTAssertEqual(hs.pm, 128)
        XCTAssertEqual(hs.resolution?.width, 1280)
        XCTAssertEqual(hs.resolution?.height, 480)
    }

    func testParseHandshakeRejectsBadMagic() {
        var bad = fakeResponse()
        bad[0] = 0x00
        let hs = TrofeoProtocol.parseHandshake(bad)
        XCTAssertFalse(hs.valid)
        XCTAssertNil(hs.resolution?.width)
    }

    func testParseHandshakeRejectsWrongCmd() {
        var bad = fakeResponse()
        bad[12] = 0x02
        XCTAssertFalse(TrofeoProtocol.parseHandshake(bad).valid)
    }

    func testParseHandshakeExtractsSerial() {
        let serial = Array<UInt8>(0..<16)
        let hs = TrofeoProtocol.parseHandshake(fakeResponse(serial: serial))
        XCTAssertEqual(hs.serial, serial.map { String(format: "%02X", $0) }.joined())
    }

    func testParseHandshakeTooShort() {
        XCTAssertFalse(TrofeoProtocol.parseHandshake([0xDA, 0xDB]).valid)
    }

    /// Réponse RÉELLE capturée sur le Trofeo Vision V1.02 (36 octets). Verrouille
    /// PM=128, sub=1, résolution 1280×480 et l'extraction du serial (off-by-one >36/>=36).
    func testParseHandshakeRealTrofeoVision() {
        let hex = "dadbdcdd018000000000000001000000100000004250304b3837340e00a1af1a4302d778"
        var real = [UInt8]()
        var i = hex.startIndex
        while i < hex.endIndex {
            let j = hex.index(i, offsetBy: 2)
            real.append(UInt8(hex[i..<j], radix: 16)!)
            i = j
        }
        XCTAssertEqual(real.count, 36)
        let hs = TrofeoProtocol.parseHandshake(real)
        XCTAssertTrue(hs.valid)
        XCTAssertEqual(hs.pm, 128)
        XCTAssertEqual(hs.sub, 1)
        XCTAssertEqual(hs.resolution?.width, 1280)
        XCTAssertEqual(hs.resolution?.height, 480)
        XCTAssertEqual(hs.serial, "4250304B3837340E00A1AF1A4302D778")
        XCTAssertEqual(hs.rawLen, 36)
    }

    // MARK: Frame

    private let fakeJPEG: [UInt8] = [0xFF, 0xD8] + [UInt8](repeating: 0x11, count: 100) + [0xFF, 0xD9]

    func testFrameHeaderLayoutJPEG() {
        let frame = TrofeoProtocol.buildFrame(fakeJPEG, width: 1280, height: 480)
        XCTAssertEqual(Array(frame[0..<4]), TrofeoProtocol.magic)
        XCTAssertEqual(frame[4], TrofeoProtocol.cmdPicture)
        XCTAssertEqual(frame[6], TrofeoProtocol.modeJPEG)
        // W/H little-endian.
        XCTAssertEqual(Int(frame[8]) | (Int(frame[9]) << 8), 1280)
        XCTAssertEqual(Int(frame[10]) | (Int(frame[11]) << 8), 480)
        // Taille payload u32 LE.
        let len = Int(frame[16]) | (Int(frame[17]) << 8) | (Int(frame[18]) << 16) | (Int(frame[19]) << 24)
        XCTAssertEqual(len, fakeJPEG.count)
        // Payload préservé après le header de 20 o.
        XCTAssertEqual(Array(frame[20..<(20 + fakeJPEG.count)]), fakeJPEG)
    }

    func testFrameIs512Aligned() {
        let frame = TrofeoProtocol.buildFrame(fakeJPEG, width: 1280, height: 480)
        XCTAssertEqual(frame.count % TrofeoProtocol.usbAlign, 0)
        let pad = Array(frame[(20 + fakeJPEG.count)...])
        XCTAssertEqual(pad, [UInt8](repeating: 0, count: pad.count))
    }

    func testFrameAlreadyAlignedNotOvergrown() {
        let payload: [UInt8] = [0xFF, 0xD8] + [UInt8](repeating: 0, count: 512 - 20 - 2)
        let frame = TrofeoProtocol.buildFrame(payload, width: 1280, height: 480)
        XCTAssertEqual(frame.count, 512)
    }

    func testLooksLikeJPEG() {
        XCTAssertTrue(TrofeoProtocol.looksLikeJPEG(fakeJPEG))
        XCTAssertFalse(TrofeoProtocol.looksLikeJPEG([0x00, 0x01]))
        XCTAssertFalse(TrofeoProtocol.looksLikeJPEG([]))
    }
}
