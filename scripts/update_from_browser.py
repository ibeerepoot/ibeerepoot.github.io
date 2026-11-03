"""Nieuwe publicaties toevoegen op basis van bestanden die je zelf in je browser
uit Pure hebt opgeslagen.

Pure (research-portal.uu.nl) zit achter een botcheck, dus scripts kunnen het niet
meer zelf ophalen. Werkwijze:

  1. Open https://research-portal.uu.nl/en/persons/iris-beerepoot/publications/
     en klik op de RSS-knop. Het bestand komt in Downloads (of zet het in de websitemap).
  2. Draai ./update.sh. Dat meldt welke publicaties nieuw zijn, met hun Pure-link.
  3. Open elke nieuwe link, sla de pagina op met Cmd+S ("Webpagina, alleen HTML")
     in Downloads of in de map pure-pages/.
  4. Draai ./update.sh opnieuw. Nu worden ze toegevoegd, gecommit en gepusht.

Bestaande publicaties worden niet aangepast.
"""
import glob
import html as htmllib
import json
import os
import re
import sys

from fetch_pure import (abstract_of, classification_of, keywords_of, meta_all,
                        meta_one, normalize_authors, unescape, venue_of)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOWNLOADS = os.path.expanduser("~/Downloads")
PUBS = os.path.join(ROOT, "publications.json")


def tkey(title):
    return re.sub(r"[^a-z0-9]", "", (title or "").lower())


def newest(paths):
    paths = [p for p in paths if os.path.isfile(p)]
    return max(paths, key=os.path.getmtime) if paths else None


def find_rss():
    cands = glob.glob(os.path.join(ROOT, "rss*.xml")) + glob.glob(os.path.join(DOWNLOADS, "rss*.xml"))
    return newest(cands)


def parse_rss(path):
    s = open(path, encoding="utf-8", errors="replace").read()
    items = []
    for it in re.findall(r"<item>(.*?)</item>", s, re.S):
        def tag(name):
            m = re.search(rf"<{name}>(.*?)</{name}>", it, re.S)
            return m.group(1).strip() if m else ""
        items.append({
            "title": unescape(htmllib.unescape(tag("title"))),
            "link": tag("link"),
            "description": htmllib.unescape(tag("description")),
        })
    return items


def saved_pages():
    """Alle opgeslagen Pure-pagina's, geindexeerd op titel en op URL."""
    files = glob.glob(os.path.join(ROOT, "pure-pages", "*.htm*")) + \
        glob.glob(os.path.join(DOWNLOADS, "*.htm*"))
    by_title, by_url = {}, {}
    for f in sorted(files, key=os.path.getmtime):  # nieuwste wint
        try:
            h = open(f, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        title = meta_one(h, "citation_title")
        if not title:
            continue  # geen Pure-publicatiepagina (of de botcheck-pagina)
        by_title[tkey(title)] = (f, h)
        for url in re.findall(r'(?:rel="canonical" href|property="og:url" content)="([^"]+)"', h):
            by_url[url] = (f, h)
    return by_title, by_url


def record(item, page_html):
    description = item["description"]
    parent, classes = classification_of(description)
    date = meta_one(page_html, "citation_publication_date") or ""
    return {
        "title": meta_one(page_html, "citation_title") or item["title"],
        "authors": meta_all(page_html, "citation_author"),
        "year": int(date[:4]) if date[:4].isdigit() else 0,
        "date": date,
        "venue": venue_of(page_html, description),
        "type": parent,
        "classification": classes,
        "doi": meta_one(page_html, "citation_doi"),
        "arxiv": meta_one(page_html, "citation_arxiv_id"),
        "pure_url": item["link"],
        "pdf": meta_one(page_html, "citation_pdf_url"),
        "keywords": keywords_of(page_html),
        "abstract": abstract_of(page_html),
    }


def main():
    rss = find_rss()
    if not rss:
        print("Geen rss*.xml gevonden in de websitemap of in Downloads.")
        print("Klik op de RSS-knop op je Pure-publicatiepagina en probeer opnieuw.")
        sys.exit(1)
    items = parse_rss(rss)
    print(f"RSS: {os.path.basename(rss)} ({len(items)} items)")
    if not items:
        print("Het bestand bevat geen publicaties. Is het misschien de botcheck-pagina?")
        sys.exit(1)

    with open(PUBS, encoding="utf-8") as f:
        pubs = json.load(f)
    known_urls = {p.get("pure_url") for p in pubs}
    known_titles = {tkey(p["title"]) for p in pubs}

    new = [it for it in items
           if it["link"] not in known_urls and tkey(it["title"]) not in known_titles]
    if not new:
        print("Geen nieuwe publicaties. Je site is bij.")
        return

    by_title, by_url = saved_pages()
    added, missing = [], []
    for it in new:
        page = by_url.get(it["link"]) or by_title.get(tkey(it["title"]))
        if page:
            rec = record(it, page[1])
            added.append(rec)
            print(f"  + {rec['title'][:70]}  ({len(rec['keywords'])} keywords)")
        else:
            missing.append(it)

    if missing:
        print(f"\nNog op te slaan ({len(missing)}). Open elke link en sla op met Cmd+S:")
        for it in missing:
            print(f"  - {it['title'][:70]}\n    {it['link']}")

    if not added:
        print("\nNog niets toegevoegd.")
        sys.exit(2)

    pubs.extend(added)
    normalize_authors(pubs)
    pubs.sort(key=lambda p: (-p["year"], p["title"]))
    with open(PUBS, "w", encoding="utf-8") as f:
        json.dump(pubs, f, indent=2, ensure_ascii=False)
    print(f"\n{len(added)} toegevoegd, {len(pubs)} in totaal.")
    if missing:
        sys.exit(3)  # deels gelukt: update.sh herinnert je aan de rest


if __name__ == "__main__":
    main()
