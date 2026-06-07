#!/usr/bin/env python3
"""La découverte clé : boucle reset->handshake->frame, ~5 fps stable.

Prouve que `libusb reset_device()` réveille le device verrouillé après chaque frame,
permettant un affichage continu. C'est le fondement de `trofeo/transport.py`.
À lancer avec le venv (trofeo installé) et DYLD_FALLBACK_LIBRARY_PATH pointant
hidapi + libusb. Diagnostic : touche le matériel.
"""
import time

import hid
import usb.core
import usb.util
from PIL import ImageDraw, ImageFont

from trofeo import protocol, render

VID, PID = 0x0416, 0x5302
DURATION_S = 25
_FONT = ImageFont.load_default(size=240)


def reset_device():
    dev = usb.core.find(idVendor=VID, idProduct=PID)
    if dev is not None:
        try:
            dev.reset()
        except Exception:
            pass
        usb.util.dispose_resources(dev)


def push(frame, deadline_s=3.0):
    end = time.time() + deadline_s
    while time.time() < end:
        try:
            d = hid.Device(VID, PID)
            time.sleep(0.05)
            d.write(bytes([0x00]) + protocol.build_init_packet())
            if protocol.parse_handshake(bytes(d.read(512, 1500))).valid:
                d.write(bytes([0x00]) + frame)
                d.close()
                return True
            d.close()
        except Exception:
            time.sleep(0.08)
    return False


frames = {}
def frame_for(sec):
    if sec not in frames:
        img = render.test_pattern()
        ImageDraw.Draw(img).text((640, 240), str(sec), fill=(255, 255, 0),
                                 anchor="mm", font=_FONT)
        frames[sec] = protocol.build_frame(render.to_jpeg(img), 1280, 480)
    return frames[sec]


t0 = time.time()
n_ok = 0
while time.time() - t0 < DURATION_S:
    reset_device()
    if push(frame_for(int(time.time() - t0))):
        n_ok += 1
elapsed = time.time() - t0
print(f"{n_ok} refresh en {elapsed:.1f}s ≈ {n_ok / elapsed:.1f} fps")
