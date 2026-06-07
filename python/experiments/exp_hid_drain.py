#!/usr/bin/env python3
"""Hypothèse ACK-drain : lire l'interrupt-IN 0x83 entre deux frames.

Si drainer un statut/ACK après chaque write débloque les frames suivantes, alors
le device a besoin du read (contrairement au classement « Type 2 write-only » de
la réf). On reste en hidapi (le stack HID, seule voie macOS).
"""

import os
import sys
import time

import hid

# Permet de lancer le script sans installer le package (python/ sur le path).
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from trofeo import protocol, render


def main() -> int:
    dev = hid.Device(0x0416, 0x5302)
    time.sleep(0.10)

    # handshake
    dev.write(bytes([0x00]) + protocol.build_init_packet())
    hs = protocol.parse_handshake(bytes(dev.read(512, 5000)))
    print(f"handshake : valide={hs.valid} PM={hs.pm} res={hs.resolution}")
    if not hs.valid:
        return 2
    w, h = hs.resolution or (1280, 480)
    frame = protocol.build_frame(render.to_jpeg(render.test_pattern(w, h)), w, h)

    N, PERIOD = 15, 0.3
    for i in range(N):
        try:
            n = dev.write(bytes([0x00]) + frame)
        except Exception as e:
            print(f"frame {i+1:>2}/{N} : WRITE ÉCHEC {type(e).__name__}: {e}")
            return 4
        # drain d'un éventuel statut/ACK sur 0x83 (timeout court)
        try:
            ack = bytes(dev.read(64, 150))
            tag = f"ack {len(ack)} o : {ack[:16].hex()}" if ack else "ack vide"
        except Exception as e:
            tag = f"read err {type(e).__name__}: {e}"
        print(f"frame {i+1:>2}/{N} : {n} o écrits | {tag}")
        time.sleep(PERIOD)

    print("\n[ok] 15 frames enchaînées AVEC drain : l'ACK-read était la clé.")
    dev.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
