# mastblick

Wo ist die FRITZ!Box gerade? **mastblick** verortet eine FRITZ!Box mit LTE (z. B. 6820 LTE) grob über die Mobilfunkzelle, in die sie eingebucht ist, und zeigt das auf einer Karte – samt Sendemast, Fahrtverlauf, Netzabdeckung und Auswertungen. Gedacht für eine Box, die mobil unterwegs ist (Auto, Wohnmobil, Baustelle) und z. B. per WireGuard-Tunnel an einem Server hängt.

Mit der Zeit wird die Ortung von selbst besser: Läuft beim Fahren das Handy mit (OwnTracks oder Browser), lernt mastblick aus Handy-GPS und Zellmessungen eine eigene Zelldatenbank.

## Was es kann

- **Ortung über die Zelle**: fragt die Box per TR-064 (`X_AVM-DE_WANMobileConnection#GetInfoEx`) nach allen sichtbaren Zellen mit Signalstärke und Abstand (Timing Advance)
  - Reihenfolge der Quellen: Ring um einen bekannten Mast (gemeldeter Abstand, Richtung eigener Zelldaten) → Fingerabdruck (Signalstärken der primären und Nachbarzellen gegen frühere Messungen) → eigene Zelldatenbank → eigene Mastdatenbank → BeaconDB / OpenCelliD → andere Sektoren derselben Station
  - Alle Verfahren werden bei jeder Abfrage mitgerechnet und gespeichert; die Karte zeigt sie zum Vergleich mit dem Handy-GPS
  - Plausibilitätsfilter gegen Ausreißer und Glättung bei Ping-Pong zwischen zwei Zellen
- **Karte** (Leaflet, OpenStreetMap)
  - Box mit Genauigkeitskreis, bekannte Masten, laufende Linie zum gerade verbundenen Mast
  - Track je Fahrt oder Zeitabschnitt, Handy-GPS je Quelle farbig, Live-Position per Push (Server-Sent Events)
- **Masten**: eigene Mastdatenbank je eNB oder Sektor
  - Anlernen aus Abstandsringen (Ausgleichsrechnung)
  - Vorschläge für unbekannte Masten und Nachschärfen bekannter Masten – übernommen wird nur per Klick
- **Handy-Tracking** über die OwnTracks-App
  - wird bewusst auf der Seite ein- und ausgeschaltet
  - der Server stellt die App dabei per Fernkonfiguration auf „Move“ bzw. „Significant“
  - schaltet sich nach 12 h selbst ab
- **Auswertungen**
  - Ortungsgüte je Fahrt: angezeigt, eigene Zelldaten, Fingerabdruck, freie Daten
  - Netzabdeckung (RSRP-Raster), Funklöcher und Ping-Laufzeit
  - Versorgungsgebiete je Zelle, Zellwechsel und Ping-Pong
  - Datenmenge je Fahrt
