#!/usr/bin/env python3
"""Expérience : piloter le Trofeo en libusb (pyusb) interrupt-OUT, comme la réf.

But : savoir (a) si libusb peut claim l'interface HID sur macOS (le mur IOKit),
et (b) si l'interrupt-OUT sur EP 0x02 enchaîne les frames sans figer le device
(là où hidapi/SetReport gèle à la 2e frame).

Throwaway. Rien n'est committé tant que ce n'est pas validé.
"""

import os
import sys
import time

import usb.core
import usb.util

# Permet de lancer le script sans installer le package (python/ sur le path).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from trofeo import protocol, render

VID, PID = 0x0416, 0x5302
_EP_TYPE = {0: "control", 1: "isochronous", 2: "bulk", 3: "interrupt"}


def main() -> int:
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is None:
        print("[!!] device 0416:5302 introuvable (branché ? backend libusb ok ?)")
        return 1
    print(f"[ok] device trouvé : bus={dev.bus} addr={dev.address} "
          f"class={dev.bDeviceClass}")

    # --- Descripteurs (utile quoi qu'il arrive) ---
    print("\n=== descripteurs ===")
    for cfg in dev:
        print(f"config {cfg.bConfigurationValue} : {cfg.bNumInterfaces} interface(s)")
        for intf in cfg:
            cls = intf.bInterfaceClass
            print(f"  iface {intf.bInterfaceNumber} alt {intf.bAlternateSetting} "
                  f"class=0x{cls:02x}{' (HID)' if cls == 3 else ''}")
            for ep in intf:
                addr = ep.bEndpointAddress
                direction = "IN" if addr & 0x80 else "OUT"
                ettype = _EP_TYPE.get(usb.util.endpoint_type(ep.bmAttributes), "?")
                print(f"    EP 0x{addr:02x} {direction:<3} {ettype:<10} "
                      f"wMaxPacketSize={ep.wMaxPacketSize}")

    # --- detach kernel driver iface 0-3 ---
    print("\n=== detach kernel driver (iface 0-3) ===")
    for i in range(4):
        try:
            active = dev.is_kernel_driver_active(i)
            if active:
                dev.detach_kernel_driver(i)
                print(f"  iface {i} : détaché")
            else:
                print(f"  iface {i} : pas de driver kernel actif")
        except Exception as e:
            print(f"  iface {i} : {type(e).__name__}: {e}")

    # --- set_configuration ---
    print("\n=== set_configuration(1) ===")
    try:
        dev.set_configuration(1)
        print("  ok")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")

    # --- claim interface 0 (le point critique macOS) ---
    print("\n=== claim_interface(0) — crux macOS ===")
    try:
        usb.util.claim_interface(dev, 0)
        print("  ok : libusb tient l'interface")
    except Exception as e:
        print(f"  FAIL: {type(e).__name__}: {e}")
        print("  >> Sur macOS, IOKit/IOHIDFamily tient probablement l'interface HID.")
        print("  >> Conclusion : libusb nu non viable ici -> piste IOUSBHost côté Swift.")
        return 2

    # --- endpoints sur iface 0 ---
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = ep_in = None
    for ep in intf:
        if ep.bEndpointAddress & 0x80:
            ep_in = ep_in or ep.bEndpointAddress
        else:
            ep_out = ep_out or ep.bEndpointAddress
    print(f"\n=== endpoints retenus : OUT=0x{ep_out:02x} IN=0x{ep_in:02x} ===")

    # --- handshake ---
    print("\n=== handshake ===")
    n = dev.write(ep_out, protocol.build_init_packet(), timeout=5000)
    print(f"  init écrit ({n} o)")
    resp = bytes(dev.read(ep_in, 512, timeout=5000))
    hs = protocol.parse_handshake(resp)
    print(f"  resp {len(resp)} o ; valide={hs.valid} PM={hs.pm} res={hs.resolution}")
    if not hs.valid:
        print("  [!!] handshake invalide, on s'arrête")
        return 3
    w, h = hs.resolution or (1280, 480)

    # --- frames en rafale (< 2s pour battre la revert) ---
    print("\n=== frames en rafale (15 x, période 0.8s) ===")
    frame = protocol.build_frame(render.to_jpeg(render.test_pattern(w, h)), w, h)
    N, PERIOD = 15, 0.8
    for i in range(N):
        to = max(100, len(frame) // 4 + 100)
        try:
            n = dev.write(ep_out, frame, timeout=to)
            print(f"  frame {i+1:>2}/{N} : {n} o écrits")
        except Exception as e:
            print(f"  frame {i+1:>2}/{N} : ÉCHEC {type(e).__name__}: {e}")
            print("  >> l'interrupt-OUT gèle aussi -> ce n'est pas (que) le transport.")
            return 4
        time.sleep(0.001)            # le 1ms de la réf
        if i < N - 1:
            time.sleep(PERIOD)
    print("\n[ok] 15 frames enchaînées sans gel : le transport ÉTAIT le problème.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
