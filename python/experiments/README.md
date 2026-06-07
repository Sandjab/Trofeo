# experiments/ — diagnostics matériels (trace reproductible)

Scripts jetables qui ont servi à établir le verdict de faisabilité macOS
(voir [`../../docs/MACOS_FEASIBILITY.md`](../../docs/MACOS_FEASIBILITY.md)).
Pas du code de production — ils touchent le matériel et peuvent figer la dalle
(replug requis).

Prérequis : venv avec `pyusb` + `hid` + `pillow` installés, libs natives brew
(`libusb`, `hidapi`), et la variable de loader :

```bash
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib
```

| Script | Ce qu'il montre |
|---|---|
| `exp_pyusb.py` | Dump des descripteurs (EP 0x02 OUT interrupt/512, EP 0x83 IN interrupt/8 ; iface 0 = HID). `claim_interface(0)` → **Errno 13** : libusb ne peut pas prendre l'interface HID sur macOS. |
| `exp_hid_drain.py` | En hidapi : handshake + 1 frame OK, puis 2ᵉ write → **timeout** ; drainer l'EP 0x83 ne change rien (pas d'ACK). Lock après 1 frame. |
| `exp_resetloop.py` | **La solution** : `reset_device()` (libusb, sans claim) réveille le device → boucle `reset → handshake → frame` à **~5 fps stable**. Fondement de `trofeo/transport.py`. |

> `exp_resetloop.py` s'appuie sur le package `trofeo` installé (venv) ; les deux autres
> ont un `sys.path` relatif. Tous se lancent avec `.venv/bin/python` et le `DYLD` ci-dessus.
