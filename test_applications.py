# Copyright 2026 Munim, Inc.
# Licensed under the Apache License, Version 2.0 (Apache-2.0).
# Made with AI agents working in the name of MV2 of Munim, Inc. (mv2@munimtech.com).
"""Checks data/doe_202c_applications.csv against the orders table and the renewals table.

Every number stated in docs/applications.md is asserted here. Standard library only.
"""
import csv
import datetime as dt
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
APPS = os.path.join(HERE, "data", "doe_202c_applications.csv")
ORDERS = os.path.join(HERE, "skills", "doe-202c-orders", "doe_202c_orders.csv")
RENEWALS = os.path.join(HERE, "data", "doe_202c_renewals.csv")
PAGE_PREFIX = "https://www.energy.gov/ceser/federal-power-act-section-202c-"
COLUMNS = ["order", "plant_key", "issued", "application_posted", "applicant",
           "application_date", "application_title", "lead_days", "page_url",
           "page_last_updated", "checked_on", "note"]


def read(path):
    with open(path, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def d(s):
    return dt.date.fromisoformat(s)


class ApplicationsTable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.apps = read(APPS)
        cls.orders = read(ORDERS)
        cls.renewals = read(RENEWALS)
        cls.by_order = {r["order"]: r for r in cls.apps}

    def test_columns(self):
        with open(APPS, encoding="utf-8", newline="") as fh:
            header = next(csv.reader(fh))
        self.assertEqual(header, COLUMNS)

    def test_one_row_per_plant_order(self):
        plant = [r for r in self.orders if r["kind"] == "plant"]
        self.assertEqual(len(plant), 35)
        self.assertEqual(len(self.apps), 35)
        self.assertEqual(len(self.by_order), 35)
        self.assertEqual(set(self.by_order), {r["order"] for r in plant})
        for r in plant:
            a = self.by_order[r["order"]]
            self.assertEqual(a["plant_key"], r["plant_key"], r["order"])
            self.assertEqual(a["issued"], r["issued"], r["order"])

    def test_orders_per_plant(self):
        counts = {}
        for r in self.apps:
            counts[r["plant_key"]] = counts.get(r["plant_key"], 0) + 1
        self.assertEqual(counts, {"campbell": 7, "eddystone": 6, "wagner": 4, "centralia": 4,
                                  "schahfer": 4, "culley": 4, "craig": 4, "stanton": 2})

    def test_field_rules(self):
        for r in self.apps:
            self.assertIn(r["application_posted"], ("yes", "no"), r["order"])
            self.assertTrue(r["page_url"].startswith(PAGE_PREFIX), r["order"])
            self.assertEqual(r["checked_on"], "2026-11-15", r["order"])
            self.assertGreaterEqual(d(r["page_last_updated"]), d(r["issued"]), r["order"])
            self.assertLessEqual(d(r["page_last_updated"]), d("2026-11-15"), r["order"])
            if r["application_posted"] == "yes":
                self.assertTrue(r["applicant"] and r["application_title"], r["order"])
                lead = (d(r["issued"]) - d(r["application_date"])).days
                self.assertGreaterEqual(lead, 0, r["order"])
                self.assertEqual(int(r["lead_days"]), lead, r["order"])
            else:
                for k in ("applicant", "application_date", "application_title", "lead_days"):
                    self.assertEqual(r[k], "", (r["order"], k))

    def test_headline_counts(self):
        yes = [r for r in self.apps if r["application_posted"] == "yes"]
        no = [r for r in self.apps if r["application_posted"] == "no"]
        self.assertEqual(len(yes), 4)
        self.assertEqual(len(no), 31)
        self.assertEqual({r["plant_key"] for r in yes}, {"wagner"})
        self.assertEqual({r["applicant"] for r in yes}, {"PJM"})
        self.assertEqual(len({r["plant_key"] for r in no}), 7)
        self.assertNotIn("wagner", {r["plant_key"] for r in no})
        yes.sort(key=lambda r: r["issued"])
        self.assertEqual([r["order"] for r in yes],
                         ["202-25-6", "202-25-6A", "202-26-25", "202-26-25A"])
        self.assertEqual([int(r["lead_days"]) for r in yes], [7, 14, 0, 15])

    def test_link_to_renewal_timing(self):
        plant = [r for r in self.renewals if r["kind"] == "plant"]
        self.assertEqual(len(plant), 27)
        requested = [r for r in plant if self.by_order[r["successor"]]["application_posted"] == "yes"]
        unrequested = [r for r in plant if self.by_order[r["successor"]]["application_posted"] == "no"]
        self.assertEqual(len(requested), 3)
        self.assertEqual(len(unrequested), 24)
        self.assertTrue(all(r["status"] == "continuous" for r in unrequested))
        self.assertEqual(sorted(r["status"] for r in requested),
                         ["continuous", "continuous", "lapse"])
        lapses = [r for r in plant if r["status"] == "lapse"]
        self.assertEqual([(r["chain"], r["successor"], r["gap_days"]) for r in lapses],
                         [("wagner", "202-26-25", "141")])
        # Chains whose orders were requested == chains that ever lapsed.
        self.assertEqual({r["chain"] for r in lapses},
                         {r["plant_key"] for r in self.apps if r["application_posted"] == "yes"})
        # The 25-6A application came 2025-10-10; nothing was posted between it and 2026-05-21.
        dates = sorted(r["application_date"] for r in self.apps if r["application_date"])
        self.assertEqual(dates, ["2025-07-21", "2025-10-10", "2026-05-21", "2026-08-04"])
        self.assertEqual((d("2026-05-21") - d("2025-10-10")).days, 223)


if __name__ == "__main__":
    unittest.main()
