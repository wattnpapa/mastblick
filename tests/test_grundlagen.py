# Grundtests mit erfundenen Daten: python3 -m unittest discover -s tests
import html, importlib.machinery, importlib.util, math, os, sys, tempfile, types, unittest

HIER = os.path.dirname(os.path.abspath(__file__))
WURZEL = os.path.dirname(HIER)
TMP = tempfile.mkdtemp(prefix="mastblick-test-")
with open(os.path.join(TMP, "config.toml"), "w") as f:
    f.write(f'[daten]\nverzeichnis = "{TMP}"\n[box]\nadresse = "192.0.2.1"\n')
os.environ["MASTBLICK_KONFIG"] = os.path.join(TMP, "config.toml")
sys.path.insert(0, os.path.join(WURZEL, "lib"))

from mastblick import db, konfig  # noqa: E402


def programm(name):
    """Skript aus bin/ als Modul laden, ohne den Hauptteil auszuführen."""
    lader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), os.path.join(WURZEL, "bin", name))
    spec = importlib.util.spec_from_loader(lader.name, lader)
    mod = importlib.util.module_from_spec(spec)
    lader.exec_module(mod)
    return mod


ABFRAGE = programm("mastblick-abfrage")
API = programm("mastblick-api")


def zelle(connected, plmn, tac, cellid, dist, rsrp, pci=100):
    return (f"<Cell><Connected>{connected}</Connected><CellType>lte</CellType><PLMN>{plmn}</PLMN><TAC>{tac}</TAC>"
            f"<PhysicalId>{pci}</PhysicalId><Cellid>{cellid}</Cellid><Distance>{dist}</Distance><RSRP>{rsrp}</RSRP>"
            f"<Rsrq>-9</Rsrq></Cell>")


class Konfig(unittest.TestCase):
    def test_datei_und_standard(self):
        self.assertEqual(konfig.DATEN, TMP)
        self.assertEqual(konfig.K["box"]["adresse"], "192.0.2.1")
        self.assertEqual(konfig.K["box"]["tr064_port"], 49000)          # Standardwert bleibt
        self.assertFalse(konfig.K["melden"]["beacondb"])                 # Melden ist ohne Zustimmung aus
        self.assertEqual(konfig.box_url("/x"), "http://192.0.2.1:49000/x")


class Tr064(unittest.TestCase):
    def test_zellliste_hex_und_sortierung(self):
        liste = zelle("none", "26201", "1A2B", "01234-05", 0, -101, 7) + zelle("primary", "26201", "1A2B", "06258-15", 450, -88, 473)
        antwort = (f"<s:Envelope><s:Body><u:GetInfoExResponse><NewCurrentAccessTechnology>LTE</NewCurrentAccessTechnology>"
                   f"<NewSignalRSRP0>-88</NewSignalRSRP0><NewCellList>{html.escape(liste)}</NewCellList>"
                   f"</u:GetInfoExResponse></s:Body></s:Envelope>")
        alt = ABFRAGE.subprocess.run
        ABFRAGE.subprocess.run = lambda *a, **k: types.SimpleNamespace(stdout=antwort)
        try:
            info = ABFRAGE.tr064()
        finally:
            ABFRAGE.subprocess.run = alt
        self.assertEqual(info["technik"], "LTE")
        p = info["zellen"][0]                                            # primäre Zelle steht vorn
        self.assertEqual(p["verbunden"], "primary")
        self.assertEqual((p["enb"], p["sektor"], p["eci"], p["tac"]), (0x06258, 0x15, 0x625815, 0x1A2B))
        self.assertEqual(p["distanz_m"], 450)


class Datenbank(unittest.TestCase):
    def test_abfrage_fehler_gps_aufraeumen(self):
        t = 2_000_000_000
        z = [{"verbunden": "primary", "typ": "lte", "plmn": "26201", "tac": 1, "eci": 0x625815, "enb": 0x6258,
              "sektor": 0x15, "cellid": "06258-15", "pci": 473, "distanz_m": 150, "rsrp": -90, "rsrq": -9}]
        db.abfrage_schreiben(t, "LTE", z, rtt=50.0, wg_s=10, boot=t - 600, box_b=[10, 20], wg_b=[1, 2],
                             geo={"lat": 52.5, "lng": 13.4, "genauigkeit_m": 300, "quelle": "Test"})
        db.fehler_schreiben(t + 10, "keine Antwort", wg_s=200)
        db.gps_schreiben([(t * 1000, 52.5001, 13.4001, 5, 10.0, 90, "test")])
        a, b = db.messungen(t - 1)
        self.assertEqual(a["zellen"][0]["cellid"], "06258-15")
        self.assertEqual((a["box_b"], a["wg_b"], a["boot"]), ([10, 20], [1, 2], t - 600))
        self.assertEqual(b["fehler"], "keine Antwort")
        self.assertEqual(db.verlauf(t, t)[0][4], "06258-15")
        self.assertEqual(len(db.gps(t * 1000 - 1)), 1)


class Mastschaetzung(unittest.TestCase):
    def test_ringe_um_bekannten_mast(self):
        mast = (52.50, 13.40)
        obs = []
        for w in range(0, 360, 40):                                      # Messpunkte rundherum, 600 m entfernt
            d = 600
            lat = mast[0] + d * math.sin(math.radians(w)) / 110540
            lng = mast[1] + d * math.cos(math.radians(w)) / (111320 * math.cos(math.radians(mast[0])))
            obs.append({"lat": lat, "lng": lng, "distanz_m": d / API.TA_FAKTOR})
        e = API.schaetzung(obs)
        self.assertIsNotNone(e)
        self.assertLess(math.hypot(*API.enu(mast[0], mast[1], e["lat"], e["lng"])), 20)
        self.assertTrue(e["eindeutig"])

    def test_punkte_auf_einer_linie_sind_mehrdeutig(self):
        obs = [{"lat": 52.5, "lng": 13.40 + i * 0.003, "distanz_m": 400 + abs(i - 3) * 100} for i in range(7)]
        e = API.schaetzung(obs)
        if e:
            self.assertFalse(e["eindeutig"])


if __name__ == "__main__":
    unittest.main()
