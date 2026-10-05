# UniFi Protect Cameras for Loxone (LoxBerry plugin)

🇩🇪 [Deutsche Version](README.de.md)

Brings UniFi Protect cameras (G3/G4/G5/G6, doorbells incl. package camera) into the Loxone app –
as an **MJPEG video stream** and **JPEG snapshot**, the two formats a Loxone custom intercom understands.

**Languages:** English, Deutsch, Français, Italiano, Español, Nederlands, Svenska, Norsk.
The plugin follows the language set in LoxBerry; other languages fall back to English.

## How it works

```
UniFi NVR ──RTSPS (H.264/H.265, 1 connection per camera)──► go2rtc on the LoxBerry
                                                            ├─ ffmpeg → MJPEG (encoded once, shared by all apps)
                                                            └─ snapshot: Protect API (camera JPEG, ~0.3 s) / fallback from stream
Loxone app / Miniserver ◄──── http://LOXBERRY:1984/api/stream.mjpeg?src=<camera>_mjpeg
                        ◄──── http://LOXBERRY/plugins/unifi2lox/snapshot.php?cam=<camera>
```

- One NVR connection and one encoder per camera, no matter how many apps are watching.
- First frame after ~0.6–1.6 s; with “instant start” ~0.2 s (constant CPU load).
- Full-resolution snapshots straight from the camera, cached in RAM for simultaneous requests.

## Installation

1. Upload the ZIP in LoxBerry under *Plugin management → Install plugin* (LoxBerry ≥ 3.0, built for 4.0).
   ffmpeg and go2rtc are installed automatically.
2. Create an API key in UniFi OS: *Protect → Settings → button “Integrations” (below the settings) → Create API key*.
3. Open the plugin page → host + API key → **Find cameras** → apply → **Save & apply**.
   (Without API key: “Add camera manually” with the RTSP URL from Protect.)

## Loxone Config

Periphery → Intercom → **Custom Intercom**:

| Field | Value |
|---|---|
| Video stream URL | `http://<LoxBerry-IP>:1984/api/stream.mjpeg?src=<camera>_mjpeg` |
| Image URL | `http://<LoxBerry-IP>/plugins/unifi2lox/snapshot.php?cam=<camera>` |
| User / password | from the plugin, section “Server” |

## Recommendations

| Hardware | Settings |
|---|---|
| Raspberry Pi 4/5 | Source *Medium*, 1280 px, 10 fps, software encoding. 2–4 simultaneous streams. |
| Intel NUC / x86 | Source *High* possible, hardware acceleration *VAAPI*. |
| Raspberry Pi 3 | Source *Low* or *Medium* at 640 px, 5–8 fps. |

For remote access via the Loxone app the stream must be reachable from outside (VPN recommended).

## Translations

All texts are in `templates/lang/language_<code>.ini`. To add a language, copy `language_en.ini`,
translate the values and name it with the ISO code (e.g. `language_pl.ini`). Pull requests welcome.