- **Fahrten**: Eine Einschaltung der Box ist eine Fahrt (Uptime per TR-064).
- **Optional melden**: Messpaare an [BeaconDB](https://beacondb.net) und [OpenCelliD](https://opencellid.org), standardmäßig **aus**.

## Wie gut ist das?

Bei uns, nach fünf Fahrten in Norddeutschland. Gemessen wurde der mittlere Abstand der gezeigten Position zum Handy-GPS:

| Quelle | Median | 90 % unter |
|---|---|---|
| nur BeaconDB | 6,7 km | 18,9 km |
| nur OpenCelliD | 7,9 km | 40 km |
| eigene Zelldatenbank | 0,3 km | 1,0 km |

Der Abstand, den die Box zum Mast meldet, war bei uns etwa 1,2-mal zu kurz; das ist im Code als Faktor hinterlegt.

## Aufbau

```
bin/mastblick-abfrage   Dienst: fragt die Box ab (60 s, beim Tracking 10 s), verortet, schreibt status.json + Datenbank
bin/mastblick-api       Dienst: HTTP-API und Push für die Karte, OwnTracks-Empfang, Auswertungen
bin/mastblick-melden    Timer (15 min): Zelldatenbank lernen, Gütewerte, optional melden, alte Daten löschen
lib/mastblick/          Konfiguration (TOML) und SQLite-Datenbank
web/index.html          Kartenseite (eine Datei, lädt nur Leaflet von cdnjs)
systemd/, nginx/        Beispiel-Units und Webserver-Konfiguration
tools/demo-daten.py     erfundene Demo-Fahrt zum Ausprobieren ohne Box
```

Daten liegen in `/var/lib/mastblick`:

- `mastblick.db` (SQLite: Abfragen, Zellen, GPS)
- `masten.json`, `zellen.json`, `status.json` und einige kleine Zustandsdateien

## Voraussetzungen

- Linux-Server mit systemd und Python 3.11 oder neuer (nur Standardbibliothek), dazu `curl`; für Tunnelwerte `wireguard-tools`
- FRITZ!Box mit LTE, vom Server aus erreichbar
- Auf der Box: TR-064 aktiv („Heimnetz → Netzwerk → Netzwerkeinstellungen → Zugriff für Anwendungen zulassen“) und ein eigener Benutzer für mastblick
  - Welche Rechte dieser Benutzer mindestens braucht, ist noch nicht ausgetestet.

## Installation

```sh
git clone https://github.com/wattnpapa/mastblick.git
cd mastblick
sudo ./install.sh
```

Danach:

1. `/etc/mastblick/config.toml` anpassen (Box-Adresse, ggf. `[tunnel]`).
2. Zugangsdaten der Box hinterlegen – die Datei legst du selbst an, das Kennwort taucht sonst nirgends auf:
   ```sh
   sudo install -o root -g mastblick -m 640 /dev/null /etc/mastblick/fritzbox.netrc
   sudoedit /etc/mastblick/fritzbox.netrc     # machine 192.168.178.1 login <benutzer> password <kennwort>
   ```
3. Webserver einrichten (`nginx/mastblick.conf.example`). Im Heimnetz geht es auch ohne: in der Konfiguration `[api] web_verzeichnis = "/opt/mastblick/web"` und `adresse = "0.0.0.0"` setzen.
4. `sudo systemctl restart mastblick-abfrage mastblick-api`

Den Standort des Handys gibt der Browser nur über **HTTPS** heraus. Für das Mitschreiben im Browser braucht die Seite also ein Zertifikat.

## Handy-Tracking mit OwnTracks

1. Zugang anlegen. Gespeichert wird nur der SHA-256 des Kennworts:
   ```sh
   read -rsp "Kennwort: " pw; echo
   printf '%s:%s\n' "<benutzer>" "$(printf %s "$pw" | sha256sum | cut -d' ' -f1)" | sudo tee /etc/mastblick/owntracks.auth >/dev/null
   unset pw
   sudo chown root:mastblick /etc/mastblick/owntracks.auth; sudo chmod 640 /etc/mastblick/owntracks.auth
   ```
2. In der App einstellen:
   - Modus HTTP
   - URL `https://<deine-seite>/api/owntracks`
   - Benutzer und Kennwort von eben
   - „cmd“ und „remoteConfiguration“ einschalten, damit der Server den Modus umstellen darf
3. Auf der Karte „Handy-Tracking → einschalten“, nur wenn das Handy bei der Box ist. Ist es aus, verwirft der Server alle Positionen.

## Melden an BeaconDB / OpenCelliD

Standardmäßig aus. Wer einschaltet (`[melden] beacondb = true` bzw. `opencellid = true`), schickt seine gefahrenen Positionen samt Zellmessungen an diese offenen Datenbanken. Das hilft allen anderen, ist aber öffentlich.

- Für OpenCelliD braucht es einen API-Schlüssel in `/etc/mastblick/opencellid.key`.
- Gemeldet wird nur, was wirklich gemessen wurde: Handy-GPS höchstens 20 s auseinander und ≤ 50 m genau.
- Stillstand wird nicht doppelt gemeldet.

**CellMapper** wird nur als Link zum Nachsehen angeboten; automatische Abfragen verbieten dessen Nutzungsbedingungen.

## Ausprobieren ohne Box

```sh
mkdir -p demo && printf '[daten]\nverzeichnis = "%s/demo"\n[api]\nport = 8099\nweb_verzeichnis = "%s/web"\n' "$PWD" "$PWD" > demo/config.toml
MASTBLICK_KONFIG=demo/config.toml python3 tools/demo-daten.py
MASTBLICK_KONFIG=demo/config.toml python3 bin/mastblick-api
# → http://127.0.0.1:8099
```

## Tests

```sh
python3 -m unittest discover -s tests
```

## Datenschutz

- mastblick speichert Standorte der Box und – wenn eingeschaltet – des Handys, 90 Tage lang (einstellbar).
- Die Karte gehört hinter eine Anmeldung.
- Wer die Seite öffnen darf, sieht die Live-Position.

## Lizenz

[EUPL-1.2](LICENSE)

---

*English summary:* mastblick locates an AVM FRITZ!Box with LTE via its serving cell (TR-064), shows it on a Leaflet map with masts, tracks and coverage, and learns its own cell database from phone GPS (OwnTracks). Reporting to BeaconDB/OpenCelliD is opt-in. Code and UI are in German. Licensed under EUPL-1.2.
