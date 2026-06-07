# Protocole filaire — Thermalright Trofeo Vision (HID, « Type 2 »)

> **Source de vérité du projet.** Le code Python et le futur port Swift s'écrivent
> *à partir de ce document*. C'est une description **clean-room** : on documente
> les **faits** du protocole (octets, séquences), reconstitués par
> reverse-engineering. On ne copie aucun code GPL — voir la note de licence en bas.

## 1. Matériel cible

| Champ | Valeur |
|---|---|
| Modèle | Thermalright Trofeo Vision, hardware **V1.02** |
| Écran | 6,86″ Full Color LCD, **1280 × 480** |
| USB | **VID 0x0416** (Winbond/Nuvoton) · **PID 0x5302** |
| Classe | **HID** (« Type 2 ») — pas une UART série (≠ écrans Turing) |
| Logiciel d'origine | TRCC (Thermalright LCD Control Center), .NET fermé, Windows |

⚠️ **Le PID 0x5302 est partagé** par plusieurs modèles à résolutions différentes
(Trofeo Vision 1280×480, Frozen Warframe 320×240, Elite Vision…). **La résolution
ne se déduit pas du PID** : elle se confirme au handshake via le *PM byte* (§3).

## 2. Transport

Deux implémentations, **même protocole** :

| | Python (expérimentation) | Swift (port, à venir) |
|---|---|---|
| Couche | hidapi (package `hid`) | **IOHIDManager** direct (IOKit) |
| Dépendance runtime | libhidapi (`brew install hidapi`) | aucune (framework système) |
| macOS | OK (hidapi passe par IOHIDManager) | natif |

Le Trofeo est **HID natif** : sur macOS il se pilote via **IOHIDManager** sans
driver tiers, sans dépendance externe, sans permissions élevées. On ne tente
**pas** de `claim_interface` libusb sur une interface HID (IOKit/IOHIDFamily la
saisit).

**Descripteurs réels (relevés 2026-06-07, pyusb) :**

| Interface | Classe | Endpoints |
|---|---|---|
| iface 0 | 0x03 (HID) | **EP 0x02 OUT interrupt, wMaxPacketSize 512** · EP 0x83 IN interrupt, wMaxPacketSize 8 |
| iface 1 | 0xff (vendor) | aucun endpoint data |

→ Les frames partent sur **EP 0x02 (interrupt OUT, paquets de 512)** — ce qui
**explique l'alignement à 512** du padding (§4). L'endpoint IN est **0x83**
(pas 0x81 comme le suggérait le fallback codé en dur de la réf).

**libusb nu = inutilisable sur macOS (confirmé, pas supposé).** `claim_interface(0)`
→ `Errno 13 Access denied` : IOHIDFamily tient l'interface HID et macOS n'autorise
pas à détacher ce driver en userspace (sudo n'y change rien pour une interface de
classe HID). Le transport libusb interrupt-OUT de la réf fonctionne sous Linux,
**pas** sur macOS pour ce device. → sur macOS, **le stack HID (IOHIDManager) est la
seule voie** ; un accès USB brut (IOUSBHost) se heurterait au même verrou sur
iface 0.

### Report ID (subtilité HID)

En hidapi, le **premier octet de chaque `write` est le Report ID** (`0x00` ici,
report non-numéroté), retiré par la lib avant émission. Donc :

- buffer passé à `hid.write()` = `0x00` + paquet on-wire ;
- le paquet **on-wire** reste `DA DB DC DD …` (ce que décrit ce document) ;
- `read` ne renvoie **pas** de préfixe pour un report non-numéroté : la réponse
  commence directement par le MAGIC.

> **À valider sur matériel :** que ce device veuille bien le préfixe Report ID 0,
> et la **taille max de report** acceptée pour streamer un JPEG entier en un seul
> transfert.

## 3. Handshake / init

**Paquet d'init — 512 octets :**

```
DA DB DC DD | 00 00 00 00 00 00 00 00 | 01 00 00 00 | 00 00 00 00 | 00 … (pad → 512)
^ MAGIC       ^ 8 octets zéro           ^ cmd=1 (LE)  ^ 4 zéro       ^ padding zéro
```

