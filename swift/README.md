# TrofeoKit — port Swift natif

Port IOKit pur de la reset-loop (cf. [`../docs/MACOS_FEASIBILITY.md`](../docs/MACOS_FEASIBILITY.md)),
sans dépendance tierce. Destiné à être consommé par [Iris](../../Iris).

## Découpage

| Fichier | Rôle | Équivalent Python | Vérifié |
|---|---|---|---|
| `Sources/TrofeoKit/Protocol.swift` | pur : init / handshake / frame | `trofeo/protocol.py` | ✅ `swift test` 11/11 |
| `Sources/TrofeoKit/Render.swift` | CoreGraphics/CoreText → JPEG (ImageIO) | `trofeo/render.py` | ✅ rendu image conforme |
| `Sources/TrofeoKit/Transport.swift` | reset-loop : IOUSBLib reset + IOHIDManager SetReport | `trofeo/transport.py` | ⚠️ compile, **test matériel en attente** |
| `Sources/trofeo-cli/main.swift` | CLI (run / pattern / reset / preview) | `scripts/run.py` | ⚠️ idem |

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

## Points à valider sur matériel (au retour)

- Le **reset IOUSBLib** ré-énumère bien le device (équivalent du `reset_device()` pyusb).
- `IOHIDDeviceSetReport` accepte init puis frame après ré-énumération.
- **Non implémenté volontairement** : lecture de la réponse handshake (interrupt-IN via
  input-report callback). On s'appuie sur le succès des SetReport ; à ajouter si le
  firmware l'exige.
- Métriques : le CLI affiche load + uptime ; CPU%/RAM% (host_statistics) restent à porter
  depuis la version Python (psutil).

## Source de vérité

Protocole : [`../docs/PROTOCOL.md`](../docs/PROTOCOL.md). Clean-room, MIT.
