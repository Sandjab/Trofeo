# CLAUDE.md — Instructions pour l'agent d'implémentation

Pilote open-source de l'écran **Thermalright Trofeo Vision** (HID / Type 2).
Prototype Python d'abord (« first light »), puis port Swift natif destiné à être
intégré au projet **Iris** (`../Iris`).

## 1. Contexte projet

- Écran USB HID `0416:5302`, 1280×480, piloté en JPEG sur un endpoint HID.
- **`docs/PROTOCOL.md` est la source de vérité** du protocole filaire. Toute
  question « quel octet, dans quel ordre » se répond là, pas en relisant un autre
  repo.
- Cible finale : une lib Swift `TrofeoKit` consommée par Iris (voir `swift/`).

## 2. Avant de coder

- Lire `docs/PROTOCOL.md` en entier.
- Le protocole comporte des **incertitudes non levées** (PM byte, taille de
  report, ACK) — listées en §7 du protocole. Ne pas câbler en dur une hypothèse
  non vérifiée : la marquer et la faire remonter par le `first_light`.

## 3. Posture de travail

- Prototype : on privilégie la clarté et la vérifiabilité, pas l'exhaustivité.
  Le but du first light est de **lire le vrai PM byte** sur le matériel.
- S'en tenir aux règles globales (`~/.claude/CLAUDE.md`) : changements
  chirurgicaux, simplicité d'abord, échouer fort plutôt que masquer.

## 4. Vérifications obligatoires

```bash
cd python && python3 -m pytest tests/ -q     # protocole pur, sans matériel
```

- Les tests de `protocol.py` doivent passer **sans matériel ni hidapi installé**.
- Le `first_light.py` exige le matériel branché : ne pas prétendre l'avoir
  « validé » sans la sortie réelle de l'écran.

## 5. Conventions code

- **Python 3.9+**, `from __future__ import annotations` partout.
- **`protocol.py` reste PUR** : zéro E/S, zéro import matériel. C'est lui qu'on
  teste et que Swift réécrira à l'identique.
- Tout l'USB/HID vit dans `transport.py` ; tout Pillow vit dans `render.py`. Ne
  pas mélanger ces frontières (elles structurent aussi le port Swift).
- Tests : encoder le *pourquoi* (un octet faux = image corrompue / device qui
  rejette), pas seulement la valeur.

## 6. Clean-room & licence — NON négociable

- Le repo de référence `Lexonight1/thermalright-trcc-linux` est **GPL-3.0**. On
  s'en sert pour **comprendre** le protocole, **jamais** pour copier du code.
- On réimplémente à partir des **faits** de `docs/PROTOCOL.md`. Licence du projet :
  **MIT** (compatible avec l'intégration Iris, MIT).
- Ne jamais coller de code source GPL dans ce repo (Python ou Swift).

## 7. Protocole (résumé)

Init 512 o `DA DB DC DD … 01 …` → lire 512 o → valider MAGIC + `resp[12]==0x01` →
`PM = resp[5]` → frame JPEG avec header 20 o (`W,H,len` little-endian) paddée sur
512 o, un seul write, pas d'ACK. **Détails exacts : `docs/PROTOCOL.md`.**

## 8. Build & run

```bash
# Lib native HID (une fois)
brew install hidapi

# Env Python
cd python
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Tests (sans matériel)
pytest tests/ -q

# First light (matériel branché)
# macOS : pointer libhidapi de brew (sinon ImportError au chargement de `hid`).
export DYLD_FALLBACK_LIBRARY_PATH="$(brew --prefix hidapi)/lib"
python scripts/first_light.py            # handshake + mire
python scripts/first_light.py --dump-only
```

> **Note dyld** : poser `DYLD_FALLBACK_LIBRARY_PATH` *à l'intérieur* du process
> Python (os.environ avant l'import) ne marche PAS — dyld lit la variable au
> lancement uniquement. Elle doit être dans l'environnement du shell.

## 9. Port Swift / macOS — ⚠️ plan initial invalidé

**Le plan « TrofeoKit via IOHIDManager » est un cul-de-sac pour le streaming**
(prouvé sur matériel, voir `docs/MACOS_FEASIBILITY.md`) : ce device est sur une
interface **HID-class** que IOHIDFamily verrouille ; IOHIDManager ne peut émettre
qu'**une** frame puis ne peut pas faire le clear-halt/reset requis ; libusb ne peut
pas claim l'interface (Errno 13, même en root).

- **Ne pas** repartir sur un transport IOHIDManager/hidapi pour streamer.
- Décision d'architecture **en attente** (cf. README, feuille de route) :
  daemon Linux déporté (recommandé) / DriverKit dext (lourd, incertain) / VM passthrough.
- Le découpage `Protocol` (pur) / `Render` reste réutilisable quel que soit le choix ;
  seul le `Transport` est impacté.

## 10. Ce qu'il ne faut PAS faire

- Copier du code GPL (réf) dans ce repo.
- Déduire la résolution du **PID** : elle vient du **PM byte** au handshake.
- Supposer le type d'endpoint / la taille de report sans le vérifier sur matériel.
- Tenter un `claim_interface` libusb sur une interface HID macOS (IOKit la saisit).
- Prétendre « ça marche » sur l'écran sans la sortie réelle du first light.

## 11. Incertitudes à valider sur matériel

Voir `docs/PROTOCOL.md` §7 : PM byte (128 vs 68), taille max de report, préfixe
Report ID, absence d'ACK. Le `first_light.py` imprime ce qu'il faut pour trancher.