`cmd = 1` = *device info*.

**Séquence :** (réf : 3 tentatives, timeout ~5000 ms)
1. petite pause (~50 ms) ;
2. `write(init)` ;
3. pause (~200 ms) ;
4. `read(512)`.

**Validation de la réponse :** `len ≥ 20` **et** `resp[0:4] == DA DB DC DD` **et**
`resp[12] == 0x01`. Tant que ce n'est pas validé, **on ne pousse aucune frame**.

**Parsing :**

| Octet(s) | Signification |
|---|---|
| `resp[4]` | sub |
| `resp[5]` | **PM byte** → géométrie réelle |
| `resp[12]` | doit valoir `0x01` |
| `resp[16] == 0x10` | marqueur « serial présent » |
| `resp[20:36]` | serial (16 o, si présent) |

**PM byte → résolution (connu) :**

| PM | Résolution | Note |
|---|---|---|
| **128** | 1280 × 480 | **Trofeo Vision V1.02 — confirmé sur matériel (2026-06-07)** |
| 68 | 1280 × 480 | autre chemin théorique (non observé sur ce device) |
| 69 | 1920 × 440 | variante ultrawide |

> **Levé sur matériel :** le Trofeo Vision V1.02 renvoie **PM = 128 (0x80)**,
> `sub = 1`, sur une réponse de **36 octets** (pas 512). Exemple réel ::
>
>     da db dc dd 01 80 00 00 00 00 00 00 01 00 00 00 10 00 00 00
>     42 50 30 4b 38 37 34 0e 00 a1 af 1a 43 02 d7 78
>
> `resp[16]==0x10` → serial présent en `resp[20:36]` (ici préfixe ASCII « BP0K874 »
> puis binaire). ⚠️ Le serial occupe `[20:36]`, donc il faut `len(resp) >= 36`
> (un `> 36` est un off-by-one qui rate le serial sur ce device).

## 4. Frame image

Pour le Trofeo 1280×480 : **JPEG** (qualité ~95), pas de RGB565.

**Header — 20 octets (mode JPEG) :**

```
DA DB DC DD | 02 00 | 00 00 | <W u16 LE> <H u16 LE> | 02 00 00 00 | <len u32 LE>
^ MAGIC       ^ cmd   ^ mode   ^ 1280       ^ 480       ^ const       ^ taille JPEG
              =PICTURE =JPEG
```

- `cmd_type = 0x02` (PICTURE) ; octet 6 = `0x00` (JPEG) ou `0x01` (RGB565).
- En mode **RGB565** (autres devices, pas le Trofeo) les dimensions sont figées à
  `240 × 320` dans le header (héritage firmware).
- Champs entiers en **little-endian**.

**Émission :**
- `frame = header(20) + JPEG`, **paddé à un multiple de 512 octets** (zéro) ;
- envoyée en **un seul transfert** ;
- **pas d'ACK** à lire (contrairement au « Type 3 » des écrans 0418:53xx).

