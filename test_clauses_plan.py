"""Checks that docs/clauses-plan.md describes what tools/clauses/ runs: id, version, the plant
orders, the clause patterns and the bars. Reads every file as text.

MV2 of Munim, Inc. (made with AI agents). Apache-2.0."""

import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))


def read(path):
    with open(os.path.join(HERE, path), encoding="utf-8") as fh:
        return fh.read()


class ClausesPlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = read("docs/clauses-plan.md")
        cls.code = read("tools/clauses/clauses.py")
        cls.tests = read("tools/clauses/test_clauses.py")

    def test_status_and_id(self):
        self.assertIn("Status: pre-registration, nothing run yet.", self.doc)
        self.assertIn("Pre-registration id: clauses-1.", self.doc)
        self.assertIn("pre-registration id clauses-1", self.code)

    def test_version(self):
        self.assertIn('VERSION = "0.1.0"', self.code)
        self.assertIn("`tools/clauses/clauses.py` 0.1.0", self.doc)

    def test_plant_orders_listed(self):
        for order in ("202-25-3", "202-25-6A", "202-26-25A", "202-26-44", "202-26-46",
                      "202-26-47", "202-26-49", "202-26-51"):
            self.assertIn('("%s", ' % order, self.code)
        self.assertIn("7 Campbell", self.doc)
        self.assertIn("2 Stanton", self.doc)

    def test_patterns_match_plan(self):
        for pat in (r"economic\s+dispatch", r"minimi[sz]e\s+(?:the\s+)?costs?",
                    r"hours\s+necessary\s+to\s+meet\s+the\s+emergency", r"capacity\s+resource"):
            self.assertIn(pat, self.code)
            self.assertIn("`%s`" % pat, self.doc)
        for year in ("2025", "2026"):
            url = "https://www.energy.gov/ceser/%s-doe-202c-orders" % year
            self.assertIn(url, self.code)
            self.assertIn(url, self.doc)
        for w in ("application", "rehearing", "motion", "exhibit", "intervene", "notice",
                  "petition", "comment", "answer", "protest", "letter", "fact-sheet", "report",
                  "complaint"):
            self.assertIn('"%s"' % w, self.code)
            self.assertIn(w, self.doc)

    def test_bars(self):
        for text in ("MIN_CHARS = 500", 'CUTOFF = "2026-09-11"', "P3_SHARE = 0.90",
                     "len(have) >= 30"):
            self.assertIn(text, self.code)
        for text in ("**Gate G1:**", "**P1 (75%):**", "**P2 (70%):**", "**P3 (70%):**",
                     "**P4 (60%):**", "at least 500", "at least 30 of the 35", "at least 90%"):
            self.assertIn(text, self.doc)
        for name in ("def test_all_hold", "def test_each_can_fail", "def test_gate_and_missing"):
            self.assertIn(name, self.tests)

    def test_licence_and_disclosure(self):
        line = "DOE's order PDFs (U.S. government works) are downloaded at run time and not stored here."
        self.assertIn(line, self.doc)
        self.assertIn(line, self.code)
        for text in (self.code, self.tests):
            self.assertIn("Apache-2.0", text)
        self.assertIn("No person has checked these results by hand.", self.doc)
        self.assertIn("Made with AI agents working in MV2's name", self.doc)


if __name__ == "__main__":
    unittest.main()
