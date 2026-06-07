# Trofeo

Pilote open-source pour l'écran **Thermalright Trofeo Vision** (6,86″ LCD,
1280 × 480) sous macOS — sans le logiciel propriétaire Windows (TRCC).

> **Statut :** prototype fonctionnel sur macOS. ✅ Affichage **live à ~5 fps**, stable
> et fluide, via la « reset-loop » (`reset libusb → handshake → frame hidapi`) qui
> contourne le verrouillage de l'interface HID par IOHIDFamily. Voir
> [`docs/MACOS_FEASIBILITY.md`](docs/MACOS_FEASIBILITY.md).

## Pourquoi

L'écran est livré avec **TRCC** (Thermalright LCD Control Center), un logiciel
.NET fermé et **Windows uniquement**. Ce projet pilote l'écran directement, en
HID natif, pour pouvoir l'utiliser ailleurs — et à terme l'intégrer au projet
[**Iris**](../Iris) via une lib Swift native.

## Le matériel

| | |
|---|---|
| Modèle | Thermalright Trofeo Vision, hardware V1.02 |
| Écran | 6,86″ Full Color LCD, **1280 × 480** |
| USB | VID `0x0416` · PID `0x5302` — classe **HID** (« Type 2 ») |

C'est un device **HID natif** : sur macOS il se pilote via **IOHIDManager**
(IOKit), sans driver tiers ni permissions élevées.

## Démarrage rapide (prototype Python)

```bash
brew install hidapi libusb          # natifs : écriture frame (hidapi) + reset (libusb)

cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests du protocole (aucun matériel requis)
pytest tests/ -q

# macOS : les libs de brew ne sont pas sur le chemin du loader -> on les pointe.
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix hidapi)/lib:$(brew --prefix libusb)/lib"

# Affichage live (le prototype) : horloge + infos système, ~3 fps, Ctrl-C pour arrêter
python scripts/run.py
python scripts/run.py --fps 2 --duration 30

# First light (diagnostic) : handshake + dump du PM byte, puis une mire 1280x480
python scripts/first_light.py
python scripts/first_light.py --dump-only     # handshake seul
```

> Validé sur Trofeo Vision V1.02 réel (2026-06-07) : PM=128 → 1280×480, affichage
> live ~5 fps stable via la reset-loop.

## Structure

```
Trofeo/
├── CLAUDE.md            instructions projet pour l'agent
├── docs/
│   ├── PROTOCOL.md      spec filaire du HID Type 2 (source de vérité)
│   └── MACOS_FEASIBILITY.md  pourquoi/comment la reset-loop (le mur HID + son contournement)
├── python/
│   ├── trofeo/
│   │   ├── protocol.py  PUR : paquets/handshake/frame (testé sans matériel)
│   │   ├── transport.py reset-loop : reset (pyusb) + handshake/write (hidapi)
│   │   └── render.py    mire + tableau de bord + JPEG (Pillow)
│   ├── scripts/run.py          affichage live (le prototype)
│   ├── scripts/first_light.py  diagnostic handshake + 1 frame
│   ├── experiments/            diagnostics matériels (trace reproductible)
│   └── tests/test_protocol.py
└── swift/               port natif (IOUSBHost reset + IOHIDManager) — à venir
```

## Feuille de route

1. **First light** — handshake + image. ✅ **Fait** (PM=128 → 1280×480).
2. **Mur macOS** (interface HID verrouillée par IOHIDFamily) → **contourné par la
   reset-loop**. ✅ Affichage live ~5 fps stable. Voir [`docs/MACOS_FEASIBILITY.md`](docs/MACOS_FEASIBILITY.md).
3. **Enrichir le prototype** : contenu (métriques, jauges), cadence configurable, robustesse.
4. **Port Swift** — `IOUSBHost` reset + `IOHIDManager` SetReport (IOKit pur), pour
   intégration dans **Iris**.

## Protocole & clean-room

Le protocole est décrit dans [`docs/PROTOCOL.md`](docs/PROTOCOL.md). Il a été
reconstitué par reverse-engineering, en s'appuyant sur le projet **GPL-3.0**
[`Lexonight1/thermalright-trcc-linux`](https://github.com/Lexonight1/thermalright-trcc-linux)
**pour comprendre le protocole, pas pour copier son code**. Ce projet réimplémente
tout de zéro à partir de la description factuelle, afin de rester sous licence
permissive.

Merci à ce projet de référence et à l'effort de reverse-engineering de la
communauté autour des écrans Thermalright.

## Licence

[MIT](LICENSE).