> ⚠️ **Keepalive nécessaire — corrige la réf.** La réf décrit ce type comme
> « non-volatile, pas de keepalive ». Faux sur le Trofeo Vision V1.02 : observé
> en first light (2026-06-07), le device **reprend son UI firmware par défaut
> en ~2 secondes** (mesuré) sans nouvelle frame. Pour maintenir une image custom,
> il faut donc **réémettre la frame plus vite que ~2 s**.
>
> ⚠️ **Une seule frame par handshake (observé 2026-06-07).** Séquence reproduite
> plusieurs fois sur le Trofeo Vision V1.02 :
> `handshake → 1 frame écrite & affichée correctement → la 2ᵉ écriture (même
> handle, ~1 s plus tard) renvoie kIOReturnTimeout (0xE00002D6)` et **fige le
> device** (il reste énuméré mais refuse toute écriture jusqu'au **replug USB**).
> Conséquences :
> - **Ré-émettre naïvement la même frame sur le même handle NE marche pas.** Le
>   « keepalive » suppose un mécanisme inter-frames encore inconnu.
> - Pistes à investiguer **dans le code de la réf** (pas à l'aveugle sur la dalle) :
>   re-handshake avant chaque frame ? lecture d'un report/ACK entre deux écritures
>   pour clore la transaction ? délai inter-frame minimal ? ré-ouverture par frame ?
> - **Récupération d'un état figé : replug USB.** Réveil logiciel : inconnu.

## 5. Orientation & luminosité

- **Rotation** : gérée **côté encodage** (image tournée avant le JPEG). Pas de
  commande device « tourne de 90° ».
- **Luminosité** : **assombrissement logiciel** de l'image avant encodage.
  **Aucun opcode USB** de luminosité sur ce type.

## 6. Récapitulatif actionnable (Trofeo 1280×480)

1. Ouvrir `0416:5302` en HID (hidapi/IOHIDManager).
2. `write` init 512 o → `read` 512 o → valider MAGIC + `resp[12]==0x01` → lire
   `PM = resp[5]`.
3. Encoder l'image en JPEG q~95 → header 20 o (`W=1280,H=480` LE, `len` u32 LE) →
   concaténer → padder à un multiple de 512 → `write` en un coup. Pas d'ACK.
4. Rotation = côté image. Luminosité = assombrissement image.

## 7. Incertitudes (levées sur Trofeo Vision V1.02, 2026-06-07)

- [x] PM byte exact renvoyé → **128 (0x80)**, `sub = 1`, réponse de 36 o.
- [x] Taille max de report pour un JPEG entier en un transfert → **OK** : un JPEG
      de ~37 Ko (header 20 o + 37 257 o, paddé à 37 376 o) est accepté en **un seul
      `write`** (37 377 o avec le Report ID).
- [x] Préfixe Report ID `0x00` → **accepté** par le device.
- [x] Absence d'ACK → **OK** : `write` retourne le compte complet, pas de read requis.
- [x] Rendu visuel → **correct sans rotation ni correction de couleurs** : la mire
      s'affiche dans le bon sens, barres R/V/B dans l'ordre (confirmé à l'œil).
- [x] Persistance → **NON, et 1 frame par handshake** : la 1ʳᵉ frame s'affiche
      **~2 s** (mesuré) puis retour à l'UI par défaut ; la 2ᵉ écriture time out et
      fige le device (replug requis). Voir §4.
- [x] ACK-drain (lire 0x83 entre deux frames) ? **NON** : le read renvoie vide et
      la 2ᵉ écriture time out quand même. Aucun statut à drainer.
- [x] Verrou firmware : après 1 frame, **tout** `SetReport` échoue — y compris un
      nouveau handshake sur open frais — jusqu'au **replug USB**. C'est un verrou
      niveau device, pas un bug logiciel.
- [ ] ⚠️ **BLOQUANT macOS.** Via le stack HID (`IOHIDDeviceSetReport`, le mécanisme
      commun à hidapi **et** à IOHIDManager/Swift), ce device n'accepte qu'**une**
      frame puis se verrouille. Le streaming de la réf passe par **libusb
      interrupt-OUT sur EP 0x02**, voie **bloquée sur macOS** (iface 0 tenue par
      IOHIDFamily, cf. §2). Questions ouvertes : la réf fonctionne-t-elle
      *réellement* sur macOS pour ce device (son `open_bulk` macOS pointe sur le
      même libusb qu'on a vu échouer) ? Existe-t-il une voie macOS — IOUSBHost
      avec entitlement, dext DriverKit, ou séquence de ré-armement inconnue ?

---

### Note de licence / clean-room

Les faits ci-dessus sont reconstitués par reverse-engineering, en s'appuyant
notamment sur le projet **GPL-3.0** [`Lexonight1/thermalright-trcc-linux`](https://github.com/Lexonight1/thermalright-trcc-linux)
(adapter HID `hid_lcd.py`) **pour comprendre le protocole, pas pour copier son
code**. Ce projet-ci réimplémente le protocole *de zéro* à partir de cette
description factuelle, sous licence **MIT**, afin de rester compatible avec son
intégration cible (Iris, MIT). Voir `README.md`.
