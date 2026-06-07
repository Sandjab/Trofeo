# TrofeoKit — port Swift natif

Port IOKit pur de la reset-loop (cf. [`../docs/MACOS_FEASIBILITY.md`](../docs/MACOS_FEASIBILITY.md)),
sans dépendance tierce. Destiné à être consommé par [Iris](../../Iris).

## Découpage

| Fichier | Rôle | Équivalent Python | Vérifié |
|---|---|---|---|
| `Sources/TrofeoKit/Protocol.swift` | pur : init / handshake / frame | `trofeo/protocol.py` | ✅ `swift test` 11/11 |
| `Sources/TrofeoKit/Render.swift` | CoreGraphics/CoreText → JPEG (ImageIO) | `trofeo/render.py` | ✅ rendu image conforme |
| `Sources/TrofeoKit/Transport.swift` | reset-loop : IOUSBLib reset + IOHIDManager SetReport | `trofeo/transport.py` | ✅ **validé matériel** (30/30 frames, ~2 fps) |
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

# Avec l'écran branché (à valider) :
.build/debug/trofeo-cli pattern            # 1 mire
.build/debug/trofeo-cli run 30             # horloge live ~3 fps, 30 s
```

## Validé sur matériel (2026-06-07)

`trofeo-cli run 15` → **30/30 frames, 0 ratée, ~2 fps**, écran piloté en continu.
Détail clé : `USBDeviceReEnumerate` exige d'abord `USBDeviceOpen` au niveau device
(sinon `kIOReturnNotOpen 0xE00002CD`) — on ouvre le device, pas l'interface HID.

## Améliorations possibles

- **Cadence** : ~2 fps (la ré-énumération IOKit + un `usleep` de pacing). On peut viser
  plus haut en retirant le pacing et/ou en affinant l'attente de ré-énumération.
- **Handshake** : on ne lit pas la réponse (input-report callback) — on s'appuie sur le
  succès des SetReport ; ça marche, à ajouter seulement si besoin.
- **Métriques** : CLI = load + uptime ; CPU%/RAM% (host_statistics) à porter depuis psutil.

## Source de vérité

Protocole : [`../docs/PROTOCOL.md`](../docs/PROTOCOL.md). Clean-room, MIT.
