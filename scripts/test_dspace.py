"""Test of de UU-repository (DSpace) bereikbaar is en wat de feed bevat."""
import json
import re
import urllib.parse
import urllib.request
from collections import Counter

UA = ("Mozilla/5.0 (compatible; irisbeerepoot-site/1.0; "
      "+https://github.com/ibeerepoot/ibeerepoot.github.io)")
FEED = ("https://dspace.library.uu.nl/server/opensearch/search?" + urllib.parse.urlencode({
    "format": "atom", "scope": "1894baf6-d89f-4073-9b4b-4c89b978e011",
    "sort": "dc.date.accessioned", "sort_direction": "DESC",
    "query": "dc.contributor.author:Beerepoot, Iris", "configuration": "community", "rpp": 100}))


def get(url, accept="*/*"):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except Exception as e:
        return type(e).__name__, ""


status, body = get(FEED)
print(f"Feed: status {status}, {len(body)} tekens")
entries = re.findall(r"<entry>(.*?)</entry>", body, re.S)
print(f"Entries: {len(entries)}")
m = re.search(r"<opensearch:totalResults>(\d+)", body)
print(f"totalResults: {m.group(1) if m else '?'}")
if not entries:
    print(body[:1500])
else:
    tags = Counter(t for e in entries for t in set(re.findall(r"<([a-zA-Z:_]+)[\s>]", e)))
    print("Elementen (in hoeveel entries):")
    for t, n in tags.most_common():
        print(f"  {n:>3}  {t}")
    print("\nEerste entry:\n" + entries[0][:3000])

    # Volledige metadata via de DSpace REST API, voor de eerste drie items
    for handle in re.findall(r"/handle/(\d+/\d+)", "".join(entries))[1:4]:
        st, js = get(f"https://dspace.library.uu.nl/server/api/pid/find?id=hdl:{handle}",
                     "application/json")
        print(f"\nREST API hdl:{handle}: status {st}")
        if st == 200:
            md = json.loads(js).get("metadata", {})
            for k, v in md.items():
                print(f"  {k}: {'; '.join(x['value'] for x in v)[:150]}")
