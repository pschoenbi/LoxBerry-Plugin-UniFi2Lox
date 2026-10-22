#!/bin/bash
# Save user configuration before LoxBerry replaces the plugin folders
set -e
umask 077
PFOLDER="$3"; LBH="${5:-$LBHOMEDIR}"
[ -n "$LBH" ] || { echo "<FAIL> LBHOMEDIR unbekannt"; exit 2; }
if [ -f "$LBH/bin/plugins/$PFOLDER/https_manager.py" ]; then
    LBHOMEDIR="$LBH" python3 "$LBH/bin/plugins/$PFOLDER/https_manager.py" upgrade-check || exit 2
    # Keep certificate writers out of the configuration backup until stopped.flag is set.
    exec 9>"$LBH/config/plugins/$PFOLDER/https/operation.lock"
    python3 -c 'import fcntl; fcntl.flock(9, fcntl.LOCK_EX | fcntl.LOCK_NB)' || { echo "<FAIL> HTTPS operation is running"; exit 2; }
fi
BACKUP="/tmp/${1}_upgrade"
mkdir -p "$BACKUP"
cp -a "$LBH/config/plugins/$PFOLDER/." "$BACKUP/config/"
python3 - "$BACKUP/config/config.json" <<'PY'
import json, sys
with open(sys.argv[1]) as f:
    config = json.load(f)
assert isinstance(config.get("server"), dict), "Invalid saved configuration"
PY
if [ -f "$LBH/data/plugins/$PFOLDER/streams_cache.json" ]; then
    cp -a "$LBH/data/plugins/$PFOLDER/streams_cache.json" "$BACKUP/"
fi
# keep the go2rtc binary, saves the download
if [ -f "$LBH/bin/plugins/$PFOLDER/go2rtc" ]; then
    cp -a "$LBH/bin/plugins/$PFOLDER/go2rtc" "$BACKUP/"
fi
mkdir -p "$LBH/data/plugins/$PFOLDER"
if [ -f "$LBH/data/plugins/$PFOLDER/stopped.flag" ]; then
    touch "$BACKUP/was_stopped"
fi
touch "$LBH/data/plugins/$PFOLDER/stopped.flag"
"$LBH/bin/plugins/$PFOLDER/service.sh" stop >/dev/null 2>&1
echo "<OK> Konfiguration gesichert"
exit 0
