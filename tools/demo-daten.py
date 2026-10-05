#!/usr/bin/env python3
# Erfundene Demo-Fahrt durch Berlin, um Karte und Auswertungen ohne FRITZ!Box auszuprobieren.
# Schreibt ins Datenverzeichnis der aktiven Konfiguration (MASTBLICK_KONFIG) – nur in ein leeres Testverzeichnis!
#   MASTBLICK_KONFIG=demo/config.toml python3 tools/demo-daten.py
import json, math, os, random, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))
from mastblick import db, konfig

if os.path.exists(db.PFAD):
    sys.exit(f"{db.PFAD} existiert schon – Demo-Daten nur in ein leeres Verzeichnis schreiben.")
os.makedirs(konfig.DATEN, exist_ok=True)
random.seed(7)
PLMN = "26201"
MASTEN = {  # erfundene Masten entlang der Strecke: (eNB, lat, lng)
    1: (25000, 52.5200, 13.3700), 2: (25010, 52.5160, 13.3950), 3: (25020, 52.5125, 13.4200), 4: (25030, 52.5080, 13.4450)}


def zelle(enb, sek, dist, rsrp, primaer):
    eci = enb * 256 + sek
    return {"verbunden": "primary" if primaer else "none", "typ": "lte", "plmn": PLMN, "tac": 0x1A2B, "eci": eci, "enb": enb,
            "sektor": sek, "cellid": f"{enb:05x}-{sek:02x}", "pci": (enb + sek) % 504, "distanz_m": dist, "rsrp": rsrp, "rsrq": -9}


t0 = int(time.time()) - 1800
start, ende = (52.5210, 13.3600), (52.5070, 13.4550)
gps, n = [], 120
for i in range(n):
    t = t0 + i * 10
    f = i / (n - 1)
    lat = start[0] + f * (ende[0] - start[0]) + 0.0004 * math.sin(f * 9)
    lng = start[1] + f * (ende[1] - start[1])
    gps.append((t * 1000, round(lat, 6), round(lng, 6), 5, 12.0, 100, "owntracks"))
    # Abstände zu allen Masten, nächster ist primär
    ab = sorted(((math.hypot((lng - m[2]) * 111320 * math.cos(math.radians(lat)), (lat - m[1]) * 110540), m[0]) for m in MASTEN.values()))
    zellen = [zelle(enb, 21 if j == 0 else 3, round(d / 1.2 / 150) * 150, round(-60 - d / 40 + random.uniform(-4, 4)), j == 0)
              for j, (d, enb) in enumerate(ab)]
    mast = next(m for m in MASTEN.values() if m[0] == ab[0][1])
    geo = {"lat": mast[1] + random.uniform(-.004, .004), "lng": mast[2] + random.uniform(-.006, .006), "genauigkeit_m": 900, "quelle": "BeaconDB"}
    db.abfrage_schreiben(t, "LTE", zellen, rtt=round(random.uniform(40, 90), 1), wg_s=20, boot=t0 - 60,
                         box_b=[i * 150000, i * 20000], wg_b=[i * 9000, i * 7000], geo=geo)
db.gps_schreiben(gps)
with open(konfig.datei("masten.json"), "w") as fh:
    json.dump({f"{PLMN}:{MASTEN[1][0]}": {"lat": MASTEN[1][1], "lng": MASTEN[1][2], "quelle": "Demo", "notiz": "erfunden", "erfasst": "demo"},
               f"{PLMN}:{MASTEN[3][0]}": {"lat": MASTEN[3][1], "lng": MASTEN[3][2], "quelle": "Demo", "notiz": "erfunden", "erfasst": "demo"}}, fh)
letzte = db.messungen(t0 + (n - 2) * 10)[-1]
with open(konfig.datei("status.json"), "w") as fh:
    json.dump({"ok": True, "fehler": None, "abgefragt": letzte["t"], "technik": "LTE", "rsrp_antennen": None,
               "zellen": letzte["zellen"], "geo": {"lat": 52.5085, "lng": 13.4420, "genauigkeit_m": 900, "quelle": "BeaconDB"}}, fh)
print(f"Demo-Fahrt mit {n} Abfragen und {len(gps)} GPS-Punkten in {konfig.DATEN}")
