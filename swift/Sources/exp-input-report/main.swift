// Expérience : le « lock après 1 frame » est-il host-side (IOHIDFamily) ?
//
// Hypothèse (Apple Forums thread 742144, symptôme identique au nôtre) : après un
// output report resté sans réponse du device, IOHIDFamily se jamme et tout
// SetReport suivant time out — le verrou serait dans macOS, pas dans le firmware.
// Workaround proposé là-bas : émettre en kIOHIDReportTypeInput au lieu d'Output.
// Cohérent avec nos mesures : le handshake (qui reçoit une réponse) ne jamme pas,
// la frame (sans réponse) jamme ; clear-halt inopérant ; reset (recrée l'objet
// IOHIDDevice kernel) débloque. Cf. docs/PROTOCOL.md §7, docs/MACOS_FEASIBILITY.md.
//
// Phases (chacune part d'un reset pour un état propre) :
//   control  : frame1 Output, frame2 Output  → doit reproduire le lock (timeout)
//   out-in   : frame1 Output, suite en Input → si OK : streaming sans reset
//   in-in    : toutes les frames en Input    → si out-in échoue dès frame2
//
// Verdict écran À L'ŒIL : le compteur « F n » doit défiler sur la dalle.
// Usage : swift run exp-input-report [--control]

import Foundation
import IOKit.hid
import TrofeoKit

func hex(_ r: IOReturn) -> String { String(format: "0x%08X", UInt32(bitPattern: r)) }

// MARK: - Ouverture HID minimaliste (dupliquée de Transport, avec report type libre)

final class HIDHandle {
    private let mgr: IOHIDManager
    private let dev: IOHIDDevice

    init?(vid: Int, pid: Int) {
        let mgr = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
        IOHIDManagerSetDeviceMatching(
            mgr, [kIOHIDVendorIDKey: vid, kIOHIDProductIDKey: pid] as CFDictionary)
        guard IOHIDManagerOpen(mgr, IOOptionBits(kIOHIDOptionsTypeNone)) == kIOReturnSuccess,
              let devices = IOHIDManagerCopyDevices(mgr) as? Set<IOHIDDevice>,
              let dev = devices.first,
              IOHIDDeviceOpen(dev, IOOptionBits(kIOHIDOptionsTypeNone)) == kIOReturnSuccess
        else {
            IOHIDManagerClose(mgr, IOOptionBits(kIOHIDOptionsTypeNone))
            return nil
        }
        self.mgr = mgr
        self.dev = dev
    }

    func setReport(_ bytes: [UInt8], type: IOHIDReportType) -> IOReturn {
        bytes.withUnsafeBufferPointer { buf in
            IOHIDDeviceSetReport(dev, type, 0, buf.baseAddress!, buf.count)
        }
    }

    func close() {
        IOHIDDeviceClose(dev, IOOptionBits(kIOHIDOptionsTypeNone))
        IOHIDManagerClose(mgr, IOOptionBits(kIOHIDOptionsTypeNone))
    }
}

// MARK: - Helpers

let device = TrofeoDevice()

func openAfterReenum(deadline: TimeInterval = 3.0) -> HIDHandle? {
    let end = Date().addingTimeInterval(deadline)
    while Date() < end {
        if let h = HIDHandle(vid: device.vid, pid: device.pid) { return h }
        usleep(15_000)
    }
    return nil
}

func counterFrame(_ label: String) -> [UInt8] {
    let img = Render.dashboard(clock: label, date: "exp input-report",
                               bars: [], lines: [("PHASE", label)])
    return TrofeoProtocol.buildFrame([UInt8](Render.jpeg(img, quality: 0.9)),
                                     width: Render.width, height: Render.height)
}

func typeName(_ t: IOHIDReportType) -> String { t == kIOHIDReportTypeInput ? "In" : "Out" }

/// Une phase : reset → handshake(Out) → frame1(firstType) → frames 2..count (followType).
/// Renvoie le nombre de frames écrites avec succès.
@discardableResult
func runPhase(_ name: String, firstType: IOHIDReportType, followType: IOHIDReportType,
              count: Int, intervalMs: UInt32 = 500) -> Int {
    print("\n=== phase \(name) — frame1=\(typeName(firstType)), suite=\(typeName(followType)) ===")
    do { try device.resetDevice() } catch {
        print("reset KO: \(error) — phase abandonnée")
        return 0
    }
    guard let h = openAfterReenum() else {
        print("open HID KO après ré-énumération — phase abandonnée")
        return 0
    }
    defer { h.close() }

    let hs = h.setReport(TrofeoProtocol.buildInitPacket(), type: kIOHIDReportTypeOutput)
    print("handshake(Out)  : \(hex(hs))\(hs == kIOReturnSuccess ? " OK" : " KO — phase abandonnée")")
    guard hs == kIOReturnSuccess else { return 0 }
    usleep(2000)

    var ok = 0
    for i in 1...count {
        if i > 1 { usleep(intervalMs * 1000) }
        let type = i == 1 ? firstType : followType
        let r = h.setReport(counterFrame("F \(i)"), type: type)
        print("frame \(i) (\(typeName(type)))\t: \(hex(r))\(r == kIOReturnSuccess ? " OK" : " KO — stop")")
        if r != kIOReturnSuccess { break }
        ok += 1
    }
    if ok == count {
        print("→ \(ok)/\(count) écrites SANS reset intermédiaire. Le compteur a-t-il défilé à l'écran ?")
    }
    return ok
}

// MARK: - Main

let withControl = CommandLine.arguments.contains("--control")

print("exp-input-report — hypothèse « verrou host-side IOHIDFamily »")
print("Observer la dalle : un compteur « F n » doit défiler si une phase réussit.")

if withControl {
    // Contrôle : reproduit le lock documenté (frame2 Output → timeout attendu).
    runPhase("control (Out/Out)", firstType: kIOHIDReportTypeOutput,
             followType: kIOHIDReportTypeOutput, count: 3)
}

let outIn = runPhase("out-in", firstType: kIOHIDReportTypeOutput,
                     followType: kIOHIDReportTypeInput, count: 12)
let inIn = runPhase("in-in", firstType: kIOHIDReportTypeInput,
                    followType: kIOHIDReportTypeInput, count: 12)

print("""

=== bilan ===
out-in : \(outIn)/12 écritures OK
in-in  : \(inIn)/12 écritures OK
Rappel : « écriture OK » ne prouve PAS l'affichage — vérifier à l'œil que le
compteur défilait. Si écritures OK mais écran figé, IOHIDFamily route
probablement les reports Input par EP0 et le firmware les ignore.
""")
