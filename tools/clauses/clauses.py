# clauses.py - what do DOE's 202(c) plant orders themselves say about dispatch and costs?
# pre-registration id clauses-1 (plan: docs/clauses-plan.md in munimtechnologies/doe-202c-orders).
# By MV2 of Munim, Inc. (mv2@munimtech.com). Made with AI agents working in MV2's name.
# Apache-2.0. DOE's order PDFs (U.S. government works) are downloaded at run time and not stored here.
#
# The doe-202c-orders table records the dispatch wording of two orders from DOE's web summaries.
# This script reads the orders themselves: it walks DOE's 2025 and 2026 202(c) list pages to each
# order page, downloads every linked document that looks like an order, takes the order number
# from the PDF's own text, and flags six clauses in each of the 35 plant orders. It only measures.
import argparse
import html
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

VERSION = "0.1.0"
UA = {"User-Agent": "Mozilla/5.0 (compatible; MV2-Munim-Inc-clauses/0.1.0; mailto:mv2@munimtech.com)"}
BASE = "https://www.energy.gov"
YEAR_PAGES = ["https://www.energy.gov/ceser/2025-doe-202c-orders",
              "https://www.energy.gov/ceser/2026-doe-202c-orders"]
ORDER_PAGE_PREFIX = "/ceser/federal-power-act-section-202c"
SKIP_WORDS = ("application", "rehearing", "motion", "exhibit", "intervene", "notice", "petition",
              "comment", "answer", "protest", "letter", "fact-sheet", "report", "complaint")
MAX_DOCS = 150
PAUSE = 1.5
MIN_CHARS = 500
CUTOFF = "2026-09-11"  # the D.C. Circuit's ruling in Michigan v. DOE, No. 25-1159
P3_SHARE = 0.90

# The 35 plant orders in doe_202c_orders.csv 0.2.2: (order, plant_key, issued).
PLANT_ORDERS = [
    ("202-25-3", "campbell", "2025-05-23"), ("202-25-4", "eddystone", "2025-05-30"),
    ("202-25-6", "wagner", "2025-07-28"), ("202-25-7", "campbell", "2025-08-20"),
    ("202-25-8", "eddystone", "2025-08-28"), ("202-25-6A", "wagner", "2025-10-24"),
    ("202-25-9", "campbell", "2025-11-18"), ("202-25-10", "eddystone", "2025-11-25"),
    ("202-25-11", "centralia", "2025-12-16"), ("202-25-12", "schahfer", "2025-12-23"),
    ("202-25-13", "culley", "2025-12-23"), ("202-25-14", "craig", "2025-12-30"),
    ("202-26-16", "campbell", "2026-02-17"), ("202-26-17", "eddystone", "2026-02-23"),
    ("202-26-18", "centralia", "2026-03-16"), ("202-26-19", "schahfer", "2026-03-23"),
    ("202-26-20", "culley", "2026-03-23"), ("202-26-21", "craig", "2026-03-30"),
    ("202-26-22", "campbell", "2026-05-18"), ("202-26-24", "eddystone", "2026-05-21"),
    ("202-26-25", "wagner", "2026-05-21"), ("202-26-26", "stanton", "2026-06-04"),
    ("202-26-28", "centralia", "2026-06-12"), ("202-26-29", "schahfer", "2026-06-18"),
    ("202-26-30", "culley", "2026-06-18"), ("202-26-31", "craig", "2026-06-26"),
    ("202-26-39", "campbell", "2026-08-14"), ("202-26-25A", "wagner", "2026-08-19"),
    ("202-26-40", "eddystone", "2026-08-21"), ("202-26-42", "stanton", "2026-09-01"),
    ("202-26-44", "centralia", "2026-09-11"), ("202-26-46", "schahfer", "2026-09-18"),
    ("202-26-47", "culley", "2026-09-18"), ("202-26-49", "craig", "2026-09-25"),
    ("202-26-51", "campbell", "2026-11-13"),
]

CLAUSES = {
    "C1_economic_dispatch": r"economic\s+dispatch",
    "C2_minimize_costs": r"minimi[sz]e\s+(?:the\s+)?costs?",
    "C3_hours_necessary": r"hours\s+necessary\s+to\s+meet\s+the\s+emergency",
    "C4_capacity_resource": r"capacity\s+resource",
    "C5_cost_recovery": r"cost\s+recovery|recover(?:y|ed)?\s+(?:of\s+)?(?:the\s+)?(?:its\s+)?costs?",
    "C6_environmental": r"environmental\s+(?:law|laws|regulation|regulations|requirement|requirements|permit|permits)",
}
SNIPPET = ("C1_economic_dispatch", "C3_hours_necessary", "C4_capacity_resource")

