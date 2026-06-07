"""Pilote expérimental de l'écran Thermalright Trofeo Vision (HID / Type 2).

Prototype de validation de protocole (« first light »). Voir ``docs/PROTOCOL.md``
pour la spec filaire et le README pour le statut du projet.
"""

from __future__ import annotations

__version__ = "0.0.1"

from . import protocol, render

__all__ = ["protocol", "render", "__version__"]
