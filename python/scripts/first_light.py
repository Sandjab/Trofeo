#!/usr/bin/env python3
"""First light du Trofeo Vision : handshake + dump du PM byte, puis une image.

Diagnostic en un coup. Passe par le cycle reset->handshake->frame (cf.
docs/PROTOCOL.md), donc robuste même si la dalle était figée par un essai précédent.
Une seule frame est poussée : elle s'affiche ~2 s puis le firmware reprend la main.
Pour un affichage persistant, voir ``run.py``.

Usage ::

    export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix hidapi)/lib:$(brew --prefix libusb)/lib"
    python scripts/first_light.py                 # handshake + mire
    python scripts/first_light.py --dump-only     # handshake seul
    python scripts/first_light.py --save mire.jpg
"""

from __future__ import annotations

import argparse
import sys

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from trofeo import protocol, render  # noqa: E402
from trofeo.transport import TrofeoDevice, TransportError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="First light du Trofeo Vision.")
    parser.add_argument("--dump-only", action="store_true", help="handshake seul, sans image")
    parser.add_argument("--save", metavar="FICHIER", help="sauver la mire en JPEG local")
    parser.add_argument("--quality", type=int, default=95, help="qualité JPEG (défaut 95)")
    args = parser.parse_args()

    dev = TrofeoDevice()

    try:
        if args.dump_only:
            hs = dev.handshake()
        else:
            img = render.test_pattern()
            jpeg = render.to_jpeg(img, quality=args.quality)
            if args.save:
                with open(args.save, "wb") as fh:
                    fh.write(jpeg)
                print(f"[ok] mire sauvée -> {args.save} ({len(jpeg)} o)")
            w, h = render.WIDTH, render.HEIGHT
            frame = protocol.build_frame(jpeg, w, h)
            hs = dev.send_frame(frame)
    except TransportError as exc:
        print(f"[!!] {exc}", file=sys.stderr)
        return 1

    print("[ok] handshake valide")
    print(f"     PM byte = {hs.pm} (0x{hs.pm:02x})" if hs.pm is not None else "     PM byte = ?")
    print(f"     résolution déduite = {hs.resolution}")
    print(f"     serial = {hs.serial or '(absent)'}")
    if hs.resolution is None and hs.pm is not None:
        print("[?]  PM byte non répertorié — à ajouter à docs/PROTOCOL.md.")
    if not args.dump_only:
        print("[ok] mire poussée (1 frame). Elle s'affiche ~2 s ; pour persister, "
              "utilise run.py.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
