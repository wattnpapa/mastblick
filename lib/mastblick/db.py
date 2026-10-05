# Gemeinsame SQLite-Datenbank der mastblick-Dienste (mastblick-abfrage, mastblick-api, mastblick-melden).
#   abfrage  eine Zeile je TR-064-Abfrage: Erfolg/Fehler, Ping, Tunnel, Einschaltzeit, Datenzähler, angezeigter Ort
#   zelle    alle Zellen je Abfrage (nr 0 = primäre Zelle, wie von der Box sortiert)
#   gps      Handy-Positionen (Browser, OwnTracks)
# Alle Dienste laufen als Benutzer mastblick; WAL erlaubt Lesen, während geschrieben wird.
# Lesefunktionen liefern einfache Formen: Messung als dict {t, technik, zellen, …}, Verlauf als Spaltenliste
# (zeit, plmn, tac, eci, cellid, pci, rsrp, rsrq, distanz_m, lat, lng, genauigkeit_m) als Text.
import sqlite3, time
from mastblick import konfig

PFAD = konfig.datei("mastblick.db")
KEEP_DAYS = konfig.K["daten"]["aufbewahren_tage"]
ZFELDER = ("verbunden", "typ", "plmn", "tac", "eci", "enb", "sektor", "cellid", "pci", "distanz_m", "rsrp", "rsrq")
SCHEMA = """
CREATE TABLE IF NOT EXISTS abfrage (
  t INTEGER PRIMARY KEY, ok INTEGER NOT NULL, fehler TEXT, technik TEXT, rtt REAL, wg_s INTEGER, boot INTEGER,
  box_rx INTEGER, box_tx INTEGER, wg_rx INTEGER, wg_tx INTEGER, lat REAL, lng REAL, genauigkeit_m INTEGER, quelle TEXT);
CREATE TABLE IF NOT EXISTS zelle (
  t INTEGER NOT NULL, nr INTEGER NOT NULL, verbunden TEXT, typ TEXT, plmn TEXT, tac INTEGER, eci INTEGER, enb INTEGER,
  sektor INTEGER, cellid TEXT, pci INTEGER, distanz_m INTEGER, rsrp INTEGER, rsrq INTEGER, PRIMARY KEY (t, nr)) WITHOUT ROWID;
CREATE INDEX IF NOT EXISTS zelle_eci ON zelle (eci);
CREATE TABLE IF NOT EXISTS gps (
  t_ms INTEGER PRIMARY KEY, lat REAL NOT NULL, lng REAL NOT NULL, acc REAL, speed REAL, heading REAL, quelle TEXT);
"""


def verbinden():
    con = sqlite3.connect(PFAD, timeout=15)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=NORMAL")
    con.executescript(SCHEMA)
    return con


def _mit(fn):
    con = verbinden()
    try:
        with con:
            return fn(con)
    finally:
        con.close()


# ---- schreiben ----
def abfrage_schreiben(t, technik, zellen, rtt=None, wg_s=None, boot=None, box_b=None, wg_b=None, geo=None):
    g = geo or {}
    def f(con):
        con.execute("INSERT OR REPLACE INTO abfrage VALUES (?,1,NULL,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (t, technik, rtt, wg_s, boot, *(box_b or (None, None)), *(wg_b or (None, None)),
                     g.get("lat"), g.get("lng"), g.get("genauigkeit_m"), g.get("quelle")))
        con.execute("DELETE FROM zelle WHERE t=?", (t,))
        con.executemany(f"INSERT INTO zelle VALUES (?,?,{','.join('?' * len(ZFELDER))})",
                        [(t, i, *(c.get(k) for k in ZFELDER)) for i, c in enumerate(zellen)])
    _mit(f)


def fehler_schreiben(t, fehler, rtt=None, wg_s=None):
    _mit(lambda con: con.execute("INSERT OR REPLACE INTO abfrage (t, ok, fehler, rtt, wg_s) VALUES (?,0,?,?,?)",
                                 (t, fehler, rtt, wg_s)))


def gps_schreiben(zeilen):
    """zeilen: [(t_ms, lat, lng, acc, speed, heading, quelle)]; doppelte Zeitstempel ersetzen den alten Punkt."""
    _mit(lambda con: con.executemany("INSERT OR REPLACE INTO gps VALUES (?,?,?,?,?,?,?)", zeilen))
    return len(zeilen)


def aufraeumen(tage=KEEP_DAYS):
    grenze = int(time.time() - tage * 86400)
    def f(con):
        con.execute("DELETE FROM zelle WHERE t < ?", (grenze,))
        con.execute("DELETE FROM abfrage WHERE t < ?", (grenze,))
        con.execute("DELETE FROM gps WHERE t_ms < ?", (grenze * 1000,))
    _mit(f)


# ---- lesen ----
def messungen(seit=0, bis=None):
    """Abfragen ab seit (ausschließlich) bis bis (einschließlich), zeitlich sortiert:
    Erfolg {t, technik, zellen, rtt, wg_s, boot, box_b, wg_b}, Fehler {t, fehler, rtt, wg_s}."""
    bis = bis if bis is not None else 2 ** 40
    def f(con):
        zs = {}
        for r in con.execute(f"SELECT t, {', '.join(ZFELDER)} FROM zelle WHERE t > ? AND t <= ? ORDER BY t, nr", (seit, bis)):
            zs.setdefault(r[0], []).append(dict(zip(ZFELDER, r[1:])))
        out = []
        for (t, ok, fehler, technik, rtt, wg_s, boot, brx, btx, wrx, wtx) in con.execute(
                "SELECT t, ok, fehler, technik, rtt, wg_s, boot, box_rx, box_tx, wg_rx, wg_tx FROM abfrage "
                "WHERE t > ? AND t <= ? ORDER BY t", (seit, bis)):
            if ok:
                out.append({"t": t, "technik": technik, "zellen": zs.get(t, []), "rtt": rtt, "wg_s": wg_s, "boot": boot,
                            "box_b": [brx, btx] if brx is not None else None, "wg_b": [wrx, wtx] if wrx is not None else None})
            else:
                out.append({"t": t, "fehler": fehler or "", "rtt": rtt, "wg_s": wg_s})
        return out
    return _mit(f)


def verlauf(ab=0, bis=None):
    """Erfolgreiche Abfragen mit primärer Zelle und angezeigtem Ort, je Zeile als Text:
    zeit, plmn, tac, eci, cellid, pci, rsrp, rsrq, distanz_m, lat, lng, genauigkeit_m."""
    bis = bis if bis is not None else 2 ** 40
    s = lambda v: "" if v is None else str(v)
    return _mit(lambda con: [[s(v) for v in r] for r in con.execute(
        "SELECT a.t, z.plmn, z.tac, z.eci, z.cellid, z.pci, z.rsrp, z.rsrq, z.distanz_m, a.lat, a.lng, a.genauigkeit_m "
        "FROM abfrage a JOIN zelle z ON z.t = a.t AND z.nr = 0 WHERE a.ok = 1 AND a.t >= ? AND a.t <= ? ORDER BY a.t", (ab, bis))])


def gps(seit_ms=0, bis_ms=None):
    """GPS-Punkte (t_ms, lat, lng, acc, speed, heading, quelle) mit seit_ms < t_ms ≤ bis_ms, zeitlich sortiert."""
    bis_ms = bis_ms if bis_ms is not None else 2 ** 50
    return _mit(lambda con: con.execute("SELECT t_ms, lat, lng, acc, speed, heading, quelle FROM gps "
                                        "WHERE t_ms > ? AND t_ms <= ? ORDER BY t_ms", (seit_ms, bis_ms)).fetchall())
