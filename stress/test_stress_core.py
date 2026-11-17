# SPDX-License-Identifier: Apache-2.0
"""Tests for stress_core (pre-registration stress-1). Standard library only.
Every expected value was worked out by hand from the inputs written here."""
import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stress_core as core  # noqa: E402

UTC = dt.timezone.utc
D = dt.date


def H(y, m, d, h=0):
    return dt.datetime(y, m, d, h, tzinfo=UTC)


class TestBasics(unittest.TestCase):
    def test_month_after(self):
        self.assertEqual(core.month_after(D(2023, 12, 1)), H(2024, 1, 1))
        self.assertEqual(core.month_after(D(2023, 5, 15)), H(2023, 6, 1))

    def test_as_date(self):
        self.assertEqual(core.as_date("2025-06-01"), D(2025, 6, 1))
        self.assertEqual(core.as_date(dt.datetime(2024, 1, 1, 5)), D(2024, 1, 1))
        self.assertIsNone(core.as_date(None))
        self.assertIsNone(core.as_date("NaT"))

    def test_is_existing(self):
        self.assertTrue(core.is_existing("existing", None))
        self.assertFalse(core.is_existing("retired", "OP"))
        self.assertTrue(core.is_existing(None, "OP"))
        self.assertFalse(core.is_existing("", "RE"))

    def test_year_bounds(self):
        self.assertEqual(core.year_bounds(2026, core.STUDY_START, H(2026, 10, 1)),
                         (H(2026, 1, 1), H(2026, 10, 1)))

    def test_snapshot_year(self):
        av = {2020, 2021, 2023}
        self.assertEqual(core.snapshot_year(av, 2022), 2021)
        self.assertEqual(core.snapshot_year(av, 2024), 2023)
        self.assertEqual(core.snapshot_year(av, 2025), 2023)
        self.assertIsNone(core.snapshot_year({2021}, 2021))


class TestHours(unittest.TestCase):
    def setUp(self):
        self.d = {H(2022, 12, 31, 23): 10.0, H(2023, 1, 1, 0): 20.0,
                  H(2023, 1, 1, 1): 15.0, H(2023, 6, 1, 0): 30.0}

    def test_top_k_ties(self):
        h = [H(2026, 7, 1, i) for i in range(5)]
        d = {h[0]: 5.0, h[1]: 7.0, h[2]: 7.0, h[3]: 1.0, h[4]: None}
        self.assertEqual(core.top_k(d, h[0], H(2026, 7, 2), 2), [h[1], h[2]])
        self.assertEqual(core.top_k(d, h[0], H(2026, 7, 2), 10), [h[1], h[2], h[0], h[3]])

    def test_stress_sets_clip(self):
        s = core.stress_sets({"X": self.d}, (2022, 2023), H(2022, 1, 1), H(2023, 6, 1), 2)
        self.assertEqual(s[("X", 2022)], [H(2022, 12, 31, 23)])
        # 1 June 00:00 is at the coverage end, so it is excluded
        self.assertEqual(s[("X", 2023)], [H(2023, 1, 1, 0), H(2023, 1, 1, 1)])
        self.assertEqual(core.truncate_sets(s, 1)[("X", 2023)], [H(2023, 1, 1, 0)])

    def test_window_and_shift(self):
        w = core.window_sets({"X": self.d}, (H(2023, 1, 1), H(2023, 1, 2)), H(2023, 1, 1, 1), 5, 2023)
        self.assertEqual(w, {("X", 2023): [H(2023, 1, 1, 0)]})
        self.assertEqual(core.shift_demand({H(2023, 1, 1, 1): 5.0}), {H(2023, 1, 1, 0): 5.0})

    def test_in_service_hours(self):
        lo, hi = H(2022, 1, 1), H(2026, 10, 1)
        self.assertEqual(core.in_service_hours(2022, lo, hi, None), 8760)
        self.assertEqual(core.in_service_hours(2024, lo, hi, None), 8784)
        # 1 Jan - 30 Sep 2026: 273 days
        self.assertEqual(core.in_service_hours(2026, lo, hi, None), 273 * 24)
        self.assertEqual(core.in_service_hours(2022, lo, hi, H(2022, 3, 1)), 59 * 24)
        self.assertEqual(core.in_service_hours(2023, lo, hi, H(2022, 3, 1)), 0)


class TestClassify(unittest.TestCase):
    def setUp(self):
        self.snap = {
            "1": {"status": "existing", "code": "OP", "esc": "SUB", "cap": 300.0, "planned": D(2025, 6, 1)},
            "2": {"status": "existing", "code": "OP", "esc": "BIT", "cap": 200.0, "planned": None},
            "3": {"status": "retired", "code": "RE", "esc": "NG", "cap": 50.0, "planned": None},
            "4": {"status": "existing", "code": "OP", "esc": "NG", "cap": 80.0, "planned": None},
            "5": {"status": "existing", "code": "OP", "esc": "BIT", "cap": 150.0, "planned": D(2021, 5, 1)},
        }

    def test_groups(self):
        s = self.snap
        self.assertEqual(core.classify({"1"}, s, 2022), ("R", 300.0, ["1"]))
        # in 2019 the horizon ends 31 Dec 2023, before the planned date
        self.assertEqual(core.classify({"1"}, s, 2019), ("C", 300.0, ["1"]))
        self.assertEqual(core.classify({"1", "2"}, s, 2022), ("MIXED", 500.0, ["1", "2"]))
        self.assertEqual(core.classify({"2"}, s, 2022), ("C", 200.0, ["2"]))
        # generator 3 is retired in the snapshot, so it does not count
        self.assertEqual(core.classify({"1", "3"}, s, 2022), ("R", 300.0, ["1"]))
        self.assertEqual(core.classify({"2", "4"}, s, 2022), ("NOTCOAL", 0.0, ["2", "4"]))
        self.assertEqual(core.classify({"9"}, s, 2022), (None, 0.0, []))
        # a planned date already past still counts as scheduled to retire
        self.assertEqual(core.classify({"5"}, s, 2022), ("R", 150.0, ["5"]))
        self.assertEqual(core.classify({"1", "5"}, s, 2022), ("R", 450.0, ["1", "5"]))

    def test_retire_end(self):
        r = {"1": D(2023, 12, 1), "2": D(2023, 3, 1)}
        self.assertEqual(core.retire_end(["1", "2"], r), H(2024, 1, 1))
        self.assertIsNone(core.retire_end(["1", "7"], r))
        self.assertIsNone(core.retire_end([], r))


