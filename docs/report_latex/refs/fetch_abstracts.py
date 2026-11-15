"""Fetch abstracts (Semantic Scholar, Crossref fallback) for the DOIs in dois.tsv into abstracts/."""
import json, pathlib, re, time, urllib.request
HERE = pathlib.Path(__file__).resolve().parent
out = HERE / "abstracts"; out.mkdir(exist_ok=True)
for line in (HERE / "dois.tsv").read_text().splitlines():
    if not line or line.startswith("#"): continue
    key, doi = [x.strip() for x in line.split("\t")]
    f = out / f"{key}.txt"
    if f.exists() and f.stat().st_size > 50: continue
    text = ""
    for attempt in range(3):
        try:
            u = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,abstract,tldr"
            d = json.load(urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "report-abstracts/1.0"}), timeout=30))
            text = d.get("abstract") or ((d.get("tldr") or {}).get("text") or "")
            break
        except Exception as e:
            time.sleep(4 * (attempt + 1))
    if not text:
        cr = json.loads((HERE / "crossref_cache" / (doi.replace("/", "_") + ".json")).read_text())
        text = re.sub(r"<[^>]+>", " ", cr.get("abstract", ""))
    f.write_text(text.strip())
    print(f"{key}: {len(text)} chars")
    time.sleep(1.2)
