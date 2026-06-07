// Transport « reset-loop » en IOKit pur (cf. docs/MACOS_FEASIBILITY.md).
//
//   reset (IOUSBLib USBDeviceReEnumerate) -> handshake + write (IOHIDManager) -> lock
//
// Le reset est une opération niveau *device* (IOUSBLib), qui ne requiert PAS de claim
// de l'interface HID (que IOHIDFamily verrouille) — d'où sa possibilité. La frame part
// par IOHIDDeviceSetReport (output report, reportID 0, données SANS préfixe — contrairement
// à hidapi qui préfixe le reportID).
//
// NOTE (à valider sur matériel) : contrairement au prototype Python, on ne LIT pas la
// réponse du handshake (l'interrupt-IN passerait par un input-report callback + run loop).
// On s'appuie sur le succès des SetReport. Si le firmware exige la lecture, on ajoutera
// le callback.

import Foundation
import IOKit
import IOKit.hid
import IOKit.usb
import IOKit.usb.IOUSBLib

public enum TransportError: Error, CustomStringConvertible {
    case noDevice
    case resetFailed(String)
    case notReady

    public var description: String {
        switch self {
        case .noDevice: return "device 0416:5302 introuvable"
        case .resetFailed(let s): return "reset USB échoué : \(s)"
        case .notReady: return "device pas prêt après reset (ré-énumération ?)"
        }
    }
}

public final class TrofeoDevice {

    public let vid = 0x0416
    public let pid = 0x5302
    let reportID: CFIndex = 0
    let reenumDeadline: TimeInterval = 3.0

    public init() {}

    // MARK: Reset device (IOUSBLib)

    /// Re-énumère le device (≈ reset) pour casser le lock post-frame.
    // UUID des interfaces COM IOKit — non exposées en Swift (macro structure), reconstruites.
    private static let plugInID = CFUUIDCreateFromString(nil, "C244E858-109C-11D4-91D4-0050E4C6426F" as CFString)
    private static let deviceUserClientTypeID = CFUUIDCreateFromString(nil, "9DC7B780-9EC0-11D4-A54F-000A27052861" as CFString)
    private static let deviceInterfaceID = CFUUIDCreateFromString(nil, "5C8187D0-9EF3-11D4-8B45-000A27052861" as CFString)

    public func resetDevice() throws {
        let matching = IOServiceMatching(kIOUSBDeviceClassName) as NSMutableDictionary
        matching["idVendor"] = vid
        matching["idProduct"] = pid

        var iterator: io_iterator_t = 0
        guard IOServiceGetMatchingServices(kIOMainPortDefault, matching as CFDictionary, &iterator) == KERN_SUCCESS else {
            throw TransportError.resetFailed("IOServiceGetMatchingServices")
        }
        defer { IOObjectRelease(iterator) }

        let service = IOIteratorNext(iterator)
        guard service != 0 else { throw TransportError.noDevice }
        defer { IOObjectRelease(service) }

        var pluginPtr: UnsafeMutablePointer<UnsafeMutablePointer<IOCFPlugInInterface>?>?
        var score: Int32 = 0
        guard IOCreatePlugInInterfaceForService(
            service, Self.deviceUserClientTypeID, Self.plugInID, &pluginPtr, &score) == KERN_SUCCESS,
            let plugin = pluginPtr else {
            throw TransportError.resetFailed("IOCreatePlugInInterfaceForService")
        }
        defer { _ = plugin.pointee?.pointee.Release(UnsafeMutableRawPointer(plugin)) }

        var deviceRaw: UnsafeMutableRawPointer?
        let iid = CFUUIDGetUUIDBytes(Self.deviceInterfaceID)
        let qr = plugin.pointee?.pointee.QueryInterface(UnsafeMutableRawPointer(plugin), iid, &deviceRaw)
        guard qr == 0, let deviceRaw else {
            throw TransportError.resetFailed("QueryInterface \(qr.map(String.init) ?? "nil")")
        }
        let device = deviceRaw.bindMemory(to: UnsafeMutablePointer<IOUSBDeviceInterface>?.self, capacity: 1)
        defer { _ = device.pointee?.pointee.Release(UnsafeMutableRawPointer(device)) }

        // USBDeviceReEnumerate exige le device OUVERT au niveau USB, sinon
        // kIOReturnNotOpen (0xE00002CD). On n'ouvre que le device (pas l'interface
        // HID, que IOHIDFamily verrouille) : Seize en repli si déjà ouvert ailleurs.
        var openKr = device.pointee?.pointee.USBDeviceOpen(UnsafeMutableRawPointer(device))
        if openKr != kIOReturnSuccess {
            openKr = device.pointee?.pointee.USBDeviceOpenSeize(UnsafeMutableRawPointer(device))
        }
        guard openKr == kIOReturnSuccess else {
            throw TransportError.resetFailed("USBDeviceOpen \(openKr.map(String.init) ?? "nil")")
        }

        let rr = device.pointee?.pointee.USBDeviceReEnumerate(UnsafeMutableRawPointer(device), 0)
        // Après ré-énumération le device disparaît du bus : le handle devient
        // caduc, inutile de USBDeviceClose (Release suffit).
        guard rr == kIOReturnSuccess else {
            _ = device.pointee?.pointee.USBDeviceClose(UnsafeMutableRawPointer(device))
            throw TransportError.resetFailed("USBDeviceReEnumerate \(rr.map(String.init) ?? "nil")")
        }
    }