DASHES = "‐‑‒–—−"
ORDER_RE = re.compile(r"Order\s+No\.?\s*(202\s*[-%s]\s*2[56]\s*[-%s]\s*\d{1,2}[A-Z]?)\b" % (DASHES, DASHES))
LINK_RE = re.compile(r"<a\s[^>]*?href\s*=\s*\"([^\"]+)\"[^>]*>(.*?)</a>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def canon(order):
    """'202–26–031' -> '202-26-31', '202-25-6a' -> '202-25-6A'."""
    s = order
    for d in DASHES:
        s = s.replace(d, "-")
    s = re.sub(r"\s+", "", s).upper()
    parts = s.split("-")
    if len(parts) != 3:
        return s
    m = re.match(r"^(\d+)([A-Z]?)$", parts[2])
    if not m:
        return s
    return "%s-%s-%d%s" % (parts[0], parts[1], int(m.group(1)), m.group(2))


PLANT_INDEX = {canon(o): (o, k, d) for o, k, d in PLANT_ORDERS}


def normalize(text):
    """Join words split across lines by a hyphen, unify quotes and collapse white space."""
    text = re.sub(r"([a-z])-[ \t]*\n\s*([a-z])", r"\1\2", text)
    text = text.replace("“", '"').replace("”", '"').replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", text).strip()


def find_order_no(text, head=2000):
    m = ORDER_RE.search(normalize(text[: head * 2])[:head])
    return canon(m.group(1)) if m else None


def classify(text):
    t = normalize(text)
    flags, snippets = {}, {}
    for name, pat in CLAUSES.items():
        m = re.search(pat, t, re.I)
        flags[name] = bool(m)
        if m and name in SNIPPET:
            snippets[name] = t[max(0, m.start() - 200): m.end() + 200]
    m = re.search(r"only\s+during\s+(?:the\s+)?hours\s+necessary", t, re.I)
    flags["C3_only_during"] = bool(m)
    return flags, snippets


def extract_links(page_html, base=BASE):
    out = []
    for href, inner in LINK_RE.findall(page_html):
        text = html.unescape(TAG_RE.sub(" ", inner))
        text = re.sub(r"\s+", " ", text).strip()
        url = urllib.parse.urljoin(base + "/", html.unescape(href).strip())
        out.append((url.split("#")[0], text))
    return out


def order_pages(links):
    seen, out = set(), []
    for url, _ in links:
        path = urllib.parse.urlparse(url).path
        if urllib.parse.urlparse(url).netloc.endswith("energy.gov") and path.startswith(ORDER_PAGE_PREFIX):
            if url not in seen:
                seen.add(url)
                out.append(url)
    return out


def is_order_doc(url, text):
    p = urllib.parse.urlparse(url)
    if not p.netloc.endswith("energy.gov"):
        return False
    if not (p.path.startswith("/documents/") or p.path.lower().endswith(".pdf")):
        return False
    hay = (p.path + " " + text).lower()
    if "order" not in hay:
        return False
    return not any(w in hay for w in SKIP_WORDS)


def fetch(url, timeout=120):
    last = None
    for _ in range(3):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read(), resp.geturl(), resp.headers.get("Content-Type", "")
        except Exception as exc:  # retried, then raised
            last = exc
            time.sleep(10)
    raise last


def wait_for(url, token, minutes):
    deadline = time.time() + minutes * 60
    polls = 0
    while True:
        polls += 1
        try:
            if token in fetch(url, 60)[0].decode("utf-8", "replace"):
                return True, polls, now()
        except Exception:
            pass
        if time.time() > deadline:
            return False, polls, now()
        time.sleep(60)


def pdf_text(data):
    from pypdf import PdfReader  # only needed in the job, not in the unit tests
    reader = PdfReader(io.BytesIO(data))
    return len(reader.pages), "\n".join((pg.extract_text() or "") for pg in reader.pages)


def grade(rows):
    """rows: {canon order: {"issued": str, "chars": int, flags...}} for plant orders with text."""
    have = {o: r for o, r in rows.items() if r.get("chars", 0) >= MIN_CHARS}
    g1 = len(have) >= 30
    k49, k51, k46, k47 = canon("202-26-49"), canon("202-26-51"), canon("202-26-46"), canon("202-26-47")

    def c3(o):
        return have[o]["C3_hours_necessary"]

    res = {"G1": {"held": g1, "orders_with_text": len(have), "of": len(PLANT_ORDERS)}}
    if k49 in have and k51 in have:
        before = [o for o, r in have.items() if r["issued"] < CUTOFF]
        hits_before = sorted(o for o in before if c3(o))
        res["P1"] = {"held": c3(k49) and c3(k51) and not hits_before,
                     "c3_49": c3(k49), "c3_51": c3(k51), "c3_before_cutoff": hits_before,
                     "checked_before_cutoff": len(before)}
    else:
        res["P1"] = {"held": None, "why": "202-26-49 or 202-26-51 has no text"}
    if k46 in have and k47 in have:
        res["P2"] = {"held": (not c3(k46)) and (not c3(k47)), "c3_46": c3(k46), "c3_47": c3(k47)}
    else:
        res["P2"] = {"held": None, "why": "202-26-46 or 202-26-47 has no text"}
    if have:
        n1 = sum(1 for r in have.values() if r["C1_economic_dispatch"])
        res["P3"] = {"held": n1 / len(have) >= P3_SHARE, "with_c1": n1, "of": len(have),
                     "without_c1": sorted(o for o, r in have.items() if not r["C1_economic_dispatch"])}
    else:
        res["P3"] = {"held": None, "why": "no text"}
    if k51 in have:
        res["P4"] = {"held": have[k51]["C4_capacity_resource"]}
    else:
        res["P4"] = {"held": None, "why": "202-26-51 has no text"}
    if not g1:
        for k in ("P1", "P2", "P3", "P4"):
            res[k]["graded"] = False
    return res


def crawl(log):
    links = []
    for url in YEAR_PAGES:
        try:
            body, final, ctype = fetch(url)
            got = extract_links(body.decode("utf-8", "replace"))
            log.append({"url": url, "ok": True, "links": len(got)})
            links.extend(got)
        except Exception as exc:
            log.append({"url": url, "ok": False, "error": repr(exc)[:300]})
        time.sleep(PAUSE)
    docs, seen = [], set()
    for page in order_pages(links):
        try:
            body, final, ctype = fetch(page)
            got = extract_links(body.decode("utf-8", "replace"))
            cand = [(u, t) for u, t in got if is_order_doc(u, t)]
            log.append({"url": page, "ok": True, "docs": len(cand)})
            for u, t in cand:
                if u not in seen:
                    seen.add(u)
                    docs.append({"url": u, "link_text": t, "page": page})
        except Exception as exc:
            log.append({"url": page, "ok": False, "error": repr(exc)[:300]})
        time.sleep(PAUSE)
    return docs[:MAX_DOCS]


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--wait-for", default="")
    ap.add_argument("--token", default="")
    ap.add_argument("--minutes", type=float, default=240)
    a = ap.parse_args(argv)
    os.makedirs(a.out_dir, exist_ok=True)
    meta = {"version": VERSION, "started": now()}
    if a.wait_for:
        ok, polls, at = wait_for(a.wait_for, a.token, a.minutes)
        meta["plan"] = {"url": a.wait_for, "token": a.token, "found": ok, "polls": polls, "at": at}
        if not ok:
            meta["stopped"] = "plan not live"
            with open(os.path.join(a.out_dir, "clauses.json"), "w", encoding="utf-8") as fh:
                json.dump(meta, fh, indent=1)
            print("plan not live; stopping")
            return 2
    log = []
    docs = crawl(log)
    meta["pages_ok"] = sum(1 for x in log if x["ok"])
    meta["pages_failed"] = sum(1 for x in log if not x["ok"])
    meta["candidate_docs"] = len(docs)
    found, others = {}, []
    for d in docs:
        rec = {"url": d["url"], "link_text": d["link_text"], "page": d["page"]}
        try:
            data, final, ctype = fetch(d["url"])
            rec["final_url"] = final
            if not data.startswith(b"%PDF-"):
                m = re.search(r"href=\"([^\"]+\.pdf)\"", data.decode("utf-8", "replace"), re.I)
                if m:
                    pdf_url = urllib.parse.urljoin(final, html.unescape(m.group(1)))
                    data, final, ctype = fetch(pdf_url)
                    rec["final_url"] = final
            if not data.startswith(b"%PDF-"):
                rec["error"] = "not a PDF (%s)" % ctype
                others.append(rec)
                continue
            pages, text = pdf_text(data)
            rec.update({"pages": pages, "chars": len(normalize(text)), "bytes": len(data)})
            rec["order"] = find_order_no(text)
            if rec["order"] in PLANT_INDEX and rec["order"] not in found:
                order, plant, issued = PLANT_INDEX[rec["order"]]
                flags, snips = classify(text)
                rec.update({"plant_key": plant, "issued": issued}, **flags)
                rec["snippets"] = snips
                found[rec["order"]] = rec
            else:
                rec["duplicate"] = rec["order"] in found
                others.append(rec)
        except Exception as exc:
            rec["error"] = repr(exc)[:300]
            others.append(rec)
        time.sleep(PAUSE)
    meta["missing_orders"] = [o for o, _, _ in PLANT_ORDERS if canon(o) not in found]
    meta["grades"] = grade(found)
    meta["finished"] = now()
    cols = ["order", "plant_key", "issued", "pages", "chars"] + list(CLAUSES) + ["C3_only_during", "url"]
    with open(os.path.join(a.out_dir, "clauses.csv"), "w", encoding="utf-8", newline="") as fh:
        fh.write(",".join(cols) + "\n")
        for o, _, _ in PLANT_ORDERS:
            r = found.get(canon(o))
            if not r:
                continue
            fh.write(",".join(str(r.get(c, "")).replace(",", ";") for c in cols) + "\n")
    with open(os.path.join(a.out_dir, "clauses.json"), "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "orders": found, "other_docs": others, "crawl": log}, fh, indent=1)
    print(json.dumps({"found": len(found), "missing": meta["missing_orders"], "grades": meta["grades"]}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
