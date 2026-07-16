import json
import re
import sys
import time
import urllib.request
import xmltodict

FEED = "https://research-portal.uu.nl/en/persons/iris-beerepoot/publications/?format=rss&page={}"
UA = "Mozilla/5.0 (compatible; irisbeerepoot-site/1.0)"
MAX_PAGES = 10

# arXiv-categorieën en dergelijke zijn geen keywords voor op de site
KEYWORD_NOISE = re.compile(r"^(cs|econ|eess|math|q-bio|q-fin|stat)\.[A-Z]{2}$", re.I)


def get(url, attempt=1):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read().decode("utf-8", errors="replace")
    except Exception as e:
        if attempt <= 3:
            time.sleep(3 * attempt)
            return get(url, attempt + 1)
        print(f"    {e}")
        return None


def unescape(s):
    return (s.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
             .replace("&quot;", '"').replace("&#39;", "'").replace("&#160;", " "))


def meta_all(html, name):
    return [unescape(m) for m in re.findall(rf'<meta name="{name}" content="([^"]*)"', html)]


def meta_one(html, name):
    v = meta_all(html, name)
    return v[0] if v else None


def keywords_of(html):
    out, seen = [], set()
    for raw in re.split(r"[;,]", meta_one(html, "citation_keywords") or ""):
        k = raw.strip()
        if not k or KEYWORD_NOISE.match(k):
            continue
        low = k.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(k)
    return out


def classification_of(description):
    """Haal Pure's type-classificatie uit de rendering-HTML van de RSS-item."""
    parts = re.findall(r'class="type_classification[^"]*">(?:[^<]*<[^>]*>)*([^<]+)</span>', description)
    cleaned = [unescape(p).strip(" ›") for p in parts]
    cleaned = [c for c in cleaned if c]

    parent = re.search(r'class="type_classification_parent">([^<]+)', description)
    parent = unescape(parent.group(1)).strip() if parent else None

    return parent, cleaned


def venue_of(html, description):
    journal = meta_one(html, "citation_journal_title")
    if journal:
        return journal
    conf = meta_one(html, "citation_conference_title")
    if conf:
        return conf
    book = re.search(r'<em>([^<]+)</em>', description)
    if book:
        return unescape(book.group(1)).rstrip(".")
    publisher = meta_one(html, "citation_publisher")
    return publisher or ""

def abstract_of(html):
    m = re.search(r'class="textblock">(.*?)</div>', html, re.S)
    if not m:
        return None
    text = re.sub(r"<[^>]+>", " ", m.group(1))
    text = unescape(re.sub(r"\s+", " ", text)).strip()
    return text or None

def main():
    items = []
    for page in range(MAX_PAGES):
        feed = get(FEED.format(page))
        if not feed:
            break
        chunk = xmltodict.parse(feed)["rss"]["channel"].get("item") or []
        if isinstance(chunk, dict):
            chunk = [chunk]
        if not chunk:
            break
        items.extend(chunk)
        print(f"page {page}: {len(chunk)} items")
        time.sleep(0.5)

    print(f"\n{len(items)} publicaties totaal\n")

    pubs = []
    for i, item in enumerate(items, 1):
        url = item["link"]
        html = get(url)
        time.sleep(0.4)

        if not html:
            print(f"  {i:>3}  FOUT  {item['title'][:50]}")
            continue

        description = item.get("description") or ""
        parent, classes = classification_of(description)
        date = meta_one(html, "citation_publication_date") or ""

        pubs.append({
            "title": meta_one(html, "citation_title") or unescape(item["title"]),
            "authors": meta_all(html, "citation_author"),
            "year": int(date[:4]) if date[:4].isdigit() else 0,
            "date": date,
            "venue": venue_of(html, description),
            "type": parent,
            "classification": classes,
            "doi": meta_one(html, "citation_doi"),
            "arxiv": meta_one(html, "citation_arxiv_id"),
            "pure_url": url,
            "pdf": meta_one(html, "citation_pdf_url"),
            "keywords": keywords_of(html),
            "abstract": abstract_of(html),
        })

        p = pubs[-1]
        print(f"  {i:>3}  {p['year']}  {len(p['keywords'])}kw  {(p['type'] or '?')[:28]:<28}  {p['title'][:40]}")

    pubs.sort(key=lambda p: (-p["year"], p["title"]))

    if not pubs:
        print("Niets opgehaald, niets weggeschreven.")
        sys.exit(1)

    with open("publications.json", "w", encoding="utf-8") as f:
        json.dump(pubs, f, indent=2, ensure_ascii=False)

    from collections import Counter
    kw = Counter(k.lower() for p in pubs for k in p["keywords"])
    types = Counter(p["type"] for p in pubs)

    print(f"\n{len(pubs)} weggeschreven")
    print(f"{sum(1 for p in pubs if p['pdf'])} met PDF")
    with_abstract = sum(1 for p in pubs if p["abstract"])
    print(f"{with_abstract} met abstract")
    if with_abstract < len(pubs) * 0.5:
        print("  WAARSCHUWING: weinig abstracts gevonden, check of Pure's HTML is veranderd")
    print(f"{len(kw)} unieke keywords\n")

    print("Types:")
    for t, n in types.most_common():
        print(f"  {n:>3}  {t}")


if __name__ == "__main__":
    main()