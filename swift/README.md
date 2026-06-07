# swift/ — port natif (à venir)

Le port Swift reprend la **reset-loop** validée côté Python (cf.
[`../docs/MACOS_FEASIBILITY.md`](../docs/MACOS_FEASIBILITY.md)), en **IOKit pur**,
sans dépendance tierce :

| Étape du cycle | API macOS | Équivalent Python |
|---|---|---|
| reset device (réveille le lock) | **IOUSBHost** (`IOUSBHostDevice`, re-enumerate/reset) | pyusb `reset_device()` |
| handshake + write frame | **IOHIDManager** (`IOHIDDeviceSetReport`, output) | hidapi `hid.Device.write` |
| compose la frame (pur) | — | `trofeo/protocol.py` |
| rendu image → JPEG | CoreGraphics / ImageIO | `trofeo/render.py` |

> Le reset se fait au niveau **device** (IOUSBHost), donc il ne nécessite **pas** de
> claim de l'interface HID — c'est précisément ce qui le rend possible alors que
> IOHIDFamily tient l'interface. La frame, elle, part par `IOHIDDeviceSetReport`.

## Forme cible

- **`TrofeoKit`** : bibliothèque SwiftPM autonome, consommée par
  [Iris](../../Iris) en dépendance (cohérent avec son archi `IrisKit`/`irisd`/…).
- Découpage miroir du Python : `Protocol` (pur, testable) / `Transport` (reset-loop
  IOKit) / `Render` (CoreGraphics).

## Points de vigilance (hérités du prototype)

- **Cadence** : ~5 fps plafond ; viser 2-3 fps suffit pour horloge/métriques et
  réduit la fréquence des resets USB (innocuité long terme non établie).
- **Robustesse** : retry de ré-énumération après reset (le device disparaît ~100 ms),
  comme `TrofeoDevice._open_with_handshake` côté Python.

## Source de vérité

Protocole filaire : [`../docs/PROTOCOL.md`](../docs/PROTOCOL.md). Le port s'écrit à
partir de ce document (clean-room, MIT), pas en recopiant le code de référence GPL.
