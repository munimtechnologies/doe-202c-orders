# SPDX-License-Identifier: Apache-2.0
"""Tests for dispatch_core (pre-registration dispatch-1). Standard library only.
Every expected value was worked out by hand from the inputs written here or
from skills/doe-202c-orders/doe_202c_orders.csv (88 rows, as of 16 Nov 2026)."""
import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dispatch_core as core  # noqa: E402

UTC = dt.timezone.utc
ORDERS = os.path.join(HERE, "..", "skills", "doe-202c-orders", "doe_202c_orders.csv")
PLANTS = os.path.join(HERE, "..", "skills", "doe-202c-orders", "doe_202c_plant_mw.csv")


def H(y, m, d, h=0):
    return dt.datetime(y, m, d, h, tzinfo=UTC)


class TestTime(unittest.TestCase):
    def test_day_start(self):
        self.assertEqual(core.day_start_utc(dt.date(2026, 1, 1), -5), H(2026, 1, 1, 5))
        self.assertEqual(core.day_start_utc(dt.date(2026, 1, 1), -8), H(2026, 1, 1, 8))

    def test_merge(self):
        a = [(H(2026, 1, 3), H(2026, 1, 4)), (H(2026, 1, 1), H(2026, 1, 2)), (H(2026, 1, 2), H(2026, 1, 3))]
        self.assertEqual(core.merge_intervals(a), [(H(2026, 1, 1), H(2026, 1, 4))])
        b = [(H(2026, 1, 1), H(2026, 1, 2)), (H(2026, 1, 5), H(2026, 1, 6))]
        self.assertEqual(core.merge_intervals(b), b)

    def test_hours_in_clipped(self):
        iv = [(H(2026, 1, 1, 5), H(2026, 1, 2, 5))]
        hrs = core.hours_in(iv, H(2021, 1, 1), H(2026, 1, 1, 10))
        self.assertEqual(hrs, [H(2026, 1, 1, h) for h in range(5, 10)])
        self.assertEqual(len(core.hours_in(iv, H(2021, 1, 1), H(2027, 1, 1))), 24)

    def test_shift_years(self):
        self.assertEqual(core.shift_years(H(2024, 2, 29, 12), 1), H(2023, 2, 28, 12))
        self.assertEqual(core.shift_years(H(2026, 7, 1, 3), 3), H(2023, 7, 1, 3))

    def test_intersect(self):
        a = [(H(2026, 1, 1), H(2026, 1, 10))]
        b = [(H(2025, 12, 30), H(2026, 1, 2)), (H(2026, 1, 9), H(2026, 1, 12))]
        self.assertEqual(core.intersect_intervals(a, b),
                         [(H(2026, 1, 1), H(2026, 1, 2)), (H(2026, 1, 9), H(2026, 1, 10))])


class TestMetrics(unittest.TestCase):
    def test_top_n(self):
        h = [H(2026, 7, 1, i) for i in range(5)]
        demand = {h[0]: 5.0, h[1]: 7.0, h[2]: 7.0, h[3]: 1.0}  # h[4] has no demand
        self.assertEqual(core.top_n_hours(demand, h, 2), [h[1], h[2]])
        self.assertEqual(core.top_n_hours(demand, h, 3), [h[1], h[2], h[0]])
        self.assertEqual(core.top_n_hours(demand, h, 10), [h[1], h[2], h[0], h[3]])

    def test_plant_metrics(self):
        h = [H(2026, 7, 1, i) for i in range(4)]
        gen = {h[0]: 100.0, h[1]: 0.0, h[2]: 50.0}
        m = core.plant_metrics(gen, h, 100.0)
        self.assertEqual(m["n"], 4)
        self.assertEqual(m["online_hours"], 2)
        self.assertAlmostEqual(m["online_share"], 0.5)
        self.assertAlmostEqual(m["mean_mw"], 37.5)
        self.assertAlmostEqual(m["cf"], 0.375)
        self.assertEqual(m["no_record_hours"], 1)
        self.assertEqual(core.plant_metrics(gen, [], 100.0)["online_share"], None)

    def test_ratio(self):
        self.assertAlmostEqual(core.ratio(0.6, 0.4), 1.5)
        self.assertIsNone(core.ratio(0.6, 0))
        self.assertIsNone(core.ratio(None, 0.4))


