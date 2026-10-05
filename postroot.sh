#!/bin/bash
# Runs as root: allow hardware video acceleration (Intel VAAPI / Raspberry V4L2)
for g in video render; do
    getent group "$g" >/dev/null && usermod -a -G "$g" loxberry
done
echo "<OK> Benutzer loxberry für Hardware-Beschleunigung berechtigt"
exit 0
