#!/bin/bash
# Runs as user loxberry.  $1 tmpdir  $2 name  $3 folder  $4 version  $5 LBHOMEDIR
PFOLDER="$3"; LBH="${5:-/opt/loxberry}"
BIN="$LBH/bin/plugins/$PFOLDER"
CFGDIR="$LBH/config/plugins/$PFOLDER"
DATA="$LBH/data/plugins/$PFOLDER"
GO2RTC_VERSION="v1.9.14"
BACKUP="/tmp/${1}_upgrade"

mkdir -p "$DATA" "$LBH/log/plugins/$PFOLDER"
chmod +x "$BIN/service.sh" "$BIN/unifi2lox.py"

# ---- go2rtc binary --------------------------------------------------------
case "$(dpkg --print-architecture 2>/dev/null || uname -m)" in
    amd64|x86_64)  ASSET=go2rtc_linux_amd64 ;;
    arm64|aarch64) ASSET=go2rtc_linux_arm64 ;;
    armhf|armv7l)  ASSET=go2rtc_linux_arm ;;
    armel|armv6l)  ASSET=go2rtc_linux_armv6 ;;
    i386|i686)     ASSET=go2rtc_linux_i386 ;;
    *) echo "<FAIL> Unbekannte Architektur"; exit 2 ;;
esac

if [ -x "$BACKUP/go2rtc" ]; then
    cp -a "$BACKUP/go2rtc" "$BIN/go2rtc"
    echo "<OK> go2rtc aus vorheriger Version übernommen"
fi
# always try to fetch the pinned version, fall back to latest
for URL in "https://github.com/AlexxIT/go2rtc/releases/download/$GO2RTC_VERSION/$ASSET" \
           "https://github.com/AlexxIT/go2rtc/releases/latest/download/$ASSET"; do
    echo "<INFO> Lade $URL"
    if curl -fsSL --retry 3 -o "$BIN/go2rtc.new" "$URL"; then
        chmod +x "$BIN/go2rtc.new"
        if "$BIN/go2rtc.new" -version >/dev/null 2>&1; then
            mv -f "$BIN/go2rtc.new" "$BIN/go2rtc"
            echo "<OK> go2rtc installiert: $("$BIN/go2rtc" -version 2>&1 | head -1)"
            break
        fi
    fi
    rm -f "$BIN/go2rtc.new"
done
if [ ! -x "$BIN/go2rtc" ]; then
    echo "<FAIL> go2rtc konnte nicht heruntergeladen werden"
    exit 2
fi

# ---- configuration --------------------------------------------------------
if [ ! -f "$CFGDIR/config.json" ]; then
    cp "$CFGDIR/config.default.json" "$CFGDIR/config.json"
    echo "<OK> Standardkonfiguration angelegt"
fi
# fill in secrets once
python3 - "$CFGDIR/config.json" <<'PY'
import json, secrets, sys
p = sys.argv[1]
c = json.load(open(p))
s = c.setdefault("server", {})
if not s.get("password"):
    s["password"] = secrets.token_urlsafe(12)
if not s.get("snapshot_key"):
    s["snapshot_key"] = secrets.token_hex(12)
json.dump(c, open(p, "w"), indent=2)
PY
chmod 600 "$CFGDIR/config.json"

command -v ffmpeg >/dev/null || echo "<WARNING> ffmpeg nicht gefunden - MJPEG-Umwandlung funktioniert nicht"
exit 0
