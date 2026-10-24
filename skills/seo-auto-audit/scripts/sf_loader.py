"""Read a Screaming Frog SEO Spider CSV export (any version / folder layout)."""
import os, re, glob
import pandas as pd
from common import isnan, clean, unesc


def slug(issue_name):
    s = issue_name.lower().replace(": ", "_").replace("-", "")
    s = re.sub(r"\s+", "_", s.strip())
    return s


class SF:
    def __init__(self, d):
        self.d = d
        self._cache = {}
        ov = self.read("issues_overview_report.csv")
        self.overview = ov if ov is not None else pd.DataFrame(columns=["Issue Name", "Issue Type", "Issue Priority", "URLs", "How To Fix"])
        html = self.read("internal_html.csv")
        if html is None:
            allf = self.read("internal_all.csv")
            html = allf[allf["Content Type"].astype(str).str.contains("text/html", na=False)] if allf is not None else pd.DataFrame()
        self.html = html.reset_index(drop=True)
        self.base = None

    def read(self, name):
        if name in self._cache:
            return self._cache[name]
        df = None
        for p in (os.path.join(self.d, name), os.path.join(self.d, "issues_reports", name)):
            if os.path.exists(p):
                try:
                    df = pd.read_csv(p, low_memory=False, encoding="utf-8-sig")
                except Exception:
                    df = None
                if df is not None and len(df):
                    break
                df = None
        self._cache[name] = df
        return df

    # ---------- issues ----------
    def issue_names(self):
        return [n for n, u in zip(self.overview["Issue Name"], self.overview["URLs"]) if (u or 0) > 0]

    def issue_meta(self, name):
        r = self.overview[self.overview["Issue Name"] == name]
        return r.iloc[0].to_dict() if len(r) else {}

    def issue_df(self, name):
        df = self.read(slug(name) + ".csv")
        return df

    def issue_inlinks(self, name):
        return self.read(slug(name) + "_inlinks.csv")

    def issue_urls(self, name):
        """URLs affected by an SF issue. For link-type issues returns source pages (from *_inlinks)."""
        df = self.issue_df(name)
        if df is None:
            return []
        col = "Address" if "Address" in df.columns else ("Source" if "Source" in df.columns else df.columns[0])
        return [str(x) for x in df[col].dropna().unique()]

    # ---------- pages ----------
    def pages(self):
        out = []
        h = self.html
        for _, r in h.iterrows():
            g = lambda c, d="": clean(r.get(c, d), d)
            out.append({
                "url": g("Address"), "status": int(g("Status Code", 0) or 0), "indexability": g("Indexability"),
                "indexability_status": g("Indexability Status"),
                "title": unesc(g("Title 1")), "title_len": int(g("Title 1 Length", 0) or 0), "title_px": int(g("Title 1 Pixel Width", 0) or 0),
                "desc": unesc(g("Meta Description 1")), "desc_len": int(g("Meta Description 1 Length", 0) or 0),
                "desc2": unesc(g("Meta Description 2")),
                "h1": [unesc(x) for x in [g("H1-1"), g("H1-2")] if x], "h2": [unesc(x) for x in [g("H2-1"), g("H2-2")] if x],
                "canonical": g("Canonical Link Element 1"), "robots": g("Meta Robots 1"),
                "words": int(g("Word Count", 0) or 0), "text_ratio": float(g("Text Ratio", 0) or 0),
                "depth": g("Crawl Depth"), "inlinks": g("Unique Inlinks"), "response_time": g("Response Time"),
                "transferred": g("Total Transferred (Bytes)"), "carbon": g("Carbon Rating"), "redirect": g("Redirect URL"),
                "readability": g("Readability"), "near_dupes": g("No. Near Duplicates"),
            })
        js = self.read("javascript_all.csv")
        if js is not None:
            m = js.set_index("Address")
            for p in out:
                if p["url"] in m.index:
                    p["html_words"] = clean(m.loc[p["url"]].get("HTML Word Count"), None)
        h1 = self.read("h1_all.csv")
        if h1 is not None:  # full H1 list when more than 2
            cols = [c for c in h1.columns if re.match(r"H1-\d+$", c)]
            m = h1.set_index("Address")
            for p in out:
                if p["url"] in m.index:
                    p["h1"] = [unesc(m.loc[p["url"]][c]) for c in cols if not isnan(m.loc[p["url"]][c])]
        return out

    # ---------- images ----------
    def images(self):
        allimg = self.read("images_all.csv")
        sizes = {}
        if allimg is not None:
            sizes = dict(zip(allimg["Address"], allimg["Size (Bytes)"]))
        miss = self.read("images_missing_alt_text_inlinks.csv")
        if miss is None:
            miss = self.read("images_missing_alt_attribute_text_inlinks.csv")
        missing = []
        if miss is not None:
            for _, r in miss.iterrows():
                missing.append({"page": r["Source"], "img": r["Destination"], "alt": clean(r.get("Alt Text"), "")})
        over = self.read("images_over_100_kb.csv")
        big = [] if over is None else [{"img": a, "bytes": int(b)} for a, b in zip(over["Address"], over["Size (Bytes)"])]
        return {"sizes": {k: int(v) for k, v in sizes.items() if not isnan(v)}, "missing_alt": missing, "over_100kb": big,
                "count": 0 if allimg is None else len(allimg)}

    # ---------- links ----------
    def link_issues(self):
        out = {"internal": [], "external": []}
        rc = {}
        for f in ("response_codes_all.csv", "response_codes_internal_all.csv"):
            df = self.read(f)
            if df is not None:
                for _, r in df.iterrows():
                    rc[r["Address"]] = (clean(r.get("Status Code"), 0), clean(r.get("Status"), ""), clean(r.get("Redirect URL"), ""))
        files = glob.glob(os.path.join(self.d, "*inlinks.csv")) + glob.glob(os.path.join(self.d, "issues_reports", "*inlinks.csv"))
        seen, fams = set(), set()
        for f in files:
            b = os.path.basename(f)
            kind = None
            if re.match(r"(response_codes_)?internal_(client_error|server_error|redirection|no_response|redirect_chain)", b) or b.startswith("internal_all_error"):
                kind = "internal"
            elif re.match(r"(response_codes_)?external_(client_error|server_error|redirection|no_response)", b):
                kind = "external"
            if not kind:
                continue
            fam = re.sub(r"^(response_codes_)?", "", b)
            if fam.startswith("internal_all_error") or fam.startswith("all_error"):
                continue  # aggregate file; the specific client/server error files cover these rows
            if fam in fams:
                continue
            fams.add(fam)
            df = self.read(b)
            if df is None or "Source" not in df.columns:
                continue
            for _, r in df.iterrows():
                key = (b, _)
                if key in seen:
                    continue
                seen.add(key)
                st = rc.get(r["Destination"], (clean(r.get("Status Code"), 0), clean(r.get("Status"), ""), ""))
                out[kind].append({"source": r["Source"], "target": r["Destination"], "status": int(st[0] or 0), "status_text": st[1],
                                  "final": st[2], "anchor": clean(r.get("Anchor"), ""), "position": clean(r.get("Link Position"), "")})
        rb = self.read("response_codes_blocked_by_robots_txt.csv")
        out["blocked_external"] = [] if rb is None else [{"target": a, "inlinks": int(clean(i, 0))} for a, i in zip(rb["Address"], rb.get("Inlinks", [0] * len(rb)))]
        return out

    def crawl_overview(self):
        p = os.path.join(self.d, "crawl_overview.csv")
        if not os.path.exists(p):
            return {}
        out = {}
        with open(p, encoding="utf-8-sig", errors="replace") as f:
            for line in f:
                parts = [x.strip().strip('"') for x in line.split(",")]
                if len(parts) >= 2 and parts[0] and parts[1]:
                    out.setdefault(parts[0], parts[1])
        return out

    def security_counts(self):
        out = {}
        for k in ("hsts", "contentsecuritypolicy", "xcontenttypeoptions", "xframeoptions", "secure_referrerpolicy"):
            df = self.read(f"security_missing_{k}_header.csv")
            out[k] = 0 if df is None else len(df)
        return out

    def structured(self):
        df = self.read("structured_data_all.csv")
        if df is None:
            return None
        enabled = df.get("Total Types", pd.Series([0])).fillna(0).sum() > 0
        return {"enabled": bool(enabled), "rows": df.to_dict("records")}
