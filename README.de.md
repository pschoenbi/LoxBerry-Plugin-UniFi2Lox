# UniFi Protect Kameras für Loxone (LoxBerry-Plugin)

🇬🇧 [English version](README.md)

Bringt UniFi-Protect-Kameras (G3/G4/G5/G6, Doorbells inkl. Paketkamera) in die Loxone App –
als **MJPEG-Videostream** und **JPEG-Standbild**, den beiden Formaten, die eine
benutzerdefinierte Loxone-Intercom versteht.

## Wie es funktioniert

```
UniFi NVR ──RTSPS (H.264/H.265, 1 Verbindung pro Kamera)──► go2rtc auf dem LoxBerry
                                                            ├─ ffmpeg → MJPEG (einmal kodiert, für alle Apps geteilt)
                                                            └─ Standbild: Protect-API (Kamera-JPEG, ~0,3 s) / Fallback aus dem Stream
Loxone App / Miniserver ◄──── http://LOXBERRY:1984/api/stream.mjpeg?src=<kamera>_mjpeg
                        ◄──── http://LOXBERRY/plugins/unifi2lox/snapshot.php?cam=<kamera>
```

**Qualität:** Quelle wählbar (Hoch/Mittel/Niedrig/Paket), Ausgabebreite, FPS und JPEG-Qualität
pro Kamera einstellbar, volle JPEG-Farbskala (yuvj420p). Standbilder kommen in voller Auflösung
direkt von der Kamera statt aus dem Videostream.

**Geschwindigkeit:**
- Eine einzige NVR-Verbindung und ein einziger Encoder pro Kamera, egal wie viele Apps zuschauen.
- „NVR-Verbindung halten“ (Standard) spart den RTSPS-Verbindungsaufbau.
- Kürzere Stream-Analyse von ffmpeg: erstes Bild nach ~0,6–1,6 s statt ~2,6 s (gemessen, 2-s-Keyframe).
- „Sofortstart“ hält den Encoder dauerhaft warm → erstes Bild in ~0,2 s (kostet dauerhaft CPU).
- Standbild-Cache im RAM: gleichzeitig klingelnde Apps lösen nur einen Abruf aus.

## Installation

1. ZIP in LoxBerry unter *Plugin-Verwaltung → Plugin installieren* hochladen (LoxBerry ≥ 3.0, getestet für 4.0).
   ffmpeg und go2rtc werden automatisch installiert.
2. In UniFi OS einen API-Key erstellen: *Protect → Einstellungen → Button „Integrations“ (unterhalb der Einstellungen) → API-Key erstellen*.
3. Plugin-Seite öffnen → Host + API-Key → **Kameras suchen** → übernehmen → **Speichern & anwenden**.
   (Ohne API-Key: „Kamera manuell“ und die RTSP-URL aus Protect eintragen.)

## Loxone Config

Peripherie → Intercom → **Benutzerdefinierte Intercom**:

| Feld | Wert |
|---|---|
| Video-Stream URL | `http://<LoxBerry-IP>:1984/api/stream.mjpeg?src=<kamera>_mjpeg` |
| Bild-URL | `http://<LoxBerry-IP>/plugins/unifi2lox/snapshot.php?cam=<kamera>` |
| Benutzer / Passwort | aus dem Plugin, Abschnitt „Server“ |

Die URLs zeigt die Plugin-Seite pro Kamera mit Kopier-Knopf an.

## Empfehlungen

| Hardware | Einstellung |
|---|---|
| Raspberry Pi 4/5 | Quelle *Mittel*, 1280 px, 10 fps, Software-Kodierung. 2–4 gleichzeitige Streams problemlos. |
| Intel NUC / x86 | Quelle *Hoch* möglich, Hardware-Beschleunigung *VAAPI*. |
| Raspberry Pi 3 | Quelle *Niedrig* oder *Mittel* mit 640 px, 5–8 fps. |

Für den Fernzugriff über die Loxone App muss der Stream extern erreichbar sein (VPN empfohlen,
alternativ Port-Weiterleitung auf 1984 – das Passwort schützt den Stream).

## Dateien

- `bin/unifi2lox.py` – Protect-API, Kamerasuche, erzeugt `go2rtc.yaml`
- `bin/service.sh` – Start/Stopp/Watchdog von go2rtc
- `bin/common.php` – Standbild-Logik inkl. Cache
- `webfrontend/htmlauth/` – Einstellungsseite, `webfrontend/html/snapshot.php` – Bild-Endpoint
