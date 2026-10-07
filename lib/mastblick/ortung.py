# Fingerabdruck-Ortung: frühere Abfragen mit Handy-GPS bilden eine Karte „welche Zellen mit welcher Signalstärke wo“.
# Eine neue Abfrage bekommt den Ort ihrer ähnlichsten früheren Messungen. Verglichen werden alle Zellen, die die Box
# meldet (primäre und Nachbarzellen) über ihre RSRP-Werte; eine fehlende Zelle zählt als sehr schwach (FEHLT dBm).
# Kandidaten: nur frühere Messungen mit derselben primären Zelle. Auswertung aller Fahrten bis 07.10. (ohne Blick
# auf die letzten 10 min): so Median 327 m (angezeigt 385 m). Nur über gemeinsame Nachbarzellen (primäre Zelle neu)
# lag jede probierte Variante 3,4–5,7 km daneben (angezeigt 1,1 km): veraltete Nachbarzellen der Box und Zellen,
# die im Flachland kilometerweit zu hören sind. Deshalb ohne diesen Rückfall.
import bisect, math, time
from mastblick import db

K = 3                 # so viele ähnlichste Messungen mitteln
FEHLT = -125          # dBm für eine Zelle, die nur in einem der beiden Fingerabdrücke vorkommt
NEU_S = 600           # Index höchstens so alt, dann neu aus der Datenbank
GPS_LUECKE_S = 20     # GPS zum Abfragezeitpunkt nur zwischen Punkten, die höchstens so weit auseinander liegen
GPS_GENAU_M = 50
MIN_ACC_M = 150

_IDX = {"t": 0, "paare": [], "prim": {}}


def schluessel(c):
    return f'{c.get("plmn")}:{c.get("eci")}'


def abdruck(zellen):
    return {schluessel(c): c["rsrp"] for c in zellen if c.get("eci") and c.get("rsrp") is not None}


def abstand(a, b):
    """Mittlere RSRP-Differenz (dB) zweier Fingerabdrücke {zelle: RSRP}."""
    ks = set(a) | set(b)
    return math.sqrt(sum((a.get(k, FEHLT) - b.get(k, FEHLT)) ** 2 for k in ks) / len(ks)) if ks else 99


def gps_punkte():
    return [(t / 1000, la, ln, 999 if acc is None else acc) for t, la, ln, acc, sp, hd, q in db.gps()]


def gps_bei(pts, t):
    """Handy-Position zum Zeitpunkt t, linear zwischen Nachbarpunkten (≤ GPS_LUECKE_S, ≤ GPS_GENAU_M), sonst None."""
    i = bisect.bisect_right(pts, (t, 1e9))
    if i == 0 or i >= len(pts):
        return None
    a, b = pts[i - 1], pts[i]
    if b[0] - a[0] > GPS_LUECKE_S or max(a[3], b[3]) > GPS_GENAU_M:
        return None
    f = 0 if b[0] == a[0] else (t - a[0]) / (b[0] - a[0])
    return a[1] + f * (b[1] - a[1]), a[2] + f * (b[2] - a[2])


def index():
    """Messpaare (lat, lng, Fingerabdruck, t) aus Datenbank und Handy-GPS, höchstens NEU_S alt."""
    if time.time() - _IDX["t"] < NEU_S:
        return _IDX
    pts = gps_punkte()
    paare, prim = [], {}
    for m in db.messungen():
        z = m.get("zellen")
        p = gps_bei(pts, m["t"]) if z else None
        fp = abdruck(z) if p else None
        if not fp:
            continue
        i = len(paare)
        paare.append((p[0], p[1], fp, m["t"]))
        prim.setdefault(schluessel(z[0]), []).append(i)
    _IDX.update(t=time.time(), paare=paare, prim=prim)
    return _IDX


def fingerabdruck(zellen, idx=None, vor=None):
    """Ort aus den K ähnlichsten früheren Messungen, gewichtet nach Ähnlichkeit; None ohne passende Messungen.
    vor: nur Messungen bis 10 min vor diesem Zeitpunkt (Nachrechnen, ohne die eigene Fahrtminute zu benutzen)."""
    idx = idx or index()
    fp = abdruck(zellen)
    if not fp or not zellen:
        return None
    alt = (lambda i: idx["paare"][i][3] < vor - 600) if vor else (lambda i: True)
    kand = [i for i in idx["prim"].get(schluessel(zellen[0]), []) if alt(i)]
    if len(kand) < K:
        return None
    nb = sorted((abstand(fp, idx["paare"][i][2]), i) for i in kand)[:K]
    w = [1 / (1 + d) for d, _ in nb]
    lat = sum(idx["paare"][i][0] * x for (_, i), x in zip(nb, w)) / sum(w)
    lng = sum(idx["paare"][i][1] * x for (_, i), x in zip(nb, w)) / sum(w)
    k = math.cos(math.radians(lat))
    streu = max(math.hypot((idx["paare"][i][0] - lat) * 110540, (idx["paare"][i][1] - lng) * 111320 * k) for _, i in nb)
    return {"lat": round(lat, 6), "lng": round(lng, 6), "genauigkeit_m": max(MIN_ACC_M, round(streu + 20 * nb[0][0])),
            "quelle": "Fingerabdruck", "anzahl": len(kand), "db": round(nb[0][0], 1)}
