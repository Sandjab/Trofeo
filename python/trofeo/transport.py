"""Transport « reset-loop » — la seule voie de streaming userspace sur macOS.

Découverte clé (cf. docs/PROTOCOL.md) : ce device n'accepte qu'**une** frame par
ouverture, puis verrouille tout `SetReport` (IOHIDDeviceSetReport timeout). Mais un
**`libusb reset_device()`** — opération niveau device qui ne nécessite PAS de claim
de l'interface HID (interdit par IOHIDFamily sur macOS) — le **réveille**. D'où le
cycle, validé à ~5 fps stable sur matériel :

    reset (pyusb) -> handshake + write frame (hidapi) -> close

On combine donc deux piles : pyusb/libusb pour le reset, hidapi pour l'écriture de
la frame (l'écriture passe par l'interface HID, seule porte d'entrée des frames).
Le port Swift fera l'équivalent en IOKit pur : `IOUSBHost` reset + `IOHIDManager`
SetReport.

Imports paresseux : `import trofeo` (protocole pur, testé) ne tire ni hid ni usb.
"""

from __future__ import annotations

import time

from . import protocol

VID = 0x0416
PID = 0x5302

#: Report ID HID préfixé à chaque write (0 = report non-numéroté).
REPORT_ID = 0x00

#: Délai de settle après ouverture hidapi avant le premier write.
_SETTLE_S = 0.05

#: Fenêtre max pour qu'un device ré-énumère après reset et réponde au handshake.
_REENUM_DEADLINE_S = 3.0


class TransportError(RuntimeError):
    """Échec d'ouverture, de reset ou d'écriture côté transport."""


def _require_hid():
    try:
        import hid
        return hid
    except ImportError as exc:  # pragma: no cover - dépend de l'env
        raise TransportError(
            "package 'hid' indisponible. `pip install hid` (+ `brew install hidapi`), "
            'et lancer avec DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix hidapi)/lib".'
        ) from exc


def _require_usb():
    try:
        import usb.core  # noqa: F401
        import usb.util  # noqa: F401
        import usb
        return usb
    except ImportError as exc:  # pragma: no cover - dépend de l'env
        raise TransportError(
            "package 'pyusb' indisponible. `pip install pyusb` (+ `brew install libusb`), "
            'et lancer avec DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix libusb)/lib".'
        ) from exc


class TrofeoDevice:
    """Pilote bas niveau du Trofeo Vision. Une frame = un cycle reset+handshake+write.

    Exemple ::

        dev = TrofeoDevice()
        hs = dev.send_frame(frame_bytes)   # reset -> handshake -> write
        print(hs.pm, hs.resolution)
    """

    def __init__(self, vid: int = VID, pid: int = PID, report_id: int = REPORT_ID):
        self._vid = vid
        self._pid = pid
        self._report_id = report_id

    # --- bas niveau -------------------------------------------------------

    def _reset(self) -> None:
        """Réveille le device via un reset libusb (sans claim de l'iface HID)."""
        usb = _require_usb()
        try:
            dev = usb.core.find(idVendor=self._vid, idProduct=self._pid)
        except usb.core.NoBackendError as exc:  # pragma: no cover - dépend de l'env
            raise TransportError(
                "backend libusb introuvable — `brew install libusb` et "
                'DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix libusb)/lib".'
            ) from exc
        if dev is not None:
            try:
                dev.reset()
            except Exception:
                # Un reset peut échouer si le device ré-énumère déjà : non bloquant.
                pass
            usb.util.dispose_resources(dev)

    def _open_with_handshake(self, deadline_s: float = _REENUM_DEADLINE_S):
        """Rouvre en hidapi et fait le handshake, en réessayant le temps que le
        device ré-énumère après le reset. Renvoie ``(device, Handshake)`` ou
        ``(None, None)``."""
        hid = _require_hid()
        end = time.monotonic() + deadline_s
        while time.monotonic() < end:
            try:
                dev = hid.Device(self._vid, self._pid)
                time.sleep(_SETTLE_S)
                dev.write(bytes([self._report_id]) + protocol.build_init_packet())
                hs = protocol.parse_handshake(bytes(dev.read(protocol.INIT_PACKET_SIZE, 1500)))
                if hs.valid:
                    return dev, hs
                dev.close()
            except Exception:
                time.sleep(0.08)  # device pas encore ré-énuméré : on réessaie
        return None, None

    # --- API ------------------------------------------------------------

    def handshake(self) -> protocol.Handshake:
        """Reset + handshake seul (sans frame). Pour diagnostiquer le PM byte."""
        self._reset()
        dev, hs = self._open_with_handshake()
        if dev is None or hs is None:
            raise TransportError("aucun handshake valide après reset (device ré-énuméré ?).")
        dev.close()
        return hs

    def send_frame(self, frame: bytes) -> protocol.Handshake:
        """Cycle complet : reset -> handshake -> write d'une frame. Renvoie le
        handshake (utile pour la résolution réelle)."""
        self._reset()
        dev, hs = self._open_with_handshake()
        if dev is None or hs is None:
            raise TransportError("device n'a pas ré-énuméré après reset.")
        try:
            dev.write(bytes([self._report_id]) + frame)
        finally:
            dev.close()
        return hs
