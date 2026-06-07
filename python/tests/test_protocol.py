"""Tests du protocole filaire — PURS, sans matériel ni hidapi.

Chaque test encode *pourquoi* l'octet compte, pas seulement *quoi* il vaut :
un mauvais magic, un mauvais ordre d'octets ou un padding raté = image corrompue
ou device qui rejette. Si la logique métier du protocole change, ces tests
doivent casser.
"""

from __future__ import annotations

import struct

from trofeo import protocol


# --- Init / handshake -----------------------------------------------------


def test_init_packet_shape():
    pkt = protocol.build_init_packet()
    # Taille fixe : le firmware attend exactement 512 o.
    assert len(pkt) == protocol.INIT_PACKET_SIZE
    # Magic + commande : sans ça le device ne répond pas avec ses infos.
    assert pkt[0:4] == protocol.MAGIC
    assert pkt[12] == protocol.CMD_DEVICE_INFO
    # Le reste est du remplissage zéro.
    assert pkt[16:] == b"\x00" * (protocol.INIT_PACKET_SIZE - 16)


def _fake_response(pm: int = 128, sub: int = 0, serial: bytes | None = None) -> bytes:
    resp = bytearray(512)
    resp[0:4] = protocol.MAGIC
    resp[4] = sub
    resp[5] = pm
    resp[12] = protocol.CMD_DEVICE_INFO
    if serial is not None:
        resp[16] = 0x10  # marqueur « serial présent »
        resp[20:20 + len(serial)] = serial
    return bytes(resp)


def test_parse_handshake_valid_pm128():
    hs = protocol.parse_handshake(_fake_response(pm=128))
    assert hs.valid is True
    assert hs.pm == 128
    # PM 128 doit résoudre le Trofeo Vision 1280x480.
    assert hs.resolution == (1280, 480)


def test_parse_handshake_rejects_bad_magic():
    bad = bytearray(_fake_response())
    bad[0] = 0x00  # magic cassé
    hs = protocol.parse_handshake(bytes(bad))
    # On NE doit PAS considérer le device prêt : géométrie non confirmée.
    assert hs.valid is False
    assert hs.resolution is None


def test_parse_handshake_rejects_wrong_cmd():
    bad = bytearray(_fake_response())
    bad[12] = 0x02  # pas une réponse device-info
    assert protocol.parse_handshake(bytes(bad)).valid is False


def test_parse_handshake_extracts_serial():
    hs = protocol.parse_handshake(_fake_response(serial=bytes(range(16))))
    assert hs.serial == bytes(range(16)).hex().upper()


def test_parse_handshake_too_short():
    assert protocol.parse_handshake(b"\xda\xdb").valid is False


# Réponse RÉELLE capturée sur le Trofeo Vision V1.02 (first light, 2026-06-07).
# Exactement 36 octets — c'est ce contrat-là que le parsing doit honorer, pas une
# version idéalisée de 512 o. Verrouille notamment l'extraction du serial (qui a
# révélé un off-by-one : >36 ratait le serial, il faut >=36).
REAL_HANDSHAKE = bytes.fromhex(
    "dadbdcdd018000000000000001000000100000004250304b3837340e00a1af1a4302d778"
)


def test_parse_handshake_real_trofeo_vision():
    assert len(REAL_HANDSHAKE) == 36
    hs = protocol.parse_handshake(REAL_HANDSHAKE)
    assert hs.valid is True
    assert hs.pm == 128  # 0x80 : c'est CE chemin que prend le Trofeo Vision réel
    assert hs.sub == 1
    assert hs.resolution == (1280, 480)
    # Serial présent dès 36 o (pas 37) : la régression à ne plus jamais réintroduire.
    assert hs.serial == "4250304B3837340E00A1AF1A4302D778"
    assert hs.raw_len == 36


# --- Frame image ----------------------------------------------------------

# Un JPEG minimal factice : ce qui compte ici c'est le magic FF D8 (détection
# du mode), pas la validité de l'image.
FAKE_JPEG = b"\xff\xd8" + b"\x11" * 100 + b"\xff\xd9"


def test_frame_header_layout_jpeg():
    frame = protocol.build_frame(FAKE_JPEG, 1280, 480)
    assert frame[0:4] == protocol.MAGIC
    assert frame[4] == protocol.CMD_PICTURE
    assert frame[6] == protocol.MODE_JPEG
    # Largeur/hauteur en little-endian : un mauvais ordre => image déformée.
    assert struct.unpack_from("<HH", frame, 8) == (1280, 480)
    # Taille du payload en u32 LE : un device qui lit trop/pas assez corrompt tout.
    assert struct.unpack_from("<I", frame, 16)[0] == len(FAKE_JPEG)
    # Le payload est préservé tel quel juste après le header de 20 o.
    assert frame[20:20 + len(FAKE_JPEG)] == FAKE_JPEG


def test_frame_is_512_aligned():
    frame = protocol.build_frame(FAKE_JPEG, 1280, 480)
    # Le firmware attend des transferts alignés sur 512 o.
    assert len(frame) % protocol.USB_ALIGN == 0
    # Le padding est du zéro en fin de buffer.
    assert frame[20 + len(FAKE_JPEG):] == b"\x00" * (len(frame) - 20 - len(FAKE_JPEG))


def test_frame_already_aligned_not_overgrown():
    # Charge calibrée pour que header(20)+payload tombe pile sur un multiple de 512.
    payload = b"\xff\xd8" + b"\x00" * (512 - 20 - 2)
    frame = protocol.build_frame(payload, 1280, 480)
    assert len(frame) == 512  # pas de bloc de padding superflu


def test_looks_like_jpeg():
    assert protocol.looks_like_jpeg(FAKE_JPEG) is True
    assert protocol.looks_like_jpeg(b"\x00\x01") is False
    assert protocol.looks_like_jpeg(b"") is False
