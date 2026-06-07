# Faisabilité macOS — verdict (2026-06-07)

> **Décision en attente.** Ce document fige ce qu'on a établi pour pouvoir trancher
> l'architecture plus tard. Il s'appuie sur des mesures matérielles réelles (Trofeo
> Vision V1.02, macOS Apple Silicon) + recherche du code de référence, des issues
> GitHub et de la doc Apple.

## Verdict — RÉSOLU (2026-06-07)

**Il existe une voie userspace viable sur macOS : la « reset-loop ».** Validée sur
matériel à **~5 fps stable et fluide** (125/125 refresh sur 25 s, 0 échec). Pas de
kext, pas de firmware, pas de daemon déporté.

Le problème de fond reste réel — les endpoints data (EP 0x02 OUT) sont sur une
**interface HID (0x03)** dont **IOHIDFamily s'empare en exclusif**, donc on ne peut
ni la claim en libusb (Errno 13) ni envoyer plus d'une frame via IOHIDManager (lock).
**Le contournement :** un **`libusb reset_device()`** (opération niveau *device*, qui
ne requiert PAS de claim de l'interface) **réveille** le device après chaque frame.
D'où le cycle :

```
reset (libusb) -> handshake -> 1 frame (hidapi/IOHIDManager) -> [lock] -> reset -> ...
```

Un cycle complet ≈ **0,21 s** (reset + handshake + frame 37 Ko), soit ~5 fps. Comme
on repasse une frame bien avant le revert firmware (~2 s), l'image reste affichée en
continu. **Limites honnêtes :** plafond ~5 fps (pas de vidéo fluide) ; on déclenche un
reset USB ~3-5×/s, dont l'innocuité 24/7 sur le long terme n'est **pas** établie (à
surveiller : stabilité, logs USB, usure).

> Implémentation : `python/trofeo/transport.py` (`TrofeoDevice`), boucle dans
> `python/scripts/run.py`. Port Swift visé : **`IOUSBHost` reset + `IOHIDManager`
> SetReport**, en IOKit pur (zéro dépendance tierce) — le plan natif Mac est ressuscité.

### Pourquoi le contournement est nécessaire (les murs directs, toujours vrais)

## Les trois murs

| Voie | Résultat | Statut |
|---|---|---|
| **libusb / pyusb** | `claim_interface(0)` → `kIOReturnExclusiveAccess` → **Errno 13, même en root** (pas une question de permission) | **mesuré** |
| **hidapi / IOHIDManager** | 1ʳᵉ frame OK et affichée, puis **tout `SetReport` time out** (le firmware semble exiger un clear-halt/reset que l'API HID ne peut pas émettre) → **lock après 1 frame, replug requis** | **mesuré** |
| **DriverKit / USBDriverKit dext** | seule voie « native », mais pour une interface **HID-class** la pile HID d'Apple (`AppleUserHIDDrivers`) **gagne le matching** par défaut → succès **incertain** + coût disproportionné (entitlement vendor-ID, app notarisée, system extension approuvée par l'utilisateur) | documenté |

### L'insight qui explique tout

La « réussite macOS » de l'écosystème — l'app Swift **MacTR** — pilote le Trofeo
**9.16 = `0416:5408`, qui expose une interface VENDOR (0xff), pas HID** ; libusb
*peut* claim une interface vendor sur macOS. Notre **6.86″ = `5302` est HID-class**
→ c'est précisément la porte fermée. La réf elle-même n'a **aucun chemin HID macOS**
(`macos.py` = SCSI/libusb only ; mainteneur : *« i don't own a mac, macos is
backburner »* ; seul testeur macOS sur un 1280×480 → crash, jamais de stream).

### Détail mécaniste (supposé, non prouvé sans capture USB)

`IOHIDDeviceSetReport(Output)` route bien par l'interrupt-OUT (le device a EP 0x02),
d'où l'affichage de la 1ʳᵉ frame. Mais l'endpoint se met probablement en **STALL**
après ce gros transfert atypique, et il faudrait un `CLEAR_FEATURE(ENDPOINT_HALT)`
sur 0x02 — **impossible via IOHIDManager**. `IOHIDDeviceSetReportWithCallback`
(async) ne sauve pas : **jamais implémenté par Apple**. Le comportement observé
(lock après 1 frame) est solide quelle que soit la cause exacte.

## Conséquence pour le plan initial

**Le port Swift via IOHIDManager est un cul-de-sac pour le streaming** (confiance
haute). « TrofeoKit IOHIDManager intégré à Iris » **ne peut pas** piloter cet écran
en continu sur macOS.

## Chemin retenu : reset-loop (natif Mac)

C'est l'option implémentée (`run.py`). Directe, sur le Mac, sans matériel ni
entitlement. Le seul point de vigilance est le **stress des resets répétés** dans la
durée — à observer en usage réel (et à modérer via une cadence basse, 2-3 fps suffisent
pour de l'horloge/métriques).

### Fallbacks (si le stress des resets s'avérait problématique)

1. **Cadence basse** — réduire à 1-2 fps (resets moins fréquents) ; suffit pour un
   écran de statut quasi-statique. Premier réflexe, zéro coût.
2. **Daemon Linux déporté** (RPi) exécutant le chemin libusb interrupt-OUT natif Linux,
   le Mac poussant les frames en réseau. Robuste mais matériel en plus.
3. **DriverKit dext / VM passthrough** — lourds/incertains, non retenus sauf nécessité.

## Sources

- thermalright-trcc-linux #91 (MacTR / 0416:5408 vendor-class, libusb Swift), #109
  (« macOS seems untested »), #132/#150/#128 (Linux, udev hidraw pour 5302).
- MacTR — github.com/beret21/MacTR (app macOS, vendor-class uniquement).
- libusb-devel #89, libusb #920, pyusb #208 (claim HID macOS → Errno 13 même en root).
- hidapi #385 (`IOHIDDeviceSetReport` hangs macOS) ; Apple Forums (SetReportWithCallback
  jamais implémenté ; USBDriverKit ignoré quand `AppleUserHIDDrivers` matche).
- Reproductibilité : `python/experiments/exp_pyusb.py` (Errno 13 sur claim),
  `python/experiments/exp_hid_drain.py` (lock après 1 frame, ACK-drain inutile).