    // MARK: HID (frame write)

    private func openHID() -> (IOHIDManager, IOHIDDevice)? {
        let mgr = IOHIDManagerCreate(kCFAllocatorDefault, IOOptionBits(kIOHIDOptionsTypeNone))
        let matching: [String: Any] = [kIOHIDVendorIDKey: vid, kIOHIDProductIDKey: pid]
        IOHIDManagerSetDeviceMatching(mgr, matching as CFDictionary)
        guard IOHIDManagerOpen(mgr, IOOptionBits(kIOHIDOptionsTypeNone)) == kIOReturnSuccess else {
            return nil
        }
        guard let devices = IOHIDManagerCopyDevices(mgr) as? Set<IOHIDDevice>, let dev = devices.first else {
            IOHIDManagerClose(mgr, IOOptionBits(kIOHIDOptionsTypeNone))
            return nil
        }
        guard IOHIDDeviceOpen(dev, IOOptionBits(kIOHIDOptionsTypeNone)) == kIOReturnSuccess else {
            IOHIDManagerClose(mgr, IOOptionBits(kIOHIDOptionsTypeNone))
            return nil
        }
        return (mgr, dev)
    }

    private func setReport(_ dev: IOHIDDevice, _ bytes: [UInt8]) -> IOReturn {
        bytes.withUnsafeBufferPointer { buf in
            IOHIDDeviceSetReport(dev, kIOHIDReportTypeOutput, reportID, buf.baseAddress!, buf.count)
        }
    }

    // MARK: API

    /// Cycle complet : reset -> ré-énumération -> init -> frame. Lève si non prêt.
    public func sendFrame(_ frame: [UInt8]) throws {
        try resetDevice()
        let deadline = Date().addingTimeInterval(reenumDeadline)
        while Date() < deadline {
            if let (mgr, dev) = openHID() {
                defer {
                    IOHIDDeviceClose(dev, IOOptionBits(kIOHIDOptionsTypeNone))
                    IOHIDManagerClose(mgr, IOOptionBits(kIOHIDOptionsTypeNone))
                }
                if setReport(dev, TrofeoProtocol.buildInitPacket()) == kIOReturnSuccess {
                    usleep(2000)
                    if setReport(dev, frame) == kIOReturnSuccess { return }
                }
            }
            usleep(15_000)  // poll serré pendant la ré-énumération
        }
        throw TransportError.notReady
    }
}
