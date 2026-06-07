"""Rendu d'image pour le Trofeo : mire de test + encodage JPEG.

Seule couche qui dépend de Pillow. Le port Swift fera l'équivalent avec
CoreGraphics ; la frontière (produire des octets JPEG d'une image WxH) est la
même.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

WIDTH = 1280
HEIGHT = 480


def test_pattern(width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    """Mire de « first light » : repères de coins, flèche « HAUT », barres RGB.

    Pensée pour vérifier d'un coup d'œil, sur l'écran réel : l'orientation
    (la flèche doit pointer vers le haut, les coins doivent être lisibles dans
    le bon sens) et l'ordre des couleurs (R/V/B annoncés sous les barres).
    """
    img = Image.new("RGB", (width, height), (8, 8, 12))
    draw = ImageDraw.Draw(img)

    # Cadre 1 px pour repérer les bords / le débordement éventuel.
    draw.rectangle([0, 0, width - 1, height - 1], outline=(90, 90, 90))

    # Repères de coins.
    pad = 12
    for label, x, y, anchor in (
        ("TL", pad, pad, "la"),
        ("TR", width - pad, pad, "ra"),
        ("BL", pad, height - pad, "ld"),
        ("BR", width - pad, height - pad, "rd"),
    ):
        draw.text((x, y), label, fill=(230, 230, 230), anchor=anchor)

    # Barres de couleur pour contrôler l'ordre des canaux.
    bars = [
        ("R", (255, 0, 0)),
        ("V", (0, 255, 0)),
        ("B", (0, 0, 255)),
        ("C", (0, 255, 255)),
        ("M", (255, 0, 255)),
        ("J", (255, 255, 0)),
        ("W", (255, 255, 255)),
    ]
    bw = width // len(bars)
    bar_top = height - 90
    for i, (label, color) in enumerate(bars):
        x0 = i * bw
        draw.rectangle([x0, bar_top, x0 + bw - 2, height - 30], fill=color)
        draw.text((x0 + bw // 2, height - 22), label, fill=(230, 230, 230), anchor="ma")

    # Flèche « HAUT » au centre + libellé résolution.
    cx, cy = width // 2, height // 2
    draw.polygon(
        [(cx, cy - 70), (cx - 36, cy + 6), (cx - 12, cy + 6),
         (cx - 12, cy + 60), (cx + 12, cy + 60), (cx + 12, cy + 6), (cx + 36, cy + 6)],
        fill=(255, 210, 0),
    )
    draw.text((cx, cy - 96), "HAUT", fill=(255, 210, 0), anchor="md")
    draw.text((cx, 24), f"TROFEO  {width}x{height}", fill=(255, 255, 255), anchor="ma")

    return img


def rotate(img: Image.Image, degrees: int) -> Image.Image:
    """Rotation côté encodage (l'orientation se gère AVANT le JPEG, pas par une
    commande device). ``degrees`` horaire."""
    if degrees % 360 == 0:
        return img
    return img.rotate(-degrees, expand=True)


def to_jpeg(img: Image.Image, quality: int = 95) -> bytes:
    """Encode ``img`` en JPEG baseline."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()
