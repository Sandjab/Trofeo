#!/usr/bin/env python3
"""First light du Trofeo Vision : handshake + dump du PM byte, puis une image.

Objectif unique : valider le protocole sur le matériel réel et LIRE le vrai PM
byte renvoyé par *cet* écran (128 ou 68 ? — voir docs/PROTOCOL.md). Si tout va
bien, on pousse une mire de test 1280x480 pour contrôler orientation et couleurs.

Usage ::

    pip install hid pillow          # libhidapi natif requis : brew install hidapi
    python scripts/first_light.py                 # handshake + image
    python scripts/first_light.py --dump-only     # handshake seul, pas d'image
    python scripts/first_light.py --save mire.jpg # sauve aussi la mire en local
"""

from __future__ import annotations

import argparse
import sys

# Permet de lancer le script sans installer le package (depuis python/).
sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from trofeo import protocol, render  # noqa: E402
from trofeo.transport import HidTransport, TransportError  # noqa: E402


def _hexdump(data: bytes, length: int = 32) -> str:
    return " ".join(f"{b:02x}" for b in data[:length])


def main() -> int:
    parser = argparse.ArgumentParser(description="First light du Trofeo Vision.")
    parser.add_argument("--dump-only", action="store_true", help="handshake seul, sans image")
    parser.add_argument("--save", metavar="FICHIER", help="sauver la mire en JPEG local")
    parser.add_argument("--quality", type=int, default=95, help="qualité JPEG (défaut 95)")
    parser.add_argument("--width", type=int, default=render.WIDTH)
    parser.add_argument("--height", type=int, default=render.HEIGHT)
    args = parser.parse_args()

    try:
        with HidTransport() as t:
            print(f"[ok] device {HidTransport().__class__.__name__} ouvert "
                  f"({protocol.MAGIC.hex()} attendu en réponse)")

            # 1) Handshake.
            init = protocol.build_init_packet()
            print(f"[->] init : {len(init)} o  | {_hexdump(init)} ...")
            t.write(init)
            resp = t.read(protocol.INIT_PACKET_SIZE)
            print(f"[<-] resp : {len(resp)} o  | {_hexdump(resp, len(resp))}")

            hs = protocol.parse_handshake(resp)
            if not hs.valid:
                print("[!!] handshake INVALIDE (magic ou resp[12] inattendu). "
                      "On s'arrête : géométrie non confirmée.")
                return 2
            print(f"[ok] handshake valide")
            print(f"     PM byte (resp[5]) = {hs.pm}  (0x{hs.pm:02x})")
            print(f"     sub (resp[4])     = {hs.sub}")
            print(f"     résolution déduite = {hs.resolution}")
            print(f"     serial            = {hs.serial or '(absent)'}")
            if hs.resolution is None:
                print("[?]  PM byte non répertorié — note-le, c'est une donnée "
                      "neuve à ajouter à docs/PROTOCOL.md.")

            if args.dump_only:
                return 0

            # 2) Image : mire de test.
            w, h = (hs.resolution or (args.width, args.height))
            img = render.test_pattern(w, h)
            jpeg = render.to_jpeg(img, quality=args.quality)
            if args.save:
                with open(args.save, "wb") as fh:
                    fh.write(jpeg)
                print(f"[ok] mire sauvée -> {args.save} ({len(jpeg)} o)")

            frame = protocol.build_frame(jpeg, w, h)
            print(f"[->] frame : header 20 o + jpeg {len(jpeg)} o "
                  f"-> {len(frame)} o (aligné {protocol.USB_ALIGN})")
            written = t.write(frame)
            print(f"[ok] {written} o écrits. Regarde l'écran : la flèche doit "
                  f"pointer vers le HAUT, les barres R/V/B dans l'ordre.")
            return 0

    except TransportError as exc:
        print(f"[!!] transport : {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
