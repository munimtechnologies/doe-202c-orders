# Tests for skills/doe-202c-orders (orders_lookup.py 0.2.1, doe_202c_orders.csv,
# doe_202c_plant_mw.csv, doe_202c_court.csv, SKILL.md). Expected values were counted by hand
# from the tables.
# Copyright 2026 MV2, Munim, Inc. Apache-2.0. Made with AI agents working in MV2's name.
import datetime as dt
import io
import json
import os
import sys
import unittest
from collections import Counter
from contextlib import redirect_stdout, redirect_stderr

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.join(HERE, "skills", "doe-202c-orders")
sys.path.insert(0, SKILL)
import orders_lookup as ol  # noqa: E402

D = dt.date
PLANT_ORDERS_NOV = {"campbell": "202-26-39", "wagner": "202-26-25A", "eddystone": "202-26-40",
                    "stanton": "202-26-42", "centralia": "202-26-44", "schahfer": "202-26-46",
                    "culley": "202-26-47", "craig": "202-26-49"}


def run(*argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = ol.main(list(argv))
    return code, out.getvalue()


class TestTables(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = ol.load_orders()
        cls.plants = ol.load_plants()
        cls.court = ol.load_court()

    def test_orders_table(self):
        self.assertEqual(len(self.rows), 87)
        self.assertEqual(len({r["order"] for r in self.rows}), 87)
        self.assertEqual(Counter(r["kind"] for r in self.rows),
                         Counter({"event": 38, "plant": 34, "island": 15}))
        self.assertEqual(Counter(r["issued"].year for r in self.rows), Counter({2025: 19, 2026: 68}))
        for r in self.rows:
            self.assertTrue(r["source"].startswith("https://"), r["order"])
            self.assertLessEqual(r["issued"], r["effective"], r["order"])
            if r["expires"] is not None:
                self.assertLessEqual(r["effective"], r["expires"], r["order"])
            self.assertEqual(r["kind"] == "plant", bool(r["plant_key"]), r["order"])
        self.assertEqual([r["order"] for r in self.rows if r["expires"] is None],
                         ["202-25-1", "202-25-2"])

    def test_as_of(self):
        newest = max(r["issued"] for r in self.rows)
        self.assertEqual(newest, D(2026, 11, 6))
        self.assertLessEqual(newest, D.fromisoformat(ol.TABLE_AS_OF))
        self.assertEqual(ol.TABLE_AS_OF, "2026-11-13")
        self.assertEqual(ol.__version__, "0.2.1")

    def test_plants_table(self):
        self.assertEqual(sorted(self.plants), sorted(PLANT_ORDERS_NOV))
        self.assertEqual({r["plant_key"] for r in self.rows if r["kind"] == "plant"},
                         set(self.plants))
        self.assertEqual(self.plants["campbell"]["plant_id_eia"], "1710")
        self.assertEqual(self.plants["stanton"]["summer_mw"], 453.4)

    def test_court_table(self):
        self.assertEqual(len(self.court), 2)
        by_order = {r["order"]: r for r in self.rows}
        for c in self.court:
            self.assertIn(c["order"], by_order)  # every action is on an order in the table
            self.assertEqual(c["plant_key"], by_order[c["order"]]["plant_key"])
            self.assertTrue(c["source"].startswith("https://"), c)
            self.assertIn(c["date_kind"], ("decided", "filed", "reported"))
            self.assertLessEqual(c["date"], D.fromisoformat(ol.COURT_AS_OF))
            self.assertTrue(c["note"], c)
        first, second = self.court
        self.assertEqual((first["order"], first["date"], first["action"], first["case"][:11]),
                         ("202-25-3", D(2026, 9, 11), "vacated", "No. 25-1159"))
        # The vacated order had already expired when the court ruled.
        self.assertLess(by_order["202-25-3"]["expires"], first["date"])
        self.assertEqual((second["date"], second["date_kind"], second["action"]),
                         (D(2026, 10, 26), "filed", "rehearing petition by DOE"))
        # Filed on the 45th day after the decision (FRAP 40, a U.S. agency is a party).
        self.assertEqual((second["date"] - first["date"]).days, 45)
        self.assertIn("climate.law.columbia.edu", second["source"])
        self.assertIn("publicpower.org", second["note"])  # the earlier report is still cited


class TestLookups(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = ol.load_orders()
        cls.plants = ol.load_plants()
        cls.court = ol.load_court()

    def test_base_order(self):
        self.assertEqual(ol.base_order("202-26-01A"), "202-26-01")
        self.assertEqual(ol.base_order("202-25-1F"), "202-25-1")
        self.assertEqual(ol.base_order("202-26-39"), "202-26-39")

    def test_in_force_november(self):
        for day in (D(2026, 11, 8), D(2026, 11, 9), D(2026, 11, 13)):
            sel = ol.in_force(self.rows, day)
            self.assertEqual(len(sel), 10, day)
            self.assertEqual({r["plant_key"]: r["order"] for r in sel if r["kind"] == "plant"},
                             PLANT_ORDERS_NOV)
            self.assertEqual(sorted(r["order"] for r in sel if r["kind"] == "island"),
                             ["202-25-1F", "202-25-2F"])
            self.assertEqual([r for r in sel if r["kind"] == "event"], [])
        m = ol.mw_in_force(self.rows, self.plants, D(2026, 11, 9))
        self.assertEqual((len(m["plants"]), m["summer_mw"], m["coal_summer_mw"], m["missing_mw"]),
                         (8, 4849.9, 3692.9, []))

    def test_in_force_january_events(self):
        sel = ol.in_force(self.rows, D(2026, 1, 26), "event")
        self.assertEqual(sorted(r["order"] for r in sel),
                         ["202-26-01", "202-26-01A", "202-26-02", "202-26-03", "202-26-04",
                          "202-26-06", "202-26-07", "202-26-08"])

    def test_expiring(self):
        got = [(r["order"], left) for r, left in ol.expiring(self.rows, D(2026, 11, 9), 14)]
        self.assertEqual(got, [("202-26-39", 5), ("202-26-25A", 8), ("202-26-40", 11)])
        self.assertEqual(len(ol.expiring(self.rows, D(2026, 11, 9), 30)), 4)
        # PREPA's 1E/2E expire 7 November but 1F/2F follow in the table; Guam's 202-26-38 does not.
        got = [r["order"] for r, _ in ol.expiring(self.rows, D(2026, 11, 1), 7)]
        self.assertEqual(got, ["202-26-38"])

    def test_find_plants(self):
        self.assertEqual(ol.find_plants(self.plants, "1710"), ["campbell"])
        self.assertEqual(ol.find_plants(self.plants, "J.H. Campbell"), ["campbell"])
        self.assertEqual(ol.find_plants(self.plants, "Schahfer"), ["schahfer"])
        self.assertEqual(ol.find_plants(self.plants, "Stanton Energy Center"), ["stanton"])
        self.assertEqual(ol.find_plants(self.plants, "Brandon Shores"), [])
        self.assertEqual(ol.find_plants(self.plants, ""), [])

    def test_chains(self):
        c = ol.chain(self.rows, "campbell")
        self.assertEqual([r["order"] for r in c["orders"]],
                         ["202-25-3", "202-25-7", "202-25-9", "202-26-16", "202-26-22", "202-26-39"])
        self.assertEqual((c["gaps"], c["first_start"]), ([], D(2025, 5, 23)))
        w = ol.chain(self.rows, "wagner")
        self.assertEqual(w["gaps"], [{"after": "202-25-6A", "before": "202-26-25", "days": 141,
                                      "from": "2026-01-01", "to": "2026-05-21"}])

    def test_renewals(self):
        rs = ol.renewals(self.rows)
        self.assertEqual(len(rs), 26)
        self.assertEqual(Counter(r["lead_days"] for r in rs),
                         Counter({0: 9, 1: 9, 2: 4, 3: 3, -141: 1}))
        self.assertEqual([r["previous"] for r in rs if r["gap_days"]], ["202-25-6A"])
        note = ol.renewal_note(self.rows)
        self.assertIn("Plant renewals in the table: 26. 25 followed with no uncovered day, "
                      "issued 0 to 3 days before", note)
        self.assertIn("202-25-6A (wagner) lapsed for 141 days before 202-26-25.", note)

    def test_successor(self):
        by = {r["order"]: r for r in self.rows}
        self.assertEqual(ol.successor(self.rows, by["202-26-22"])["order"], "202-26-39")
        self.assertIsNone(ol.successor(self.rows, by["202-26-39"]))
        self.assertEqual(ol.successor(self.rows, by["202-25-1E"])["order"], "202-25-1F")
        self.assertEqual(ol.successor(self.rows, by["202-26-02"])["order"], "202-26-02A")

    def test_court_for(self):
        self.assertEqual(len(ol.court_for(self.court, orders=["202-25-3"])), 2)
        self.assertEqual(len(ol.court_for(self.court, plant_key="campbell")), 2)
        self.assertEqual(ol.court_for(self.court, orders=["202-26-39"]), [])
        self.assertEqual(ol.court_for(self.court, plant_key="eddystone"), [])
        # "202-25-3" must not match 202-25-3x orders or the other way round.
        self.assertEqual(ol.court_for([{"order": "202-25-30", "plant_key": "x"}],
                                      orders=["202-25-3"]), [])

    def test_missing_court_file(self):
        self.assertEqual(ol.load_court(os.path.join(SKILL, "no_such_file.csv")), [])


class TestCli(unittest.TestCase):
    def test_plant(self):
        code, out = run("plant", "campbell", "--date", "2026-11-08")
        self.assertEqual(code, 0)
        self.assertIn("J.H. Campbell (MI, EIA plant 1710", out)
        self.assertIn("under order 202-26-39, 6 days until its expiry date 2026-11-14", out)
        self.assertIn("Gaps between orders: none.", out)
        self.assertIn("202-25-3  2026-09-11 decided: vacated, No. 25-1159", out)
        self.assertIn("202-25-3  2026-10-26 filed: rehearing petition by DOE, No. 25-1159", out)
        self.assertIn("says nothing about any other order", out)
        self.assertNotIn("WARNING", out)

    def test_plant_json(self):
        code, out = run("plant", "Wagner", "--date", "2026-11-09", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        (p,) = res["plants"]
        self.assertEqual((p["plant_key"], p["current_order"], p["current_expiry"],
                          p["days_until_expiry"], len(p["orders"]), len(p["gaps"]), p["court"]),
                         ("wagner", "202-26-25A", "2026-11-17", 8, 4, 1, []))
        code, out = run("plant", "1710", "--date", "2026-11-13", "--json")
        (p,) = json.loads(out)["plants"]
        self.assertEqual([(c["order"], c["action"]) for c in p["court"]],
                         [("202-25-3", "vacated"), ("202-25-3", "rehearing petition by DOE")])
        # The vacatur changes nothing in the in-force dates: 202-26-39 is still current.
        self.assertEqual((p["current_order"], p["days_until_expiry"]), ("202-26-39", 1))

    def test_unknown_plant(self):
        code, out = run("plant", "Brandon Shores", "--date", "2026-11-09")
        self.assertEqual(code, 1)
        self.assertIn("No plant under a 202(c) plant order matches", out)

    def test_in_force_after_as_of_warns(self):
        code, out = run("in-force", "--date", "2026-12-01")
        self.assertEqual(code, 0)
        self.assertIn("WARNING: 2026-12-01 is after the table's as-of date (2026-11-13)", out)
        # Campbell, Wagner, Eddystone and Stanton have expired in the table by then.
        self.assertIn("Plant orders cover 4 plant(s)", out)
        code, out = run("in-force", "--date", "2026-11-13")
        self.assertNotIn("WARNING", out)

    def test_expiring_cli(self):
        code, out = run("expiring", "--date", "2026-11-09", "--days", "14", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual([(o["order"], o["days_until_expiry"]) for o in res["orders"]],
                         [("202-26-39", 5), ("202-26-25A", 8), ("202-26-40", 11)])
        self.assertIn("Description of past orders only, not a forecast.", res["renewal_note"])

    def test_order(self):
        code, out = run("order", "202-25-1e")
        self.assertEqual(code, 0)
        self.assertIn("Next order in the same chain: 202-25-1F.", out)
        self.assertIn("Court actions in the court table: none.", out)
        code, out = run("order", "202-26-99")
        self.assertEqual(code, 1)

    def test_order_court(self):
        code, out = run("order", "202-25-3", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual(res["next_in_chain"], "202-25-7")
        self.assertEqual([c["date"] for c in res["court"]], ["2026-09-11", "2026-10-26"])
        self.assertEqual([c["date_kind"] for c in res["court"]], ["decided", "filed"])
        self.assertEqual(res["court_as_of"], "2026-11-13")
        self.assertEqual(res["version"], "0.2.1")

    def test_court_cli(self):
        code, out = run("court")
        self.assertEqual(code, 0)
        self.assertIn("Court actions on 202(c) orders in the court table: 2.", out)
        self.assertIn("https://media.cadc.uscourts.gov/opinions/docs/2026/09/25-1159.pdf", out)
        self.assertIn("https://climate.law.columbia.edu/news/climate-litigation-updates-november-6-2026",
                      out)
        code, out = run("court", "--json")
        self.assertEqual(len(json.loads(out)["court"]), 2)

    def test_summary(self):
        code, out = run("summary", "--date", "2026-11-09", "--json")
        self.assertEqual(code, 0)
        res = json.loads(out)
        self.assertEqual((res["orders"], res["by_kind"], res["in_force"], res["mw"]["summer_mw"],
                          res["court_actions"], res["orders_vacated"]),
                         (87, {"plant": 34, "event": 38, "island": 15}, 10, 4849.9, 2, ["202-25-3"]))
        code, out = run("summary", "--date", "2026-11-09")
        self.assertIn("orders vacated by a court: 202-25-3.", out)

    def test_bad_date(self):
        code, _ = run("in-force", "--date", "11/09/2026")
        self.assertEqual(code, 2)


class TestSkillDoc(unittest.TestCase):
    def test_skill_md(self):
        with open(os.path.join(SKILL, "SKILL.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertTrue(text.startswith("---\nname: doe-202c-orders\n"))
        self.assertIn("\nlicense: Apache-2.0\n", text.split("\n---\n", 1)[0] + "\n")
        self.assertIn("made with AI agents", text)
        self.assertIn(ol.TABLE_AS_OF, text)
        self.assertNotIn("2026-11-08", text)
        self.assertIn("orders_lookup.py %s" % ol.__version__, text)
        self.assertIn("doe_202c_court.csv", text)
        self.assertIn("No. 25-1159", text)
        self.assertIn("26 October 2026", text)
        self.assertNotIn("reported 30 October", text)
        for bad in ("git clone", "curl ", "wget ", "pip install", "npx "):
            self.assertNotIn(bad, text)

    def test_readme(self):
        with open(os.path.join(HERE, "README.md"), encoding="utf-8") as f:
            text = f.read()
        self.assertIn("0.2.1", text)
        self.assertIn("26 October 2026", text)
        self.assertIn("Apache-2.0", text)
        self.assertNotIn("MIT", text)


if __name__ == "__main__":
    unittest.main()