class TestCollectAndScore(unittest.TestCase):
    def setUp(self):
        h = [H(2022, 7, 15, 10 + i) for i in range(4)]
        self.h = h
        sets = {("X", 2022): h}
        subyears = [
            {"key": ("p1", 1), "y": 2022, "group": "R", "cap": 100.0, "ba": "X", "rend": None},
            {"key": ("p2", 1), "y": 2022, "group": "C", "cap": 300.0, "ba": "X", "rend": H(2022, 7, 15, 12)},
            {"key": ("p3", 1), "y": 2022, "group": "MIXED", "cap": 50.0, "ba": "X", "rend": None},
        ]
        sub_load = {("p1", 1): {h[0]: 100.0, h[1]: 0.0, h[2]: 50.0},
                    ("p2", 1): {h[0]: 300.0, h[1]: 150.0, h[2]: 300.0},
                    ("p3", 1): {h[3]: 10.0}}
        # p2 is in service 1 Jan - 15 Jul 12:00 = 195 days + 12 h = 4692 h
        ann = {("p1", 1): {2022: 219000.0}, ("p2", 1): {2022: 703800.0}}
        self.cl = core.collect(subyears, sets, sub_load, ann, H(2022, 1, 1), H(2026, 10, 1))

    def test_collect(self):
        p1 = self.cl[(("p1", 1), "R")]
        self.assertEqual(p1["n"], 4)
        self.assertAlmostEqual(p1["w_n"], 400.0)
        self.assertAlmostEqual(p1["w_on"], 200.0)
        self.assertAlmostEqual(p1["load"], 150.0)
        self.assertAlmostEqual(p1["ann_caph"], 876000.0)
        p2 = self.cl[(("p2", 1), "C")]
        self.assertEqual(p2["n"], 2)   # hours 12 and 13 are at or after retirement
        self.assertAlmostEqual(p2["ann_caph"], 300.0 * 4692)

    def test_stats(self):
        r = core.group_stats(self.cl, "R")
        c = core.group_stats(self.cl, "C")
        self.assertEqual((r["clusters"], r["pairs"]), (1, 4))
        self.assertAlmostEqual(r["A"], 0.5)
        self.assertAlmostEqual(r["SCF"], 0.375)
        self.assertAlmostEqual(r["ACF"], 0.25)
        self.assertAlmostEqual(r["lift"], 1.5)
        self.assertAlmostEqual(c["A"], 1.0)
        self.assertAlmostEqual(c["SCF"], 0.75)
        self.assertAlmostEqual(c["ACF"], 0.5)
        self.assertAlmostEqual(c["lift"], 1.5)
        m = core.group_stats(self.cl, "MIXED")
        self.assertEqual(m["pairs"], 4)
        self.assertAlmostEqual(m["A"], 0.25)
        self.assertIsNone(m["lift"])   # no annual data for p3
        gap, nba = core.ba_matched(self.cl)
        self.assertAlmostEqual(gap, -0.5)
        self.assertEqual(nba, 1)
        ci = core.boot_ci(self.cl, "A", b=50)
        self.assertAlmostEqual(ci[0], -0.5)
        self.assertAlmostEqual(ci[1], -0.5)
        self.assertAlmostEqual(core.boot_ci(self.cl, "SCF", b=50)[0], -0.375)

    def test_score(self):
        main = {"R": core.group_stats(self.cl, "R"), "C": core.group_stats(self.cl, "C")}
        s = core.score(main, -0.5, {"R": {"A": 0.2}, "C": {"A": 0.9}}, [-0.5, -0.5])
        self.assertEqual(s, {"S1": True, "S2": True, "S3": True, "S4": False,
                             "S5": True, "S6": True, "S7": True, "S8": True})
        main2 = {"R": {"A": 0.85, "SCF": 0.6, "lift": None},
                 "C": {"A": 0.9, "SCF": 0.5, "lift": 1.2}}
        s2 = core.score(main2, 0.01, None, [-0.1, 0.02])
        self.assertEqual(s2, {"S1": True, "S2": False, "S3": False, "S4": None,
                              "S5": False, "S6": None, "S7": True, "S8": False})

    def test_bootstrap_bounds(self):
        cl = {(("a", 1), "R"): {"ba": "X", "n": 1, "w_n": 100.0, "w_on": 100.0, "load": 0.0},
              (("b", 1), "R"): {"ba": "X", "n": 1, "w_n": 100.0, "w_on": 0.0, "load": 0.0},
              (("c", 1), "C"): {"ba": "X", "n": 1, "w_n": 100.0, "w_on": 100.0, "load": 0.0}}
        lo, hi = core.boot_ci(cl, "A", b=200)
        # R resamples give 0, 0.5 or 1; C is always 1
        self.assertTrue(-1.0 <= lo <= hi <= 0.0)
        self.assertEqual(core.boot_ci(cl, "A", b=200), [lo, hi])   # same seed, same answer


if __name__ == "__main__":
    unittest.main(verbosity=2)
