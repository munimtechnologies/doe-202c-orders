# Unit tests for clauses.py (pre-registration id clauses-1). No network, no pypdf needed.
# MV2 of Munim, Inc. (made with AI agents). Apache-2.0.
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clauses as c  # noqa: E402


def row(issued, c1=True, c3=False, c4=False, chars=5000):
    return {"issued": issued, "chars": chars, "C1_economic_dispatch": c1,
            "C3_hours_necessary": c3, "C4_capacity_resource": c4}


def full_rows():
    rows = {}
    for o, _, d in c.PLANT_ORDERS:
        rows[c.canon(o)] = row(d)
    rows[c.canon("202-26-49")]["C3_hours_necessary"] = True
    rows[c.canon("202-26-51")]["C3_hours_necessary"] = True
    rows[c.canon("202-26-51")]["C4_capacity_resource"] = True
    return rows


class CanonTests(unittest.TestCase):
    def test_dashes_spaces_padding_suffix(self):
        self.assertEqual(c.canon("202–26–31"), "202-26-31")
        self.assertEqual(c.canon("202 - 25 - 06a"), "202-25-6A")
        self.assertEqual(c.canon("202-26-01"), "202-26-1")
        self.assertEqual(c.canon("202-26-25A"), "202-26-25A")

    def test_plant_orders(self):
        self.assertEqual(len(c.PLANT_ORDERS), 35)
        self.assertEqual(len(c.PLANT_INDEX), 35)
        keys = {k for _, k, _ in c.PLANT_ORDERS}
        self.assertEqual(keys, {"campbell", "eddystone", "wagner", "centralia", "schahfer",
                                "culley", "craig", "stanton"})
        self.assertEqual(sum(1 for _, k, _ in c.PLANT_ORDERS if k == "campbell"), 7)
        for o, _, d in c.PLANT_ORDERS:
            self.assertRegex(d, r"^20(25|26)-\d\d-\d\d$")
            self.assertTrue(o.startswith("202-" + d[2:4] + "-") or o == "202-25-6A")


class TextTests(unittest.TestCase):
    def test_find_order_no(self):
        t = "Department of Energy\nWashington, DC 20585\nOrder No. 202–26–51\nPursuant to"
        self.assertEqual(c.find_order_no(t), "202-26-51")
        self.assertEqual(c.find_order_no("Order No. 202-26-25A\nx"), "202-26-25A")
        self.assertEqual(c.find_order_no("Order No. 202-26-40 PJM Interconnection"), "202-26-40")
        self.assertIsNone(c.find_order_no("no order number here"))

    def test_normalize_joins_hyphenated_words_only(self):
        self.assertEqual(c.normalize("eco-\nnomic   dispatch"), "economic dispatch")
        self.assertEqual(c.normalize("202-26-\n51"), "202-26- 51")
        self.assertEqual(c.normalize("“quoted”"), '"quoted"')

    def test_classify(self):
        t = ("MISO shall take every step to employ economic dis-\npatch of the Campbell Plant only during "
             "the hours necessary to meet the emergency and to minimize costs. The plant shall not be "
             "considered a capacity resource. Consumers may seek cost recovery. Environmental laws apply.")
        f, s = c.classify(t)
        for k in ("C1_economic_dispatch", "C2_minimize_costs", "C3_hours_necessary",
                  "C4_capacity_resource", "C5_cost_recovery", "C6_environmental", "C3_only_during"):
            self.assertTrue(f[k], k)
        self.assertIn("C3_hours_necessary", s)
        f2, _ = c.classify("employ economic dispatch of the Plant to minimize costs to ratepayers")
        self.assertTrue(f2["C1_economic_dispatch"] and f2["C2_minimize_costs"])
        self.assertFalse(f2["C3_hours_necessary"] or f2["C3_only_during"] or f2["C4_capacity_resource"])


class LinkTests(unittest.TestCase):
    PAGE = ('<p><a href="/ceser/federal-power-act-section-202c-craig-order-no-202-26-49-0">Sep 25</a>'
            '<a href="https://www.energy.gov/ceser/federal-power-act-section-202c-craig-order-no-202-26-49-0#x">'
            'again</a><a href="/ceser/2025-doe-202c-orders">2025</a>'
            '<a href="/documents/doe-order-no-202-26-40"><span>DOE 202(c) Order No. 202-26-40 PJM</span></a>'
            '<a href="/documents/pjms-202c-renewal-application">PJM renewal application</a>'
            '<a href="/documents/202-26-40a-notice-denial-rehearing-operation-law">Order 202-26-40A notice</a>'
            '<a href="https://example.com/order.pdf">order elsewhere</a></p>')

    def test_extract_and_filter(self):
        links = c.extract_links(self.PAGE)
        self.assertEqual(len(links), 7)
        pages = c.order_pages(links)
        self.assertEqual(pages, ["https://www.energy.gov/ceser/federal-power-act-section-202c-craig-order-no-202-26-49-0"])
        docs = [u for u, t in links if c.is_order_doc(u, t)]
        self.assertEqual(docs, ["https://www.energy.gov/documents/doe-order-no-202-26-40"])
        self.assertEqual(links[3][1], "DOE 202(c) Order No. 202-26-40 PJM")


class GradeTests(unittest.TestCase):
    def test_all_hold(self):
        g = c.grade(full_rows())
        self.assertTrue(g["G1"]["held"])
        self.assertEqual(g["G1"]["orders_with_text"], 35)
        for k in ("P1", "P2", "P3", "P4"):
            self.assertIs(g[k]["held"], True, k)
        self.assertEqual(g["P1"]["checked_before_cutoff"], 30)

    def test_each_can_fail(self):
        r = full_rows()
        r[c.canon("202-26-16")]["C3_hours_necessary"] = True
        self.assertFalse(c.grade(r)["P1"]["held"])
        r = full_rows()
        r[c.canon("202-26-46")]["C3_hours_necessary"] = True
        self.assertFalse(c.grade(r)["P2"]["held"])
        r = full_rows()
        for o in ("202-25-3", "202-25-4", "202-25-6", "202-25-7"):
            r[c.canon(o)]["C1_economic_dispatch"] = False
        g = c.grade(r)
        self.assertFalse(g["P3"]["held"])
        self.assertEqual(g["P3"]["with_c1"], 31)
        r = full_rows()
        r[c.canon("202-26-51")]["C4_capacity_resource"] = False
        self.assertFalse(c.grade(r)["P4"]["held"])

    def test_gate_and_missing(self):
        r = full_rows()
        for o, _, _ in c.PLANT_ORDERS[:6]:
            r[c.canon(o)]["chars"] = 10
        g = c.grade(r)
        self.assertFalse(g["G1"]["held"])
        self.assertEqual(g["G1"]["orders_with_text"], 29)
        self.assertFalse(g["P1"]["graded"])
        r = full_rows()
        del r[c.canon("202-26-49")]
        self.assertIsNone(c.grade(r)["P1"]["held"])


if __name__ == "__main__":
    unittest.main()
