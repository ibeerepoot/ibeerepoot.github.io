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


def _meta(h, name):
    vals = re.findall(rf'<meta[^>]+name="{re.escape(name)}"[^>]+content="([^"]*)"', h)
    vals += re.findall(rf'<meta[^>]+content="([^"]*)"[^>]+name="{re.escape(name)}"', h)
    return _split(vals)


def _jsonld(h):
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', h, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        for node in (data if isinstance(data, list) else [data]):
            node = node.get("mainEntity", node) if isinstance(node, dict) else node
            kw = node.get("keywords") if isinstance(node, dict) else None
            if kw:
                return _split([kw]) if isinstance(kw, str) else [str(k) for k in kw]
    return []


def _springer_list(h):
    vals = re.findall(r'class="c-article-subject-list__subject"[^>]*>\s*(?:<[^>]+>)*\s*([^<]+)', h)
    return [htmllib.unescape(v).strip() for v in vals]


EXTRACTORS = [
    ("json-ld", _jsonld),
    ("springer-list", _springer_list),
    ("citation_keywords", lambda h: _meta(h, "citation_keywords")),
    ("keywords", lambda h: _meta(h, "keywords")),
]


def all_sources(h):
    """Alle bronnen die iets opleveren, voor diagnose."""
    return {name: f(h) for name, f in EXTRACTORS if f(h)}


def keywords_from_html(h):
    for name, f in EXTRACTORS:
        kws = f(h)
        if kws:
            return kws, name
    return [], None


def publisher_keywords(doi):
    status, url, h = fetch(doi)
    if status != 200 or not h:
        return None, status, url, None, {}
    kws, how = keywords_from_html(h)
    return kws, status, url, how, all_sources(h)


def norm(k):
    return re.sub(r"[^a-z0-9]", "", k.lower())


def openalex_keywords(doi):
    req = urllib.request.Request(
        "https://api.openalex.org/works/doi:" + doi, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            w = json.load(r)
    except Exception:
        return None
    return [k["display_name"] for k in w.get("keywords", [])]


def main():
    pubs = json.load(open("publications.json", encoding="utf-8"))
    vocab = {norm(k) for p in pubs for k in p.get("keywords", [])}
    rows = []
    for p in pubs:
        if not p.get("doi"):
            continue
        kws, status, url, how, sources = publisher_keywords(p["doi"])
        oa = openalex_keywords(p["doi"])
        pure = {norm(k) for k in p.get("keywords", [])}
        got = {norm(k) for k in (kws or [])}
        oa_n = {norm(k) for k in (oa or [])}
        prefix = p["doi"].split("/")[0]
        rows.append(dict(prefix=prefix, status=status, how=how, pure=pure, got=got, oa=oa_n,
                         oa_ok=oa is not None))
        print(f"{prefix:<9} {str(status):<5} {str(how):<17} pure={len(pure):>2} "
              f"uitg={len(got):>2}/{len(pure & got):<2} openalex={len(oa_n):>2}/{len(pure & oa_n):<2} "
              f"oa-in-vocab={len(oa_n & vocab):>2}  {p['title'][:45]}")
        if sources and len(sources) > 1:
            for name, v in sources.items():
                print(f"{'':<33}{name}: {'; '.join(v)[:90]}")
        time.sleep(1)

    print("\nPer uitgever (DOI-prefix): papers | uitgever: met kw, Pure-kw terug | OpenAlex: met kw, Pure-kw terug")
    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0])
    for r in rows:
        a = agg[r["prefix"]]
        a[0] += 1
        a[1] += bool(r["got"])
        a[2] += len(r["pure"] & r["got"])
        a[3] += bool(r["oa"])
        a[4] += len(r["pure"] & r["oa"])
        a[5] += len(r["pure"])
    for prefix, (n, wk, ov, owk, oov, npure) in sorted(agg.items(), key=lambda x: -x[1][0]):
        print(f"  {prefix:<9} {n:>3} | {wk:>3}  {ov:>3}/{npure:<3} | {owk:>3}  {oov:>3}/{npure:<3}")

    # Combinatie: uitgever waar mogelijk, anders OpenAlex
    comb_cov = sum(1 for r in rows if r["got"] or r["oa"])
    comb_ov = sum(len(r["pure"] & (r["got"] or r["oa"])) for r in rows)
    npure = sum(len(r["pure"]) for r in rows)
    print(f"\nTotaal {len(rows)} papers")
    print(f"  uitgever:            {sum(bool(r['got']) for r in rows):>3} met kw, "
          f"{sum(len(r['pure'] & r['got']) for r in rows)}/{npure} Pure-kw terug")
    print(f"  OpenAlex:            {sum(bool(r['oa']) for r in rows):>3} met kw, "
          f"{sum(len(r['pure'] & r['oa']) for r in rows)}/{npure} Pure-kw terug "
          f"(OpenAlex bereikbaar: {sum(r['oa_ok'] for r in rows)})")
    print(f"  uitgever, anders OA: {comb_cov:>3} met kw, {comb_ov}/{npure} Pure-kw terug")


if __name__ == "__main__":
    main()
