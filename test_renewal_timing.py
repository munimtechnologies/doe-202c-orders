"""Checks data/doe_202c_renewals.csv, the renewal-timing table behind
docs/renewal-timing-plan.md (pre-registration id renewal-timing-1).

MV2 of Munim, Inc. (made with AI agents working in MV2's name). Apache-2.0.

Standard library only. The renewals table is rebuilt here from the orders table
(skills/doe-202c-orders/doe_202c_orders.csv, as of 14 November 2026) and must match it
row for row. The counts asserted below were made by hand from the orders table and are the
figures quoted in docs/renewal-timing-plan.md.

Definitions (one chain = one plant for plant orders, one order number without its letter
suffix for island orders; event orders are left out):
  lead_days = predecessor's last day in force - successor's issue date
              (0 = issued on the predecessor's last day; negative = issued after it ended)
  gap_days  = successor's first day in force - predecessor's last day - 1
              (0 = starts the next day; -1 = starts on the predecessor's last day, one day of
              overlap; positive = that many days with no order in force)
"""

import csv
import datetime as dt
import os
import re
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ORDERS = os.path.join(HERE, "skills", "doe-202c-orders", "doe_202c_orders.csv")
RENEWALS = os.path.join(HERE, "data", "doe_202c_renewals.csv")
AS_OF = dt.date(2026, 11, 15)
COLUMNS = ["chain", "kind", "predecessor", "pred_expires", "successor", "succ_issued",
           "succ_effective", "lead_days", "gap_days", "status"]


def d(s):
    return dt.date.fromisoformat(s) if s else None


def load_orders(path=ORDERS):
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def chain_key(row):
    if row["kind"] == "plant":
        return row["plant_key"]
    return re.sub(r"[A-Z]+$", "", row["order"])


def chains(orders):
    out = {}
    for r in orders:
        if r["kind"] not in ("plant", "island"):
            continue
        out.setdefault((chain_key(r), r["kind"]), []).append(r)
    for rows in out.values():
        rows.sort(key=lambda r: (r["issued"], r["order"]))
    return out


def build(orders):
    rows = []
    for (key, kind), seq in chains(orders).items():
        for a, b in zip(seq, seq[1:]):
            if not a["expires"]:
                continue  # 202-25-1 and 202-25-2: expiry not stated on DOE's page
            exp, iss, eff = d(a["expires"]), d(b["issued"]), d(b["effective"])
            gap = (eff - exp).days - 1
            rows.append({
                "chain": key, "kind": kind, "predecessor": a["order"],
                "pred_expires": a["expires"], "successor": b["order"],
                "succ_issued": b["issued"], "succ_effective": b["effective"],
                "lead_days": str((exp - iss).days), "gap_days": str(gap),
                "status": "lapse" if gap > 0 else "continuous",
            })
    return rows


def load_renewals(path=RENEWALS):
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return reader.fieldnames, list(reader)


def sort_key(r):
    return (r["kind"], r["chain"], r["succ_issued"], r["successor"])


class TestRenewalTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.orders = load_orders()
        cls.header, cls.rows = load_renewals()
        cls.plant = [r for r in cls.rows if r["kind"] == "plant"]
        cls.island = [r for r in cls.rows if r["kind"] == "island"]

    def test_header(self):
        self.assertEqual(self.header, COLUMNS)

    def test_matches_orders_table(self):
        built = sorted(build(self.orders), key=sort_key)
        mine = sorted(self.rows, key=sort_key)
        self.assertEqual(len(built), len(mine))
        for b, m in zip(built, mine):
            self.assertEqual(dict(m), b)

    def test_counts(self):
        self.assertEqual(len(self.rows), 37)
        self.assertEqual(len(self.plant), 27)
        self.assertEqual(len(self.island), 10)
        self.assertEqual(Counter(r["chain"] for r in self.plant),
                         Counter({"campbell": 6, "eddystone": 5, "wagner": 3, "centralia": 3,
                                  "schahfer": 3, "culley": 3, "craig": 3, "stanton": 1}))

    def test_one_lapse(self):
        lapses = [r for r in self.rows if r["status"] == "lapse"]
        self.assertEqual(len(lapses), 1)
        r = lapses[0]
        self.assertEqual((r["chain"], r["predecessor"], r["successor"]),
                         ("wagner", "202-25-6A", "202-26-25"))
        self.assertEqual(int(r["gap_days"]), 141)  # 1 Jan to 21 May 2026 uncovered
        self.assertEqual(int(r["lead_days"]), -141)

    def test_plant_lead_days(self):
        cont = [r for r in self.plant if r["status"] == "continuous"]
        self.assertEqual(len(cont), 26)
        self.assertEqual(Counter(int(r["lead_days"]) for r in cont),
                         Counter({0: 9, 1: 10, 2: 4, 3: 3}))
        # no continuous renewal was issued after the predecessor's last day
        self.assertTrue(all(0 <= int(r["lead_days"]) <= 3 for r in cont))

    def test_plant_gap_days_shift(self):
        cont = [r for r in self.plant if r["status"] == "continuous"]
        early = [r for r in cont if d(r["succ_issued"]) < dt.date(2026, 3, 1)]
        late = [r for r in cont if d(r["succ_issued"]) >= dt.date(2026, 3, 1)]
        self.assertEqual(len(early), 7)
        self.assertEqual(len(late), 19)
        self.assertTrue(all(r["gap_days"] == "-1" for r in early))
        self.assertTrue(all(r["gap_days"] == "0" for r in late))

    def test_island(self):
        self.assertTrue(all(r["status"] == "continuous" for r in self.island))
        self.assertEqual(Counter(int(r["lead_days"]) for r in self.island),
                         Counter({0: 6, 1: 2, 2: 2}))

    def test_campbell_post_ruling_renewal(self):
        r = [x for x in self.plant if x["successor"] == "202-26-51"][0]
        self.assertEqual((r["lead_days"], r["gap_days"]), ("1", "0"))


class TestPendingOnAsOfDate(unittest.TestCase):
    """The last order of each chain, as stated in docs/renewal-timing-plan.md."""

    @classmethod
    def setUpClass(cls):
        cls.last = {k: seq[-1] for k, seq in chains(load_orders()).items()}

    def test_pending(self):
        pending = {r["order"]: r["expires"] for r in self.last.values()
                   if r["expires"] and d(r["expires"]) >= AS_OF}
        self.assertEqual(pending, {
            "202-26-25A": "2026-11-17", "202-26-40": "2026-11-20", "202-26-42": "2026-11-30",
            "202-26-44": "2026-12-11", "202-26-46": "2026-12-18", "202-26-47": "2026-12-18",
            "202-26-49": "2026-12-25", "202-26-51": "2027-02-12", "202-25-1F": "2027-02-05",
            "202-25-2F": "2027-02-05"})

    def test_lapsed_without_successor(self):
        lapsed = {r["order"]: r["expires"] for r in self.last.values()
                  if r["expires"] and d(r["expires"]) < AS_OF}
        self.assertEqual(lapsed, {"202-26-38": "2026-11-04"})  # Guam Power Authority


if __name__ == "__main__":
    unittest.main()
