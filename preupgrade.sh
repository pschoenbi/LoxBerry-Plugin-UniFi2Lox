#!/bin/bash
# Save user configuration before LoxBerry replaces the plugin folders
PFOLDER="$3"; LBH="${5:-/opt/loxberry}"
BACKUP="/tmp/${1}_upgrade"
mkdir -p "$BACKUP"
cp -a "$LBH/config/plugins/$PFOLDER/." "$BACKUP/config/" 2>/dev/null
cp -a "$LBH/data/plugins/$PFOLDER/streams_cache.json" "$BACKUP/" 2>/dev/null
# keep the go2rtc binary, saves the download
cp -a "$LBH/bin/plugins/$PFOLDER/go2rtc" "$BACKUP/" 2>/dev/null
"$LBH/bin/plugins/$PFOLDER/service.sh" stop >/dev/null 2>&1
echo "<OK> Konfiguration gesichert"
exit 0