class TestOrders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = core.read_orders(ORDERS)
        cls.plants = core.read_plants(PLANTS)

    def test_counts(self):
        self.assertEqual(len(self.rows), 88)
        self.assertEqual(len(self.plants), 8)
        self.assertEqual(self.plants["campbell"]["generators"], ["1", "2", "3"])
        self.assertAlmostEqual(self.plants["campbell"]["summer_mw"], 1330.5)
        self.assertEqual(set(self.plants), set(core.PLANT_TZ))

    def test_campbell_one_unbroken_interval(self):
        iv = core.order_intervals(self.rows, "campbell", -5)
        # 202-25-3 from 2025-05-23 to 202-26-51 ending 2027-02-12, no gap.
        self.assertEqual(iv, [(H(2025, 5, 23, 5), H(2027, 2, 13, 5))])

    def test_wagner_lapse(self):
        iv = core.order_intervals(self.rows, "wagner", -5)
        self.assertEqual(iv, [(H(2025, 7, 28, 5), H(2026, 1, 1, 5)),
                              (H(2026, 5, 22, 5), H(2026, 11, 18, 5))])

    def test_centralia_pacific(self):
        iv = core.order_intervals(self.rows, "centralia", -8)
        # 202-25-11 from 2025-12-16 to 202-26-44 ending 2026-12-11.
        self.assertEqual(iv, [(H(2025, 12, 16, 8), H(2026, 12, 12, 8))])

    def test_pjm_events(self):
        iv = core.event_intervals(self.rows, {"PJM"}, -5)
        # 202-26-02/-06/-02A/-06A: Jan 25 - Feb 2 2026, merged into one window.
        self.assertEqual(iv[0], (H(2026, 1, 25, 5), H(2026, 2, 3, 5)))
        # 202-26-23 (May 18-20), 202-26-32/-33/-32A/-33A (Jun 30 - Jul 7),
        # 202-26-35 (Jul 14-21), 202-26-41 (Sep 1-8), 202-26-45 (Sep 17-18),
        # 202-26-50 (Oct 13-16): 7 windows in all.
        self.assertEqual(len(iv), 7)
        self.assertEqual(iv[2], (H(2026, 6, 30, 5), H(2026, 7, 8, 5)))
        self.assertEqual(iv[-1], (H(2026, 10, 13, 5), H(2026, 10, 17, 5)))

    def test_wagner_s2_excludes_january(self):
        oiv = core.order_intervals(self.rows, "wagner", -5)
        eiv = core.event_intervals(self.rows, {"PJM"}, -5)
        s2 = core.intersect_intervals(eiv, oiv)
        # January and May 18-20 fall in Wagner's lapse; 5 windows remain.
        self.assertEqual(len(s2), 5)
        self.assertEqual(s2[0], (H(2026, 6, 30, 5), H(2026, 7, 8, 5)))
        hrs = core.hours_in(s2, H(2021, 1, 1), H(2026, 10, 1))
        # through Sep 30: Jun 30-Jul 7 (8 days), Jul 14-21 (8), Sep 1-8 (8), Sep 17-18 (2) = 26 days
        self.assertEqual(len(hrs), 26 * 24)

    def test_no_florida_overlap_for_stanton(self):
        oiv = core.order_intervals(self.rows, "stanton", -5)
        eiv = core.event_intervals(self.rows, {"Florida"}, -5)
        self.assertEqual(core.intersect_intervals(eiv, oiv), [])


class TestAnalyseAndScore(unittest.TestCase):
    def test_analyse_small(self):
        rows = [{"kind": "plant", "plant_key": "campbell", "area": "MISO",
                 "effective": "2026-07-01", "expires": "2026-07-01"}]
        info = {"summer_mw": 100.0}
        hrs = [H(2026, 7, 1, 5) + i * core.HOUR for i in range(24)]
        demand = {h: float(i) for i, h in enumerate(hrs)}  # highest at the last hour
        gen = {h: (100.0 if i >= 20 else 0.0) for i, h in enumerate(hrs)}
        r = core.analyse_plant("campbell", info, rows, demand, gen, H(2026, 7, 2, 5), top_n=4)
        self.assertEqual(r["order_hours"], 24)
        self.assertEqual(r["S1"]["n"], 4)
        self.assertAlmostEqual(r["S1"]["online_share"], 1.0)
        self.assertAlmostEqual(r["S1"]["cf"], 1.0)
        self.assertAlmostEqual(r["ALL"]["cf"], 4 / 24)
        self.assertAlmostEqual(r["R_S1_over_ALL"], 6.0)
        # shifted stamps: hour i gets demand i+1, so top 4 are hours 19-22 -> 3 online
        self.assertAlmostEqual(r["S1_shift"]["online_share"], 0.75)
        # baseline windows (2022-2024) have no demand here
        self.assertEqual(r["BASE"]["n"], 0)
        self.assertIsNone(r["S2"])

    def test_score(self):
        def m(n, on, cf, mean):
            return {"n": n, "online_hours": on, "online_share": on / n if n else None, "cf": cf, "mean_mw": mean}
        results = {
            "centralia": {"S1": m(100, 0, 0.0, 0.0)},
            "campbell": {"S1": m(100, 95, 0.7, 931.35), "ALL": m(1000, 600, 0.5, 665.0)},
            "schahfer": {"S1": m(100, 30, 0.2, 144.4), "BASE": m(300, 200, 0.5, 361.0)},
            "culley": {"S1": m(100, 50, 0.3, 27.0), "BASE": m(300, 150, 0.2, 18.0)},
            "eddystone": {"S2": m(200, 30, 0.01, 7.6)},
            "wagner": {"S2": m(100, 90, 0.5, 198.5)},
            "craig": {"unmapped": True},
            "stanton": {"S1": m(60, 60, 0.9, 400.0)},
        }
        summer = {"centralia": 670.0, "campbell": 1330.5, "schahfer": 722.0, "culley": 90.0,
                  "eddystone": 760.0, "wagner": 397.0, "craig": 427.0, "stanton": 453.4}
        s = core.score_predictions(results, summer)
        self.assertIs(s["P1"], True)    # 0% <= 5%
        self.assertIs(s["P2"], True)    # 95% >= 90%
        self.assertIs(s["P3"], True)    # 0.7 > 0.5
        self.assertIs(s["P4"], False)   # Culley 0.3 is not below 0.2
        self.assertIs(s["P5"], False)   # (30 + 90) / 300 = 40%
        # P6: S1 mean MW of centralia, campbell, schahfer, culley, stanton
        # = 0 + 931.35 + 144.4 + 27 + 400 = 1502.75 over 670 + 1330.5 + 722 + 90 + 453.4 = 3265.9
        self.assertIs(s["P6"], True)    # 0.46 < 0.5
        self.assertIsNone(s["P7"])      # Craig unmapped
        self.assertIsNone(s["P8"])      # Stanton has only 60 S1 hours
        self.assertAlmostEqual(core.fleet_cf(results, summer), 1502.75 / 3265.9)


if __name__ == "__main__":
    unittest.main(verbosity=2)
