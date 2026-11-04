"""Auteurskeywords ophalen van de uitgeverspagina van een publicatie (via de DOI).

Als script: test voor alle publicaties in publications.json met een DOI of de
uitgeverspagina bereikbaar is en of de keywords overeenkomen met die uit Pure.
"""
import html as htmllib
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict

UA = ("Mozilla/5.0 (compatible; irisbeerepoot-site/1.0; "
      "+https://github.com/ibeerepoot/ibeerepoot.github.io)")


def fetch(doi):
    """Geeft (status, eind-URL, html) terug."""
    req = urllib.request.Request("https://doi.org/" + doi, headers={
        "User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.geturl(), r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.geturl() if hasattr(e, "geturl") else "", ""
    except Exception as e:
        return type(e).__name__, "", ""


def _split(values):
    out = []
    for v in values:
        out += [k.strip() for k in re.split(r"[;,]", htmllib.unescape(v)) if k.strip()]
    return out


def keywords_from_html(h):
    """Probeert de gangbare plekken waar uitgevers keywords neerzetten."""
    # 1. Meta-tags (Highwire/Google Scholar, Dublin Core)
    for name in ("citation_keywords", "dc.subject", "DC.subject", "keywords"):
        vals = re.findall(rf'<meta[^>]+name="{re.escape(name)}"[^>]+content="([^"]*)"', h)
        vals += re.findall(rf'<meta[^>]+content="([^"]*)"[^>]+name="{re.escape(name)}"', h)
        kws = _split(vals)
        if kws:
            return kws, name
    # 2. JSON-LD (schema.org)
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for node in (data if isinstance(data, list) else [data]):
            node = node.get("mainEntity", node) if isinstance(node, dict) else node
            kw = node.get("keywords") if isinstance(node, dict) else None
            if kw:
                return (_split([kw]) if isinstance(kw, str) else [str(k) for k in kw]), "json-ld"
    # 3. Springer: lijst met keywords in de pagina
    vals = re.findall(r'class="c-article-subject-list__subject"[^>]*>\s*(?:<[^>]+>)*\s*([^<]+)', h)
    if vals:
        return [htmllib.unescape(v).strip() for v in vals], "springer-list"
    return [], None


def publisher_keywords(doi):
    status, url, h = fetch(doi)
    if status != 200 or not h:
        return None, status, url, None
    kws, how = keywords_from_html(h)
    return kws, status, url, how


def norm(k):
    return re.sub(r"[^a-z0-9]", "", k.lower())


def main():
    pubs = json.load(open("publications.json", encoding="utf-8"))
    rows = []
    for p in pubs:
        if not p.get("doi"):
            continue
        kws, status, url, how = publisher_keywords(p["doi"])
        pure = {norm(k) for k in p.get("keywords", [])}
        got = {norm(k) for k in (kws or [])}
        prefix = p["doi"].split("/")[0]
        rows.append((prefix, status, how, len(pure), len(got), len(pure & got), p["title"]))
        print(f"{prefix:<10} {str(status):<6} {str(how):<17} pure={len(pure):>2} uitgever={len(got):>2} "
              f"overlap={len(pure & got):>2}  {p['title'][:55]}")
        time.sleep(1)

    print("\nPer uitgever (DOI-prefix):")
    agg = defaultdict(lambda: [0, 0, 0, 0, 0])
    for prefix, status, how, n_pure, n_got, n_ov, _ in rows:
        a = agg[prefix]
        a[0] += 1
        a[1] += status == 200
        a[2] += n_got > 0
        a[3] += n_pure
        a[4] += n_ov
    print(f"  {'prefix':<10} {'papers':>6} {'bereikbaar':>10} {'met kw':>7} {'Pure-kw teruggevonden':>22}")
    for prefix, (n, ok, withkw, n_pure, n_ov) in sorted(agg.items(), key=lambda x: -x[1][0]):
        pct = f"{n_ov}/{n_pure}" if n_pure else "-"
        print(f"  {prefix:<10} {n:>6} {ok:>10} {withkw:>7} {pct:>22}")
    total = len(rows)
    print(f"\nTotaal: {total} papers, {sum(r[1] == 200 for r in rows)} bereikbaar, "
          f"{sum(r[4] > 0 for r in rows)} met keywords")


if __name__ == "__main__":
    main()
