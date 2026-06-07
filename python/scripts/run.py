#!/usr/bin/env python3
"""Prototype : affichage live sur le Trofeo Vision via la boucle reset.

Affiche une horloge + quelques infos système, rafraîchies en continu. Chaque frame
passe par le cycle prouvé `reset (libusb) -> handshake -> write (hidapi)` qui réveille
le device (verrouillé après chaque frame). Cf. docs/PROTOCOL.md.

Usage ::

    brew install hidapi libusb
    pip install -e ".[dev]"
    export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix hidapi)/lib:$(brew --prefix libusb)/lib"
    python scripts/run.py                 # horloge, ~3 fps, jusqu'à Ctrl-C
    python scripts/run.py --fps 4 --duration 30
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import psutil

sys.path.insert(0, __file__.rsplit("/scripts/", 1)[0])

from trofeo import protocol, render  # noqa: E402
from trofeo.transport import TrofeoDevice, TransportError  # noqa: E402


def _uptime_str() -> str:
    secs = int(time.time() - psutil.boot_time())
    days, rem = divmod(secs, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    return f"{days}d {hours:02d}h" if days else f"{hours:02d}h {minutes:02d}m"


def _metrics(fps: float):
    """Renvoie (bars, lines) pour le dashboard."""
    bars = [
        ("CPU", psutil.cpu_percent() / 100.0),
        ("RAM", psutil.virtual_memory().percent / 100.0),
    ]
    lines = []
    try:
        l1, l5, l15 = os.getloadavg()
        lines.append(("LOAD", f"{l1:.2f} {l5:.2f} {l15:.2f}"))
    except (OSError, AttributeError):
        pass
    lines.append(("UPTIME", _uptime_str()))
    lines.append(("REFRESH", f"{fps:.1f} fps"))
    return bars, lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Affichage live du Trofeo Vision.")
    parser.add_argument("--fps", type=float, default=3.0,
                        help="cadence cible de rafraîchissement (défaut 3 ; >2 garde "
                             "l'image vivante avant le revert ~2 s)")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="durée en secondes (0 = jusqu'à Ctrl-C)")
    parser.add_argument("--quality", type=int, default=90, help="qualité JPEG")
    args = parser.parse_args()

    interval = 1.0 / max(0.5, args.fps)
    dev = TrofeoDevice()

    print("Trofeo live — Ctrl-C pour arrêter.")
    t_start = time.monotonic()
    n_ok = n_ko = 0
    fps_live = args.fps
    last = time.monotonic()
    fails = 0

    try:
        while True:
            t0 = time.monotonic()
            bars, lines = _metrics(fps_live)
            img = render.dashboard(time.strftime("%H:%M:%S"), time.strftime("%a %d %b"), bars, lines)
            frame = protocol.build_frame(render.to_jpeg(img, args.quality), render.WIDTH, render.HEIGHT)
            try:
                dev.send_frame(frame)
                n_ok += 1
                fails = 0
            except TransportError as exc:
                n_ko += 1
                fails += 1
                print(f"[!] frame ratée ({fails}) : {exc}", file=sys.stderr)
                if fails >= 5:
                    print("[!!] 5 échecs d'affilée — device débranché ? On arrête.", file=sys.stderr)
                    return 1

            now = time.monotonic()
            fps_live = 1.0 / max(1e-3, now - last)
            last = now

            if args.duration and now - t_start >= args.duration:
                break
            time.sleep(max(0.0, interval - (now - t0)))
    except KeyboardInterrupt:
        print()

    elapsed = time.monotonic() - t_start
    rate = n_ok / elapsed if elapsed else 0.0
    print(f"Fini : {n_ok} frames affichées ({n_ko} ratées) en {elapsed:.1f}s ≈ {rate:.1f} fps")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
