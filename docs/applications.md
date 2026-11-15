# Who asked for each plant order? (applications-1)

Checked on 15 November 2026 by reading DOE's own page for every plant order in the table.
Predictions A1-A3 below were written on the same day, before any of the orders they are about
was issued. Made with AI agents working in MV2's name (MV2 of Munim, Inc., mv2@munimtech.com).
No person has checked the rows against the order PDFs. Data: CC BY 4.0. Code: Apache-2.0.
Information, not legal advice.

## Question

Under Federal Power Act section 202(c), DOE can issue an emergency order when a utility or grid
operator applies for one, or on its own motion. DOE posts each order on its own page, and the
documents filed on that order are listed there. For each of the 35 plant orders in
[`doe_202c_orders.csv`](../skills/doe-202c-orders/doe_202c_orders.csv) (May 2025 to
13 November 2026, 8 plants), does DOE's page list an application or request from the
recipient, the plant owner or the grid operator, dated on or before the day the order was
issued?

## Result

| Plant | Orders | With an application posted | Applicant | Days from application to order |
|---|---|---|---|---|
| H.A. Wagner (Unit 4) | 4 | 4 | PJM | 7, 14, 0, 15 |
| J.H. Campbell | 7 | 0 | | |
| Eddystone | 6 | 0 | | |
| Centralia | 4 | 0 | | |
| R.M. Schahfer | 4 | 0 | | |
| F.B. Culley | 4 | 0 | | |
| Craig | 4 | 0 | | |
| Stanton | 2 | 0 | | |
| **All** | **35** | **4** | | |

- **Wagner is the only plant whose orders DOE's pages show as requested.** PJM applied on
  21 July 2025 (order 202-25-6, issued 28 July), 10 October 2025 (202-25-6A, 24 October; the
  file names call it a "Wagner Unit 4 Renewal Request"), 21 May 2026 (202-26-25, issued the same
  day) and 4 August 2026 (202-26-25A, 19 August). The Wagner orders let PJM run Unit 4 beyond
  its environmental run-hour limits.
- **The other 31 orders, for 7 plants, list no application.** On each of those pages the only
  document dated on or before the issue date is DOE's order. Later filings are rehearing
  requests, motions to intervene and exhibits from states, consumer advocates and public
  interest groups. In some cases they come from the owners themselves: Tri-State and Platte
  River asked for rehearing of the Craig orders, and Consumers Energy asked for a limited
  clarification of 202-25-7.
- Row by row, with page links and each page's "last updated" date:
  [`data/doe_202c_applications.csv`](../data/doe_202c_applications.csv).

## How this lines up with renewal timing

[`docs/renewal-timing-plan.md`](renewal-timing-plan.md) found one gap in 27 plant renewals:
Wagner had no order from 1 January to 21 May 2026 (141 days). Put the two tables side by side
(this was looked at after the renewal-timing plan was published, so it is exploratory and does not
score anything in it):

- The 24 renewals that came with no application (7 plants) all left no day uncovered.
- Of the 3 Wagner renewals that came with a PJM application, 2 were continuous and 1 was the lapse.
- DOE's pages list no Wagner application between 10 October 2025 and 21 May 2026 (223 days). The
  2025 extension 202-25-6A ran to 31 December 2025, not for a 90-day term.

So the only chain that ever lapsed is the only chain that starts with a request. That is one
chain, so it shows how the record is built, not a rule. A reading that fits it: DOE renews the
orders it starts itself before they run out, while Wagner's relief runs only when PJM asks for it.
Nothing here shows why PJM did or did not apply.

## Predictions (applications-1), written 15 November 2026

Scored on 1 January 2027 from DOE's pages, and re-read on 8 January 2027. "Successor" means an
order that continues a plant's existing order, issued between 15 November and 31 December 2026.

- **A1 (0.9).** If DOE issues a successor to Wagner's 202-26-25A, DOE's page lists a PJM
  application dated on or before its issue date. No Wagner successor: not tested.
- **A2 (0.85).** No successor to Eddystone 202-26-40, Stanton 202-26-42, Centralia 202-26-44,
  Schahfer 202-26-46, Culley 202-26-47, Craig 202-26-49 or Campbell 202-26-51 lists an
  application from its recipient, plant owner or grid operator dated on or before its issue date.
  Held if this is true of every such successor; failed if any one lists one; not tested if
  there is none.
- **A3 (0.5).** If DOE issues a Wagner successor, its last day is 31 December 2026 (like
  202-25-6A), not a 90-day term.

These do not change the renewal-timing predictions (P1-P5), which stay as published.

## Method and limits

- One page per order, read on 15 November 2026 through a summarising web reader, which was
  asked to list every linked document with its date and submitter. Titles and dates are not
  byte-exact copies. The order PDFs were not read. An order's text may refer to a request or to
  correspondence that is not posted as a separate document.
- "No application posted" describes DOE's page, not what was sent to DOE. Applications are
  posted together with the order they lead to, so a pending request is invisible until then.
- DOE's page dates Wagner's May 2026 application 21 May. PJM's own copy is named
  `20260520-wagner-3-and-4-202c-request.pdf` and covers Units 3 and 4. Its content was not read.
- The same pages show some small defects, recorded here as seen and not otherwise checked:
  - The 202-26-22 page dates the order document 19 May 2026, but the order was issued 18 May.
  - On the Schahfer 202-26-46 page, the public interest groups' document links point to 202-26-47 addresses.
  - One exhibit link on the Eddystone 202-26-40 page and one on the Craig 202-26-49 page carry the title text instead of an address.
- Event orders (heat and cold waves) and the PREPA and Guam island orders are not covered.

## Reproduce

`python -m unittest -v test_applications` checks the table against the orders table and the
renewals table, including every count on this page.
