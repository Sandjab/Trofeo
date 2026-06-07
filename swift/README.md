# TrofeoKit — port Swift natif

Port IOKit pur de la reset-loop (cf. [`../docs/MACOS_FEASIBILITY.md`](../docs/MACOS_FEASIBILITY.md)),
sans dépendance tierce. Destiné à être consommé par [Iris](https://github.com/Sandjab/Iris).

## Découpage

| Fichier | Rôle | Équivalent Python | Vérifié |
|---|---|---|---|
| `Sources/TrofeoKit/Protocol.swift` | pur : init / handshake / frame | `trofeo/protocol.py` | ✅ `swift test` 11/11 |
| `Sources/TrofeoKit/Render.swift` | CoreGraphics/CoreText → JPEG (ImageIO) | `trofeo/render.py` | ✅ rendu image conforme |
| `Sources/TrofeoKit/Transport.swift` | reset-loop : IOUSBLib reset + IOHIDManager SetReport | `trofeo/transport.py` | ✅ **validé matériel** (94 frames, ~8 fps) |
| `Sources/trofeo-cli/main.swift` | CLI (run / pattern / reset / preview) | `scripts/run.py` | ✅ pilote l'écran |

## Le cycle (Transport)

```
reset (IOUSBLib USBDeviceReEnumerate, niveau device, sans claim de l'iface HID)
  -> ré-énumération -> IOHIDDeviceSetReport(init) -> IOHIDDeviceSetReport(frame) -> lock
```

`IOHIDDeviceSetReport` prend le reportID séparément (0) et les données **sans** préfixe
(contrairement à hidapi). Le reset niveau device ne requiert pas de claim de l'interface
HID — c'est ce qui rend la chose possible alors que IOHIDFamily la verrouille.

## Build & run

```bash
cd swift
swift build
swift test                      # Protocol : 11/11

# Sans matériel : rend le design en image
.build/debug/trofeo-cli preview            # -> /tmp/swift_dashboard.jpg + swift_pattern.jpg

# Avec l'écran branché :
.build/debug/trofeo-cli pattern            # 1 mire
.build/debug/trofeo-cli run                 # horloge live, cadence max (~8 fps), Ctrl-C
.build/debug/trofeo-cli run 30 3            # 30 s, throttle à 3 fps (ménage les resets)
```

## Validé sur matériel (2026-06-07)

`trofeo-cli run 12` → **94 frames, 0 ratée, ~8 fps**, écran piloté en continu, rendu stable.
Détail clé : `USBDeviceReEnumerate` exige d'abord `USBDeviceOpen` au niveau device
(sinon `kIOReturnNotOpen 0xE00002CD`) — on ouvre le device, pas l'interface HID.

## Notes & améliorations possibles

- **Cadence** : ~8 fps en max (un cycle = reset + ré-énum + 2 SetReport). Argument fps
  optionnel (`run <sec> <fps>`) pour throttler — ~8 resets/s en continu, à modérer en 24/7.
- **Handshake** : on ne lit pas la réponse (input-report callback) — on s'appuie sur le
  succès des SetReport ; ça marche, à ajouter seulement si besoin.
- **Métriques** : CLI = load + uptime ; CPU%/RAM% (host_statistics) à porter depuis psutil.

## Source de vérité

Protocole : [`../docs/PROTOCOL.md`](../docs/PROTOCOL.md). Clean-room, MIT.
