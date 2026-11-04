"""Publicaties ophalen uit de UU-repository (DSpace), die zijn metadata uit Pure haalt.

Gebruik:
  python scripts/fetch_dspace.py --compare   # vergelijken met publications.json, niets wegschrijven
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter

UA = ("Mozilla/5.0 (compatible; irisbeerepoot-site/1.0; "
      "+https://github.com/ibeerepoot/ibeerepoot.github.io)")
BASE = "https://dspace.library.uu.nl/server"
FEED = BASE + "/opensearch/search?" + urllib.parse.urlencode({
    "format": "atom", "scope": "1894baf6-d89f-4073-9b4b-4c89b978e011",
    "sort": "dc.date.accessioned", "sort_direction": "DESC",
    "query": "dc.contributor.author:Beerepoot, Iris", "configuration": "community", "rpp": 100})


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
    if not body:
        return []
    seen, out = set(), []
    for h in re.findall(r'<id>https://dspace\.library\.uu\.nl/handle/(\d+/\d+)</id>', body):
        if h not in seen:
            seen.add(h)
            out.append(h)
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


def compare():
    pubs = json.load(open("publications.json", encoding="utf-8"))
    by_doi = {bare_doi(p.get("doi")): p for p in pubs if p.get("doi")}
    by_title = {norm(p["title"]): p for p in pubs}

    hs = handles()
    print(f"{len(hs)} items in de repository, {len(pubs)} in publications.json\n")

    keys, types, extras, missing_kw = Counter(), Counter(), Counter(), Counter()
    matched, unmatched = set(), []
    tot_pure = tot_found = 0
    for h in hs:
        md = metadata(h)
        time.sleep(0.5)
        if md is None:
            print(f"  FOUT bij {h}")
            continue
        keys.update(md.keys())
        title = (md.get("dc.title") or ["?"])[0]
        types[" | ".join(md.get("dc.type.content", ["?"]))] += 1
        doi = bare_doi((md.get("dc.identifier.doi") or [None])[0])
        kws = md.get("dc.subject.keywords", [])
        p = by_doi.get(doi) or by_title.get(norm(title))
        if not p:
            unmatched.append((md.get("dc.date.issued", ["?"])[0], title))
            continue
        matched.add(id(p))
        pure = {norm(k): k for k in p.get("keywords", [])}
        got = {norm(k): k for k in kws}
        tot_pure += len(pure)
        tot_found += len(pure.keys() & got.keys())
        for k in got.keys() - pure.keys():
            extras[got[k]] += 1
        for k in pure.keys() - got.keys():
            missing_kw[pure[k]] += 1
        print(f"  pure={len(pure):>2} repo={len(got):>2} overlap={len(pure.keys() & got.keys()):>2}  {title[:60]}")

    print(f"\nPure-keywords teruggevonden: {tot_found}/{tot_pure}")
    print("\nExtra termen in de repository (niet in Pure), met frequentie:")
    for k, n in extras.most_common():
        print(f"  {n:>3}  {k}")
    print("\nPure-keywords die in de repository ontbreken:")
    for k, n in missing_kw.most_common():
        print(f"  {n:>3}  {k}")
    print("\nIn de repository, niet op de site:")
    for d, t in unmatched:
        print(f"  {d}  {t[:80]}")
    print("\nOp de site, niet in de repository:")
    for p in pubs:
        if id(p) not in matched:
            print(f"  {p['year']}  {p['type'][:20]:<20}  {p['title'][:70]}")
    print("\ndc.type.content:")
    for t, n in types.most_common():
        print(f"  {n:>3}  {t}")
    print("\nMetadatavelden (in hoeveel items):")
    for k, n in keys.most_common():
        print(f"  {n:>3}  {k}")


if __name__ == "__main__":
    if "--compare" in sys.argv:
        compare()
    else:
        print("Nog alleen --compare beschikbaar.")
