import json
import re
import sys
import urllib.request
import xmltodict

DBLP_PID = "231/6330"
URL = f"https://dblp.org/pid/{DBLP_PID}.xml"

TYPE_LABELS = {
    "article": "Journal",
    "inproceedings": "Conference",
    "incollection": "Chapter",
    "phdthesis": "Thesis",
    "book": "Book",
}

VENUE_MAP = {
    "Bus. Inf. Syst. Eng.": "Business & Information Systems Engineering",
    "Comput. Ind.": "Computers in Industry",
    "Data Knowl. Eng.": "Data & Knowledge Engineering",
    "Inf. Technol. Manag.": "Information Technology and Management",
    "Int. J. Cooperative Inf. Syst.": "International Journal of Cooperative Information Systems",
    "J. Biomed. Informatics": "Journal of Biomedical Informatics",
    "J. Intell. Inf. Syst.": "Journal of Intelligent Information Systems",
    "RCIS (1)": "International Conference on Research Challenges in Information Science (RCIS)",
    "RCIS": "International Conference on Research Challenges in Information Science (RCIS)",
    "BPM": "International Conference on Business Process Management (BPM)",
    "BPM (Forum)": "BPM Forum",
    "BPM (Demos / Resources Forum)": "BPM Demos / Resources Forum",
    "Business Process Management Workshops": "BPM Workshops",
    "Problems@BPM": "Problems@BPM Workshop",
    "CAiSE": "International Conference on Advanced Information Systems Engineering (CAiSE)",
    "CoopIS": "International Conference on Cooperative Information Systems (CoopIS)",
    "ECIS": "European Conference on Information Systems (ECIS)",
    "ICIS": "International Conference on Information Systems (ICIS)",
    "ICPM": "International Conference on Process Mining (ICPM)",
    "ICPM Workshops": "ICPM Workshops",
    "ICPM Doctoral Consortium / Demo": "ICPM Doctoral Consortium / Demo",
    "EDOC": "International Conference on Enterprise Design, Operations and Computing (EDOC)",
    "EGOV": "International Conference on Electronic Government (EGOV)",
    "ECSCW": "European Conference on Computer-Supported Cooperative Work (ECSCW)",
    "CSCW Companion": "CSCW Companion",
    "HICSS": "Hawaii International Conference on System Sciences (HICSS)",
}


def listify(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def clean_name(a):
    name = a["#text"] if isinstance(a, dict) else a
    return re.sub(r"\s+\d{4}$", "", name)


def pick_link(ee):
    links = [e["#text"] if isinstance(e, dict) else e for e in listify(ee)]
    for link in links:
        if "doi.org" in link:
            return link
    return links[0] if links else None


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "irisbeerepoot-site/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = xmltodict.parse(r.read())

    raw = []
    for record in listify(data["dblpperson"]["r"]):
        for kind, entry in record.items():
            if kind not in TYPE_LABELS:
                continue
            raw.append({
                "title": entry.get("title", "").rstrip("."),
                "authors": [clean_name(a) for a in listify(entry.get("author"))],
                "year": int(entry.get("year", 0)),
                "venue": entry.get("journal") or entry.get("booktitle") or "",
                "type": TYPE_LABELS[kind],
                "link": pick_link(entry.get("ee")),
                "key": entry.get("@key"),
            })

    published = {p["title"].lower() for p in raw if p["venue"] != "CoRR"}

    pubs = []
    for p in raw:
        if p["venue"] == "CoRR":
            if p["title"].lower() in published:
                continue
            p["venue"] = "arXiv preprint"
            p["type"] = "Preprint"
        elif p["type"] == "Thesis":
            p["venue"] = "PhD thesis, Utrecht University"
        else:
            p["venue"] = VENUE_MAP.get(p["venue"], p["venue"])
        pubs.append(p)

    if not pubs:
        print("Geen publicaties gevonden, niets weggeschreven.")
        sys.exit(1)

    pubs.sort(key=lambda p: (-p["year"], p["title"]))

    with open("publications.json", "w", encoding="utf-8") as f:
        json.dump(pubs, f, indent=2, ensure_ascii=False)

    print(f"{len(pubs)} publicaties weggeschreven.")
    for p in pubs[:5]:
        print(f"  {p['year']}  {p['type']:<11} {p['title'][:60]}")


if __name__ == "__main__":
    main()