#!/bin/bash
set -e
PFOLDER="$3"; LBH="${5:-$LBHOMEDIR}"
[ -n "$LBH" ] || { echo "<FAIL> LBHOMEDIR unbekannt"; exit 2; }
BACKUP="/tmp/${1}_upgrade"
[ -f "$BACKUP/config/config.json" ] || { echo "<FAIL> Konfigurationssicherung fehlt: $BACKUP"; exit 2; }
cp -a "$BACKUP/config/." "$LBH/config/plugins/$PFOLDER/"
echo "<OK> Konfiguration wiederhergestellt"
if [ -f "$BACKUP/streams_cache.json" ]; then
    cp -a "$BACKUP/streams_cache.json" "$LBH/data/plugins/$PFOLDER/"
fi
if [ -f "$BACKUP/was_stopped" ]; then
    touch "$LBH/data/plugins/$PFOLDER/stopped.flag"
    echo "<OK> Plugin bleibt wie vor dem Update gestoppt"
else
    rm -f "$LBH/data/plugins/$PFOLDER/stopped.flag"
    if ! LBHOMEDIR="$LBH" "$LBH/bin/plugins/$PFOLDER/service.sh" start; then
        touch "$LBH/data/plugins/$PFOLDER/stopped.flag"
        echo "<FAIL> Start fehlgeschlagen; Sicherung bleibt in $BACKUP"
        exit 2
    fi
fi
rm -rf "$BACKUP"
exit 0
