# Faisabilité macOS — verdict (2026-06-07)

> **Décision en attente.** Ce document fige ce qu'on a établi pour pouvoir trancher
> l'architecture plus tard. Il s'appuie sur des mesures matérielles réelles (Trofeo
> Vision V1.02, macOS Apple Silicon) + recherche du code de référence, des issues
> GitHub et de la doc Apple.

## Verdict

**Il n'existe aucune voie userspace viable sur macOS pour streamer des frames vers
ce device.** Le blocage est **structurel à macOS**, pas un défaut de notre code :
les endpoints data (EP 0x02 OUT) sont sur une **interface de classe HID (0x03)**,
donc **IOHIDFamily se l'approprie en exclusif** dès l'énumération.

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

## Options (par ordre de réalisme)

1. **Daemon Linux déporté** (recommandé) — un petit Linux (ex. Raspberry Pi Zero 2 W)
   branché à l'écran exécute le chemin **prouvé** (libusb interrupt-OUT, trivial sous
   Linux : `detach_kernel_driver` sur `usbhid` + udev hidraw). Le Mac/Iris compose les
   frames (ou envoie juste les métriques) et les pousse en **réseau** (HTTP/WS/TCP).
   Effort **faible**, robuste, zéro entitlement. Inconvénient : matériel en plus,
   l'écran n'est pas piloté directement par le Mac.
2. **DriverKit dext natif** — **semaines** de travail, distribution lourde, succès
   **incertain** face à `AppleUserHIDDrivers`. Seulement si le natif Mac est
   non-négociable.
3. **VM Linux + USB passthrough** sur le Mac — garderait tout sur une machine, mais
   le passthrough USB sur Apple Silicon est **douteux/fragile**. À vérifier avant tout
   engagement.

### Bonus debug (pas une solution de streaming)

Claim l'**interface vendor 1** (classe 0xff, libusb l'accepte sur macOS) et tenter
`reset_device()` pour casser le lock **sans replug** — utile pour expérimenter, mais
re-lock après chaque frame. Non vérifié.

## Sources

- thermalright-trcc-linux #91 (MacTR / 0416:5408 vendor-class, libusb Swift), #109
  (« macOS seems untested »), #132/#150/#128 (Linux, udev hidraw pour 5302).
- MacTR — github.com/beret21/MacTR (app macOS, vendor-class uniquement).
- libusb-devel #89, libusb #920, pyusb #208 (claim HID macOS → Errno 13 même en root).
- hidapi #385 (`IOHIDDeviceSetReport` hangs macOS) ; Apple Forums (SetReportWithCallback
  jamais implémenté ; USBDriverKit ignoré quand `AppleUserHIDDrivers` matche).
- Reproductibilité : `python/experiments/exp_pyusb.py` (Errno 13 sur claim),
  `python/experiments/exp_hid_drain.py` (lock après 1 frame, ACK-drain inutile).
