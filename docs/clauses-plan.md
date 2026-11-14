# What do DOE's 202(c) plant orders themselves say about dispatch and costs? (plan)

Status: pre-registration, nothing run yet.
Pre-registration id: clauses-1.

Made with AI agents working in MV2's name (MV2, Munim, Inc., mv2@munimtech.com). Code
Apache-2.0, text CC BY 4.0. Information, not legal advice.
DOE's order PDFs (U.S. government works) are downloaded at run time and not stored here.

## Why

The table in this repository records the dispatch wording of two orders, Craig's 202-26-49
(25 September 2026) and Campbell's 202-26-51 (13 November 2026): both tell the grid operator to
use economic dispatch "only during the hours necessary to meet the emergency", where earlier
orders said "to minimize costs". That reading came from DOE's web summaries of each order, not
from the orders. Both orders came after the D.C. Circuit vacated Campbell's first order on
11 September 2026 (*Michigan v. DOE*, No. 25-1159). Schahfer's and Culley's orders of
18 September 2026 did not use the new words, going by their summaries; Eddystone's summary
(202-26-40, 21 August 2026) says "employ economic dispatch to minimize costs for the American
people", and the summaries for Wagner, Stanton and Centralia say nothing about dispatch.

Trackers of these orders (EDF's coal plant mandates page, POWER Magazine's order log, the Sabin
Center's litigation tracker) follow costs, dates and lawsuits. A search on 14 November 2026 found
no table of the orders' own clauses. This check reads all 35 plant orders from May 2025 to
13 November 2026 and records six clauses in each, so the change can be dated from the orders
themselves.

## Data

- DOE's lists: `https://www.energy.gov/ceser/2025-doe-202c-orders` and
  `https://www.energy.gov/ceser/2026-doe-202c-orders`, each order page they link to
  (`/ceser/federal-power-act-section-202c...`), and every document linked from an order page whose
  link or address says "order" and none of: application, rehearing, motion, exhibit, intervene,
  notice, petition, comment, answer, protest, letter, fact-sheet, report, complaint.
- Each document's order number is taken from its own text (the first "Order No. 202-.." in its
  first 2,000 characters), not from the link.
- The 35 plant orders are the `plant` rows of `doe_202c_orders.csv` 0.2.2: 7 Campbell,
  6 Eddystone, 4 each for Wagner, Centralia, Schahfer, Culley and Craig, and 2 Stanton
  (`PLANT_ORDERS` in the code).

## Method (`tools/clauses/clauses.py` 0.1.0)

Text is extracted with pypdf, words split across lines by a hyphen are joined, quotes unified
and white space collapsed. Each order is then flagged (case-insensitive):

- C1 `economic\s+dispatch`
- C2 `minimi[sz]e\s+(?:the\s+)?costs?`
- C3 `hours\s+necessary\s+to\s+meet\s+the\s+emergency` (and, separately, "only during (the) hours
  necessary")
- C4 `capacity\s+resource`
- C5 cost recovery (`cost recovery`, `recover(y|ed) (of) (the) (its) cost(s)`)
- C6 `environmental` followed by law(s), regulation(s), requirement(s) or permit(s)

with a 400-character excerpt around the first C1, C3 and C4 match.

## Gate and predictions

- **Gate G1:** text of at least 500 characters is found for at least 30 of the 35 plant orders.
  If G1 fails, the predictions are reported as not graded and the table as incomplete.
- **P1 (75%):** C3 appears in 202-26-49 and 202-26-51 and in no plant order issued before
  11 September 2026 (30 orders).
- **P2 (70%):** C3 does not appear in 202-26-46 (Schahfer) or 202-26-47 (Culley), both issued
  18 September 2026.
- **P3 (70%):** C1 appears in at least 90% of the plant orders with text.
- **P4 (60%):** C4 appears in 202-26-51 (a news summary said Campbell "shall not be considered a
  capacity resource"; DOE's page for the order does not say so).

Each prediction is graded only if both of its orders have text; otherwise it is reported as not
graded with the reason.

## Outputs

`clauses.csv` (one row per plant order with text: order, plant, issue date, pages, characters,
the six flags, "only during", the document address) and `clauses.json` (the same with excerpts,
the grades, the orders not found, every other document read and the crawl log).

## Limits

Six regular expressions are not a legal reading: a flag says the words are there, not what they
do, and an order can say the same thing in other words. Scanned pages without a text layer would
show as missing. A document posted as an order but carrying another order's number first would be
counted under that number; such cases are listed in `clauses.json`. Nothing here says whether any
order is lawful. No person has checked these results by hand.
