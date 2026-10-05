# Neue Version veröffentlichen

1. Änderungen auf `main`, `VERSION` in `plugin.cfg` erhöhen, `CHANGELOG.md` ergänzen.
2. Release-Branch anlegen: `release-<version>` (z.B. `release-1.2.0`) vom Stand von `main`.
   Testversion: `release-1.2.0-beta1`.
3. Die GitHub-Action trägt die Version automatisch in `release.cfg` (bzw. `prerelease.cfg`) ein.
   Danach finden alle LoxBerrys das Update.

Alternativ funktioniert auch ein Tag `v1.2.0` oder ein GitHub-Release.
Release-Branches nach der Veröffentlichung nicht mehr verändern.
