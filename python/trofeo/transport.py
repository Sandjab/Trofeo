"""Transport HID pour l'expérimentation Python (via hidapi / package ``hid``).

C'est la SEULE couche qui touche le matériel. On reste volontairement minimal :
ouvrir le device par VID/PID, écrire un paquet, lire une réponse, fermer.

Choix de transport :
  * Python (ici)  → hidapi (package ``hid``). Sur macOS, hidapi passe par
    IOHIDManager, donc pas de claim libusb sur une interface HID (que IOKit
    refuserait).
  * Swift (à venir) → IOHIDManager DIRECT via IOKit, AUCUNE dépendance hidapi
    au runtime. On ne porte que le *protocole*, pas ce transport.

Subtilité HID importante : avec hidapi, le premier octet de chaque ``write`` est
le **Report ID** (0x00 ici, report non-numéroté), que la lib retire avant
émission. Donc le paquet on-wire reste ``DA DB DC DD …`` mais le buffer passé à
``hid`` est préfixé d'un 0x00. À l'inverse, ``read`` ne renvoie PAS de préfixe
pour un report non-numéroté : la réponse commence directement par le MAGIC.
"""

from __future__ import annotations

VID = 0x0416
PID = 0x5302

#: Report ID HID préfixé à chaque write (0 = report non-numéroté).
REPORT_ID = 0x00


class TransportError(RuntimeError):
    """Échec d'ouverture, d'écriture ou de lecture côté transport."""


class HidTransport:
    """Wrapper fin autour du package ``hid`` (hidapi).

    Utilisable comme context manager ::

        with HidTransport() as t:
            t.write(packet)
            resp = t.read(512)
    """

    def __init__(self, vid: int = VID, pid: int = PID, report_id: int = REPORT_ID):
        self._vid = vid
        self._pid = pid
        self._report_id = report_id
        self._dev = None

    def open(self) -> "HidTransport":
        try:
            import hid  # import paresseux : les tests purs n'en ont pas besoin
        except ImportError as exc:  # pragma: no cover - dépend de l'env
            raise TransportError(
                "package 'hid' indisponible. Deux causes possibles :\n"
                "  1. pas installé      -> `pip install hid`\n"
                "  2. libhidapi native introuvable au chargement (fréquent sur macOS :\n"
                "     brew ne met pas son lib/ sur le chemin du loader). Corrige avec :\n"
                "     `brew install hidapi` puis lance avec\n"
                "     `DYLD_FALLBACK_LIBRARY_PATH=\"$(brew --prefix hidapi)/lib\" python ...`"
            ) from exc

        try:
            self._dev = hid.Device(self._vid, self._pid)
        except Exception as exc:  # pragma: no cover - dépend du matériel
            raise TransportError(
                f"impossible d'ouvrir le device {self._vid:04x}:{self._pid:04x} "
                f"({exc}). Branché ? Bon VID/PID ? Pas déjà ouvert par un autre process ?"
            ) from exc
        return self

    def write(self, packet: bytes) -> int:
        """Écrit ``packet`` (préfixé du Report ID). Renvoie le nb d'octets écrits."""
        if self._dev is None:
            raise TransportError("transport non ouvert (appeler open() d'abord).")
        return self._dev.write(bytes([self._report_id]) + packet)

    def read(self, size: int, timeout_ms: int = 5000) -> bytes:
        """Lit jusqu'à ``size`` octets (un report d'entrée)."""
        if self._dev is None:
            raise TransportError("transport non ouvert (appeler open() d'abord).")
        return bytes(self._dev.read(size, timeout_ms))

    def close(self) -> None:
        if self._dev is not None:
            self._dev.close()
            self._dev = None

    def __enter__(self) -> "HidTransport":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()
