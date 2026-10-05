#!/bin/bash
PFOLDER="$3"; LBH="${5:-/opt/loxberry}"
BACKUP="/tmp/${1}_upgrade"
if [ -d "$BACKUP/config" ]; then
    cp -a "$BACKUP/config/." "$LBH/config/plugins/$PFOLDER/"
    echo "<OK> Konfiguration wiederhergestellt"
fi
[ -f "$BACKUP/streams_cache.json" ] && cp -a "$BACKUP/streams_cache.json" "$LBH/data/plugins/$PFOLDER/"
rm -rf "$BACKUP"
LBHOMEDIR="$LBH" "$LBH/bin/plugins/$PFOLDER/service.sh" start
exit 0
