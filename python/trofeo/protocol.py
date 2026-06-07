"""Protocole filaire de l'écran Thermalright Trofeo Vision (HID, « Type 2 »).

Module PUR : aucune E/S, aucune dépendance matérielle. On y construit et on y
parse les octets exactement tels qu'ils transitent sur le fil. Tout ce qui touche
l'USB/HID vit dans ``transport.py`` ; tout ce qui touche l'image vit dans
``render.py``. Cette séparation est volontaire : ce module est entièrement
testable sans matériel, et c'est lui que le port Swift (TrofeoKit) ré-écrira à
l'identique.

Origine des faits : reverse-engineering documenté dans ``docs/PROTOCOL.md``
(clean-room, voir la note de licence du projet). On ne copie aucun code GPL ;
on réimplémente à partir des faits du protocole.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

# --- Constantes filaires --------------------------------------------------

#: Magic de début de paquet, commun à l'init et aux frames (Type 2 / Nuvoton).
MAGIC = bytes([0xDA, 0xDB, 0xDC, 0xDD])

#: Taille fixe du paquet d'init (handshake).
INIT_PACKET_SIZE = 512

#: Tous les transferts sont alignés sur ce multiple (padding zéro en fin).
USB_ALIGN = 512

#: Octet de commande : 1 = device info (init), 2 = picture (frame).
CMD_DEVICE_INFO = 0x01
CMD_PICTURE = 0x02

#: Mode de pixel encodé dans l'octet 6 du header de frame.
MODE_JPEG = 0x00
MODE_RGB565 = 0x01


def looks_like_jpeg(data: bytes) -> bool:
    """Vrai si ``data`` commence par le magic JPEG (FF D8)."""
    return len(data) >= 2 and data[0] == 0xFF and data[1] == 0xD8


def _ceil_to_align(n: int, align: int) -> int:
    """Plus petit multiple de ``align`` supérieur ou égal à ``n``."""
    return ((n + align - 1) // align) * align


# --- Handshake / init -----------------------------------------------------


def build_init_packet() -> bytes:
    """Paquet d'init (512 o) à envoyer pour réclamer les infos device.

    Structure : MAGIC | 8 octets zéro | cmd=1 (LE u32) | 4 octets zéro,
    puis padding zéro jusqu'à 512 octets.
    """
    header = MAGIC + b"\x00" * 8 + bytes([CMD_DEVICE_INFO, 0, 0, 0]) + b"\x00" * 4
    return header.ljust(INIT_PACKET_SIZE, b"\x00")


#: PM byte connu → résolution. Le PID 0416:5302 est partagé par plusieurs
#: modèles ; c'est le PM byte (resp[5]) qui tranche la géométrie réelle.
#: 128 et 68 mènent tous deux au Trofeo Vision 6.86" 1280x480 (chemins distincts
#: dans la réf). À confirmer sur matériel : lequel renvoie *ton* écran.
_PM_RESOLUTION = {
    128: (1280, 480),
    68: (1280, 480),
    69: (1920, 440),
}


@dataclass
class Handshake:
    """Résultat parsé de la réponse d'init (512 o lus après l'envoi)."""

    valid: bool
    pm: "int | None"
    sub: "int | None"
    serial: str
    resolution: "tuple[int, int] | None"
    raw_len: int


def parse_handshake(resp: bytes) -> Handshake:
    """Valide et décode la réponse d'init.

    Critère de validité (réf) : ``len >= 20`` et ``resp[0:4] == MAGIC`` et
    ``resp[12] == CMD_DEVICE_INFO``. Tant que ce n'est pas validé, on ne pousse
    aucune frame (le device n'a pas confirmé sa géométrie).
    """
    valid = len(resp) >= 20 and resp[0:4] == MAGIC and resp[12] == CMD_DEVICE_INFO
    if not valid:
        return Handshake(False, None, None, "", None, len(resp))

    pm = resp[5]
    sub = resp[4]
    # Le serial occupe resp[20:36] (16 o) → il faut au moins 36 octets. Le vrai
    # Trofeo Vision renvoie EXACTEMENT 36 o, d'où le >= (et pas > comme on
    # pourrait le lire ailleurs : ce serait un off-by-one qui rate le serial).
    has_serial = len(resp) >= 36 and resp[16] == 0x10
    serial = resp[20:36].hex().upper() if has_serial else ""
    resolution = _PM_RESOLUTION.get(pm)
    return Handshake(True, pm, sub, serial, resolution, len(resp))


# --- Frame image ----------------------------------------------------------


def build_frame(image_data: bytes, width: int, height: int) -> bytes:
    """Construit la frame complète (header 20 o + image), paddée sur 512 o.

    Le mode (JPEG vs RGB565) est déduit du contenu de ``image_data`` : un flux
    JPEG est détecté par son magic FF D8. Pour le Trofeo 1280x480 on envoie du
    JPEG.

    Layout du header (20 octets) en mode JPEG ::

        DA DB DC DD | 02 00 | 00 00 | <W u16 LE> <H u16 LE> | 02 00 00 00 | <len u32 LE>

    En mode RGB565, l'octet 6 vaut 01 et les dimensions sont figées à 240x320
    (héritage du firmware d'origine pour les petits panneaux ; sans objet pour
    le Trofeo).
    """
    is_jpeg = looks_like_jpeg(image_data)

    header = bytearray()
    header += MAGIC
    header += bytes([CMD_PICTURE, 0x00])
    if is_jpeg:
        header += bytes([MODE_JPEG, 0x00])
        header += struct.pack("<HH", width, height)
    else:
        header += bytes([MODE_RGB565, 0x00])
        header += struct.pack("<HH", 240, 320)
    header += bytes([0x02, 0x00, 0x00, 0x00])
    header += struct.pack("<I", len(image_data))

    raw = bytes(header) + image_data
    return raw.ljust(_ceil_to_align(len(raw), USB_ALIGN), b"\x00")
