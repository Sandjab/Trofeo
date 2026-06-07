# swift/ — port natif TrofeoKit (à venir)

Placeholder. Le port Swift démarre **une fois le first light Python validé**
(PM byte réel confirmé, taille de report et préfixe Report ID levés sur matériel).

## Forme cible

- **`TrofeoKit`** : une bibliothèque **SwiftPM autonome**, consommée par
  [Iris](../../Iris) comme dépendance (cohérent avec l'archi modulaire d'Iris :
  `IrisKit` / `irisd` / `IrisAppCore`).
- **Transport : IOHIDManager direct via IOKit**, bridgé Swift. **Aucune**
  dépendance hidapi ou libusb au runtime — le Trofeo est HID natif, donc pas de
  driver tiers ni de permissions élevées.

## Découpage prévu (miroir du prototype Python)

| Unité | Rôle | Équivalent Python |
|---|---|---|
| `Protocol` | pur, testable : paquets / handshake / frame | `trofeo/protocol.py` |
| `Transport` | IOHIDManager (open par VID/PID, write/read de reports) | `trofeo/transport.py` |
| `Render` | image → JPEG (CoreGraphics / ImageIO) | `trofeo/render.py` |

## Source de vérité

Le protocole filaire est figé dans [`../docs/PROTOCOL.md`](../docs/PROTOCOL.md).
Le port Swift s'écrit **à partir de ce document** (clean-room, MIT), pas en
recopiant le code de référence GPL.

## Notes d'implémentation IOHIDManager (préparatoires)

- Ouverture : `IOHIDManagerCreate` → matching `{ VendorID: 0x0416, ProductID: 0x5302 }`
  → `IOHIDManagerOpen`.
- Écriture : `IOHIDDeviceSetReport(device, kIOHIDReportTypeOutput, reportID, data, len)`.
  Gérer le Report ID `0x00` comme côté hidapi (voir `PROTOCOL.md` §2).
- Lecture du handshake : report d'entrée via `IOHIDDeviceGetReport` /
  `IOHIDDeviceRegisterInputReportCallback`.
- À valider : taille max de report pour pousser un JPEG entier en un `SetReport`.
