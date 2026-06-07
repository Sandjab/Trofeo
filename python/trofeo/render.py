"""Rendu d'image pour le Trofeo : mire de test + encodage JPEG.

Seule couche qui dépend de Pillow. Le port Swift fera l'équivalent avec
CoreGraphics ; la frontière (produire des octets JPEG d'une image WxH) est la
même.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw, ImageFont

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


def _bar_color(frac: float) -> tuple:
    """Vert / orange / rouge selon le taux de remplissage."""
    if frac < 0.75:
        return (90, 200, 140)
    if frac < 0.90:
        return (230, 175, 70)
    return (230, 90, 90)


def dashboard(clock: str, date: str, bars=None, lines=None,
              width: int = WIDTH, height: int = HEIGHT) -> Image.Image:
    """Tableau de bord : grande horloge + date à gauche ; barres + lignes à droite.

    ``bars`` : liste de ``(label, fraction)`` rendues en jauges colorées.
    ``lines`` : liste de ``(label, valeur)`` rendues en texte.
    """
    img = Image.new("RGB", (width, height), (12, 14, 22))
    draw = ImageDraw.Draw(img)

    # Zone gauche : horloge + date.
    clock_font = ImageFont.load_default(size=168)
    date_font = ImageFont.load_default(size=46)
    left_cx = 300
    draw.text((left_cx, 205), clock, fill=(240, 242, 255), anchor="mm", font=clock_font)
    draw.text((left_cx, 320), date, fill=(150, 165, 200), anchor="mm", font=date_font)

    draw.line([(600, 50), (600, height - 50)], fill=(40, 44, 60), width=2)

    # Zone droite : jauges puis lignes.
    label_font = ImageFont.load_default(size=40)
    rx0, rx1 = 650, width - 50
    y = 72
    for label, frac in (bars or []):
        frac = max(0.0, min(1.0, frac))
        draw.text((rx0, y), label, fill=(170, 185, 215), anchor="lm", font=label_font)
        draw.text((rx1, y), f"{int(frac * 100)}%", fill=(240, 242, 255), anchor="rm", font=label_font)
        by = y + 32
        draw.rectangle([rx0, by, rx1, by + 22], fill=(30, 34, 48))
        draw.rectangle([rx0, by, rx0 + int((rx1 - rx0) * frac), by + 22], fill=_bar_color(frac))
        y += 96
    for label, value in (lines or []):
        draw.text((rx0, y), label, fill=(170, 185, 215), anchor="lm", font=label_font)
        draw.text((rx1, y), value, fill=(220, 225, 240), anchor="rm", font=label_font)
        y += 58

    return img
