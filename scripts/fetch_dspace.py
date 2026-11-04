"""Nieuwe publicaties toevoegen uit de UU-repository (DSpace).

Pure (research-portal.uu.nl) zit achter een botcheck, maar de UU-repository
neemt de metadata uit Pure over, inclusief keywords en abstract, en is wel
bereikbaar voor scripts. Bestaande publicaties in publications.json blijven
ongemoeid; dit script voegt alleen toe wat er nog niet in staat.

Gebruik:
  python scripts/fetch_dspace.py             # nieuwe publicaties toevoegen
  python scripts/fetch_dspace.py --dry-run   # alleen tonen wat erbij zou komen
  python scripts/fetch_dspace.py --compare   # keywords vergelijken met publications.json
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date

from fetch_pure import normalize_authors

UA = ("Mozilla/5.0 (compatible; irisbeerepoot-site/1.0; "
      "+https://github.com/ibeerepoot/ibeerepoot.github.io)")
SITE = "https://dspace.library.uu.nl"
BASE = SITE + "/server"
FEED = BASE + "/opensearch/search?" + urllib.parse.urlencode({
    "format": "atom", "scope": "1894baf6-d89f-4073-9b4b-4c89b978e011",
    "sort": "dc.date.accessioned", "sort_direction": "DESC",
    "query": "dc.contributor.author:Beerepoot, Iris", "configuration": "community", "rpp": 100})

# De repository mengt Pure's auteurskeywords met termen die geen keywords zijn:
# de open-accessregeling, Scopus-vakcategorieen (ASJC), arXiv-categorieen en SDG's.
# Een term die ook in de eigen keywords op de site voorkomt, blijft altijd staan.
NOISE = {
    "taverne",
    # Scopus ASJC-categorieen, zoals waargenomen in de repository
    "information systems", "information systems and management", "general computer science",
    "modelling and simulation", "control and systems engineering",
    "business and international management", "management information systems",
    "theoretical computer science", "artificial intelligence", "general engineering",
    "software", "computer science applications", "health informatics", "signal processing",
    "computer vision and pattern recognition", "computer graphics and computer-aided design",
    "hardware and architecture", "computer networks and communications",
    "business, management and accounting (miscellaneous)", "communication",
}
NOISE_PATTERN = re.compile(r"^(sdg \d+\b.*|(cs|econ|eess|math|q-bio|q-fin|stat)\.[a-z]{2})$", re.I)

# dc.type.content -> Pure-type zoals de site (app.js, TYPE) die kent
TYPE_MAP = {
    "part of book": "Chapter in Book/Report/Conference proceeding",
    "article": "Contribution to journal",
    "editorial": "Contribution to journal",
    "contribution to conference": "Contribution to conference",
    "report": "Book/Report",
    "book": "Book/Report",
    "dissertation": "Thesis",
}


def pure_type(raw):
    low = (raw or "").lower()
    if low in TYPE_MAP:
        return TYPE_MAP[low]
    if "/workingpaper/" in low:
        return "Working paper"
    if "/contributiontojournal/" in low:
        return "Contribution to journal"
    if "/contributiontobookanthology/" in low:
        return "Chapter in Book/Report/Conference proceeding"
    if "/contributiontoconference/" in low:
        return "Contribution to conference"
    return raw or None


def get(url, accept="*/*", attempt=1):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        if attempt <= 3:
            time.sleep(3 * attempt)
            return get(url, accept, attempt + 1)
        print(f"    {url}: {e}")
        return None


def handles():
    body = get(FEED)
    if body is None:
        return None
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", body, re.S):
        m = re.search(r"<id>https://dspace\.library\.uu\.nl/handle/(\d+/\d+)</id>", entry)
        if m and m.group(1) not in out:
            out.append(m.group(1))
    return out


def metadata(handle):
    js = get(f"{BASE}/api/pid/find?id=hdl:{handle}", "application/json")
    if not js:
        return None
    md = json.loads(js).get("metadata", {})
    return {k: [x["value"] for x in v] for k, v in md.items()}


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def bare_doi(d):
    return re.sub(r"^https?://(dx\.)?doi\.org/", "", d or "").lower() or None


def first(md, key):
    v = md.get(key)
    return v[0] if v else None


def split_keywords(values):
    out = []
    for v in values:
        # Soms staat een hele lijst als een waarde, met komma's gescheiden
        parts = v.split(",") if v.count(",") >= 2 else [v]
        out += [p.strip() for p in parts if p.strip()]
    return out


def clean_keywords(values, vocab):
    out, seen = [], set()
    for k in split_keywords(values):
        low = k.lower()
        if low in seen:
            continue
        if norm(k) not in vocab and (low in NOISE or NOISE_PATTERN.match(k)):
            continue
        seen.add(low)
        out.append(k)
    return out


def person(name):
    """'van de Weerd, Inge' -> 'Inge van de Weerd'."""
    if "," in name:
        last, given = [x.strip() for x in name.split(",", 1)]
        return f"{given} {last}".strip()
    return name.strip()


def pdf_of(md):
    """Link naar de publieke versie in de repository, alleen als die vrij toegankelijk is."""
    for b in md.get("dc.bitstream.metadata", []):
        parts = [x.strip() for x in b.split("|")]
        if len(parts) < 3:
            continue
        info = " ".join(parts[2:])
        if "Open Access" not in info:
            continue
        m = re.search(r"embargoEndDate:\s*(\d{4}-\d{2}-\d{2})", info)
        if m and m.group(1) > date.today().isoformat():
            continue
        return f"{SITE}/bitstreams/{parts[1]}/download"
    return None


def record(md, handle, vocab):
    doi = bare_doi(first(md, "dc.identifier.doi"))
    issued = first(md, "dc.date.issued") or ""
    venue = first(md, "dc.relation.ispartofseries") or first(md, "dc.publisher") or ""
    return {
        "title": first(md, "dc.title"),
        "authors": [person(a) for a in md.get("dc.contributor.author", [])],
        "year": int(issued[:4]) if issued[:4].isdigit() else 0,
        "date": issued.replace("-", "/"),
        "venue": venue,
        "type": pure_type(first(md, "dc.type.content")),
        "classification": ["peer-review"] if first(md, "dc.type.peerreviewed") == "Peer reviewed" else [],
        "doi": doi,
        "arxiv": doi.split("arxiv.", 1)[1] if doi and doi.startswith("10.48550/arxiv.") else None,
        "pure_url": None,
        "repository_url": f"{SITE}/handle/{handle}",
        "pdf": pdf_of(md),
        "keywords": clean_keywords(md.get("dc.subject.keywords", []), vocab),
        "abstract": first(md, "dc.description.abstract"),
    }


def load():
    pubs = json.load(open("publications.json", encoding="utf-8"))
    vocab = {norm(k) for p in pubs for k in p.get("keywords", [])}
    return pubs, vocab


def fetch_all():
    hs = handles()
    if not hs:
        print("Feed van de repository niet bereikbaar of leeg.")
        sys.exit(1)
    items = []
    for h in hs:
        md = metadata(h)
        time.sleep(0.5)
        if md is None:
            print(f"  FOUT bij {h}")
            continue
        items.append((h, md))
    return items


def compare():
    pubs, vocab = load()
    by_doi = {bare_doi(p.get("doi")): p for p in pubs if p.get("doi")}
    by_title = {norm(p["title"]): p for p in pubs}
    tot = found = 0
    extras = Counter()
    for h, md in fetch_all():
        p = by_doi.get(bare_doi(first(md, "dc.identifier.doi"))) or by_title.get(norm(first(md, "dc.title")))
        if not p:
            continue
        pure = {norm(k) for k in p.get("keywords", [])}
        got = {norm(k): k for k in clean_keywords(md.get("dc.subject.keywords", []), vocab)}
        tot += len(pure)
        found += len(pure & got.keys())
        for k in got.keys() - pure:
            extras[got[k]] += 1
    print(f"Pure-keywords teruggevonden: {found}/{tot}")
    print("Overgebleven extra termen na filteren:")
    for k, n in extras.most_common():
        print(f"  {n:>3}  {k}")


def is_preprint(t):
    return t == "Working paper"


def main():
    if "--compare" in sys.argv:
        return compare()
    dry = "--dry-run" in sys.argv

    pubs, vocab = load()
    known_dois = {bare_doi(p.get("doi")) for p in pubs if p.get("doi")}
    known = {(norm(p["title"]), is_preprint(p.get("type"))) for p in pubs}

    items = fetch_all()
    print(f"{len(items)} items in de repository, {len(pubs)} in publications.json\n")

    added = []
    for h, md in items:
        rec = record(md, h, vocab)
        if not rec["title"]:
            continue
        key = (norm(rec["title"]), is_preprint(rec["type"]))
        if (rec["doi"] and rec["doi"] in known_dois) or key in known:
            continue
        added.append(rec)
        known.add(key)
        if rec["doi"]:
            known_dois.add(rec["doi"])
        print(f"  + {rec['year']}  {(rec['type'] or '?')[:28]:<28}  {rec['title'][:60]}")
        print(f"      keywords: {'; '.join(rec['keywords']) or '(geen)'}")

    if not added:
        print("Geen nieuwe publicaties.")
        return
    if dry:
        print(f"\n--dry-run: {len(added)} nieuw, niets weggeschreven.")
        return

    pubs.extend(added)
    normalize_authors(pubs)
    pubs.sort(key=lambda p: (-p["year"], p["title"]))
    with open("publications.json", "w", encoding="utf-8") as f:
        json.dump(pubs, f, indent=2, ensure_ascii=False)
    print(f"\n{len(added)} toegevoegd, {len(pubs)} in totaal.")


if __name__ == "__main__":
    main()
