# Trofeo

Pilote open-source pour l'écran **Thermalright Trofeo Vision** (6,86″ LCD,
1280 × 480) sous macOS — sans le logiciel propriétaire Windows (TRCC).

> **Statut :** first light **validé** sur matériel réel (handshake + 1 image
> affichée), mais ⚠️ **un mur macOS est apparu** : ce device est sur une interface
> **HID-class**, dont IOHIDFamily s'empare en exclusif — on ne peut **pas** streamer
> des frames vers lui en userspace sur macOS. Détails et options dans
> [`docs/MACOS_FEASIBILITY.md`](docs/MACOS_FEASIBILITY.md). **Décision d'architecture
> en attente.**

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
brew install hidapi                 # lib HID native

cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests du protocole (aucun matériel requis)
pytest tests/ -q

# First light (écran branché) : handshake, dump du PM byte, puis une mire 1280x480
# macOS : libhidapi de brew n'est pas sur le chemin du loader -> on le pointe.
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix hidapi)/lib"
python scripts/first_light.py
python scripts/first_light.py --dump-only     # handshake seul
```

> Validé sur un Trofeo Vision V1.02 réel (2026-06-07) : handshake OK, **PM byte =
> 128 → 1280×480**, et un JPEG de ~37 Ko poussé en un seul transfert s'affiche.

Sur l'écran, la mire doit afficher une flèche pointant vers le **HAUT** et des
barres **R / V / B** dans l'ordre — de quoi vérifier orientation et couleurs d'un
coup d'œil.

## Structure

```
Trofeo/
├── CLAUDE.md            instructions projet pour l'agent
├── docs/PROTOCOL.md     spec filaire du HID Type 2 (source de vérité)
├── python/              prototype : transport hidapi + protocole + rendu
│   ├── trofeo/
│   │   ├── protocol.py  PUR : paquets/handshake/frame (testé sans matériel)
│   │   ├── transport.py HID via hidapi
│   │   └── render.py    mire de test + JPEG (Pillow)
│   ├── scripts/first_light.py
│   └── tests/test_protocol.py
└── swift/               port natif TrofeoKit (IOHIDManager) — à venir
```

## Feuille de route

1. **First light Python** — handshake + image. ✅ **Fait** (PM=128 → 1280×480, mire affichée).
2. ⚠️ **Mur macOS découvert** : streaming impossible en userspace (interface HID-class
   verrouillée par IOHIDFamily). Voir [`docs/MACOS_FEASIBILITY.md`](docs/MACOS_FEASIBILITY.md).
3. **Décision d'architecture** (en attente) :
   - Daemon Linux déporté (RPi) + client Mac réseau — *recommandé*.
   - DriverKit dext natif — lourd, succès incertain.
   - VM Linux + USB passthrough — à vérifier.

> ~~Port Swift `TrofeoKit` via IOHIDManager~~ : **abandonné pour le streaming** —
> IOHIDManager ne peut pas émettre les transferts de contrôle requis (cul-de-sac
> prouvé). Un composant Swift reste pertinent côté *client* selon l'architecture choisie.

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
