#!/usr/bin/env python3
"""Real-guidance proxy from SEC EDGAR earnings press releases (8-K Item 2.02, Exhibit 99.x).
Flags each release for 'raised guidance/outlook' language. Cached at /workspace/.earn_cache/guid.pkl.
Subset: top-N S&P 500 members by 2025 median dollar volume."""
import os, re, sys, time, zlib, pickle, html, requests, pandas as pd, numpy as np
import earnings_data as ED
C = "/workspace/.earn_cache/guid.pkl"; H = {"User-Agent": "BBA backtest lab research casey@example.com"}
RAISE = re.compile(r"\b(rais|increas|lift|boost|updat\w* and rais)\w*\s+(?:its\s+|our\s+|the\s+)?(?:full[- ]year\s+|fiscal\s+(?:year\s+)?(?:20\d\d\s+)?|annual\s+|20\d\d\s+|fy\s?\d\d\s+)?(?:financial\s+|revenue\s+|eps\s+|earnings\s+|sales\s+)?(guidance|outlook|forecast)", re.I)
RAISE2 = re.compile(r"(guidance|outlook|forecast)\s+(?:is\s+|has\s+been\s+)?(raised|increased)", re.I)
LOWER = re.compile(r"\b(lower|reduc|cut)\w*\s+(?:its\s+|our\s+|the\s+)?(?:full[- ]year\s+|fiscal\s+(?:year\s+)?(?:20\d\d\s+)?|annual\s+)?(guidance|outlook|forecast)", re.I)
RAISE3 = re.compile(r"\b(rais|increas|lift|boost)\w*(?:\W+\w+){0,4}?\W+(guidance|outlook)\b", re.I)
def flags(z):
    t = zlib.decompress(z).decode()
    return bool(RAISE.search(t) or RAISE2.search(t) or RAISE3.search(t)), bool(LOWER.search(t))
def g(u):
    for k in range(4):
        r = requests.get(u, headers=H, timeout=30); time.sleep(0.12)
        if r.status_code == 200: return r
        time.sleep(2 * (k + 1))
    return None
def subset(n):
    px = ED.prices(); tk = [t for t in ED.members().yf if t in px.columns.get_level_values(0)]
    dv = {t: float((px[t]["Close"] * px[t]["Volume"]).loc["2025"].median()) for t in tk}
    return sorted(tk, key=lambda t: -np.nan_to_num(dv[t]))[:n]
def main(n=100):
    out = pickle.load(open(C, "rb")) if os.path.exists(C) else {}
    cik = {v["ticker"].replace(".", "-"): v["cik_str"] for v in g("https://www.sec.gov/files/company_tickers.json").json().values()}
    for t in subset(n):
        if t in out or t not in cik: continue
        s = g(f"https://data.sec.gov/submissions/CIK{cik[t]:010d}.json").json()["filings"]["recent"]
        rows = []
        for f, it, d, a, pdoc in zip(s["form"], s["items"], s["filingDate"], s["accessionNumber"], s["primaryDocument"]):
            if f != "8-K" or "2.02" not in it or d < "2019-06-01": continue
            base = f"https://www.sec.gov/Archives/edgar/data/{cik[t]}/{a.replace('-', '')}"
            ix = g(base + "/index.json")
            if ix is None: continue
            docs = [x["name"] for x in ix.json()["directory"]["item"] if re.search(r"ex[-_]?99|exhibit99|ex991|dex99", x["name"], re.I) and x["name"].lower().endswith((".htm", ".html", ".txt"))]
            txt = ""
            for dn in docs[:2]:
                r = g(f"{base}/{dn}")
                if r: txt += " " + html.unescape(re.sub(r"<[^>]+>", " ", r.text))
            txt = re.sub(r"\s+", " ", txt)
            rows.append({"filed": d, "has_text": len(txt) > 500, "text": zlib.compress(txt.encode())})
        out[t] = pd.DataFrame(rows); pickle.dump(out, open(C, "wb"))
        print(t, len(rows), sum(r['has_text'] for r in rows), flush=True)
    return out
if __name__ == "__main__": main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
