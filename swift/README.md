# swift/ — port natif (plan initial invalidé)

> ⚠️ **Le plan « `TrofeoKit` via IOHIDManager » est abandonné pour le streaming.**
> Prouvé sur matériel : ce device est sur une interface **HID-class** verrouillée par
> IOHIDFamily ; IOHIDManager n'émet qu'**une** frame puis ne peut pas faire le
> clear-halt/reset requis, et libusb ne peut pas claim l'interface (Errno 13). Détails
> et options : [`../docs/MACOS_FEASIBILITY.md`](../docs/MACOS_FEASIBILITY.md).

## Où le Swift reste pertinent

Pas pour parler USB à l'écran sur macOS (impossible en userspace). Mais selon
l'architecture retenue (décision en attente), un composant Swift peut servir de
**client** côté Mac :

- compose les frames / collecte les métriques système,
- les pousse en **réseau** vers un daemon Linux déporté (RPi) branché à l'écran,
- côté Iris : intégration en tant qu'émetteur de données, pas en tant que pilote USB.

Le découpage du prototype Python (`Protocol` pur / `Render`) reste réutilisable en
Swift ; seul le `Transport` USB ne se porte pas sur macOS.
