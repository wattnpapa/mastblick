# Konfiguration aus /etc/mastblick/config.toml (anderer Pfad über MASTBLICK_KONFIG).
# Fehlende Werte kommen aus STANDARD; eine fehlende Datei ergibt die reine Standardkonfiguration.
import copy, os, tomllib

PFAD = os.environ.get("MASTBLICK_KONFIG", "/etc/mastblick/config.toml")

STANDARD = {
    "box": {
        "adresse": "192.168.178.1",        # FRITZ!Box, vom Server aus erreichbar (LAN oder Tunnel)
        "tr064_port": 49000,
        "netrc": "/etc/mastblick/fritzbox.netrc",   # "machine <adresse> login <benutzer> password <kennwort>"
    },
    "tunnel": {
        "wg_schnittstelle": "",            # z. B. "wg0"; leer = kein Tunnel-Zähler/Handshake
        "wg_peer": "",                     # AllowedIP des Box-Peers, z. B. "10.0.0.4/32"
    },
    "daten": {
        "verzeichnis": "/var/lib/mastblick",
        "aufbewahren_tage": 90,
    },
    "api": {
        "adresse": "127.0.0.1",
        "port": 8091,
        "owntracks_auth": "/etc/mastblick/owntracks.auth",   # "<benutzer>:<sha256-hex des Kennworts>"
        # Kartenseite direkt ausliefern (praktisch ohne Webserver davor); leer = nur API
        "web_verzeichnis": "",
        # weitere JSON-Dateien, die per Push an die Seite gehen: {ereignis = "/pfad/datei.json"}
        "push_dateien": {},
        # Dateien, deren Änderung nur als Signal (ohne Inhalt) gemeldet wird – für große Dateien: {ereignis = [pfade]}
        "push_signale": {},
    },
    "melden": {
        # Messpaare (Handy-GPS + Zellen) an freie Datenbanken melden – nur mit ausdrücklichem Einverständnis einschalten
        "beacondb": False,
        "opencellid": False,
        "opencellid_schluessel": "/etc/mastblick/opencellid.key",
        "user_agent": "mastblick/0.1 (+https://github.com/wattnpapa/mastblick)",
    },
}


def _mischen(basis, neu):
    for k, v in neu.items():
        if isinstance(v, dict) and isinstance(basis.get(k), dict):
            _mischen(basis[k], v)
        else:
            basis[k] = v
    return basis


def laden(pfad=PFAD):
    k = copy.deepcopy(STANDARD)
    if os.path.exists(pfad):
        with open(pfad, "rb") as f:
            _mischen(k, tomllib.load(f))
    return k


K = laden()
DATEN = K["daten"]["verzeichnis"]


def datei(name):
    """Pfad einer Datei im Datenverzeichnis."""
    return os.path.join(DATEN, name)


def box_url(pfad):
    return f'http://{K["box"]["adresse"]}:{K["box"]["tr064_port"]}{pfad}'
