#!/bin/sh
# mastblick installieren bzw. aktualisieren (Debian/Ubuntu mit systemd, als root ausführen).
# Legt den Systembenutzer mastblick an, kopiert nach /opt/mastblick, richtet /etc/mastblick und /var/lib/mastblick ein
# und installiert die systemd-Dienste. Vorhandene Konfiguration und Daten bleiben unangetastet.
set -eu
[ "$(id -u)" = 0 ] || { echo "bitte als root ausführen" >&2; exit 1; }
cd "$(dirname "$0")"
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || { echo "Python 3.11 oder neuer nötig" >&2; exit 1; }
command -v curl >/dev/null || { echo "curl fehlt (apt install curl)" >&2; exit 1; }

id mastblick >/dev/null 2>&1 || useradd --system --home-dir /var/lib/mastblick --shell /usr/sbin/nologin mastblick
install -d -m 755 /opt/mastblick
cp -r bin lib web /opt/mastblick/
chmod 755 /opt/mastblick/bin/*
install -d -o root -g mastblick -m 750 /etc/mastblick
[ -e /etc/mastblick/config.toml ] || install -o root -g mastblick -m 640 config.example.toml /etc/mastblick/config.toml
install -d -o mastblick -g mastblick -m 750 /var/lib/mastblick
install -m 644 systemd/*.service systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now mastblick-api.service mastblick-abfrage.service mastblick-melden.timer

cat <<'T'
mastblick ist installiert. Noch zu tun:
  1. /etc/mastblick/config.toml anpassen (Box-Adresse, ggf. Tunnel)
  2. Zugangsdaten der FRITZ!Box in /etc/mastblick/fritzbox.netrc (root:mastblick, 640), siehe README
  3. Webserver einrichten (nginx/mastblick.conf.example) oder [api] web_verzeichnis = "/opt/mastblick/web"
  4. systemctl restart mastblick-abfrage mastblick-api
T
