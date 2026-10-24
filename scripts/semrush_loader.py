"""Read Semrush Site Audit xlsx exports (issues, mega export, pages, structured data)."""
import pandas as pd
from common import unesc, clean, isnan


class Semrush:
    def __init__(self, files):
        self.files = files or {}
        rd = lambda k: pd.read_excel(self.files[k]) if k in self.files else None
        import warnings; warnings.filterwarnings("ignore")
        self.issues = rd("issues"); self.mega = rd("mega"); self.pages = rd("pages"); self.sd = rd("structured_data")
        for df in (self.mega, self.pages, self.sd):
            if df is not None:
                df.columns = [unesc(c) for c in df.columns]
                if "Domain" in df.columns:
                    df["url"] = df["Domain"].astype(str) + df["Page URL"].fillna("").astype(str)
                else:  # newer exports: "Page URL" already holds the full URL
                    df["url"] = df["Page URL"].fillna("").astype(str)
        if self.issues is not None:
            self.issues["Issue"] = self.issues["Issue"].map(unesc)

    @property
    def ok(self):
        return self.issues is not None

    def totals(self):
        if self.issues is None:
            return None
        g = self.issues.groupby("Issue Type")["Failed checks"].sum().to_dict()
        return {"errors": int(g.get("ERROR", 0)), "warnings": int(g.get("WARNING", 0)), "notices": int(g.get("NOTICE", 0))}

    def failed(self):
        if self.issues is None:
            return []
        f = self.issues[self.issues["Failed checks"] > 0]
        return [{"issue": r["Issue"], "type": r["Issue Type"], "failed": int(r["Failed checks"]), "total": int(r["Total checks"])} for _, r in f.iterrows()]

    def issue_urls(self, issue):
        """URLs flagged for an issue in the mega export (value > 0). Rows with a blank Page URL are the bare-domain duplicate."""
        if self.mega is None or issue not in self.mega.columns:
            return {}
        v = pd.to_numeric(self.mega[issue], errors="coerce").fillna(0)
        rows = self.mega[v > 0]
        return {u: int(n) for u, n in zip(rows["url"], v[v > 0])}

    def page_info(self):
        if self.pages is None:
            return {}
        out = {}
        for _, r in self.pages.iterrows():
            out[r["url"]] = {k: clean(r.get(k), None) for k in ("HTTP Status Code", "Crawl Depth", "Incoming Internal Links", "Outgoing Internal Links",
                             "Outgoing External Links", "In sitemap", "Page (HTML) Load Time, sec", "JS and CSS Number", "JS and CSS Size, KB",
                             "Page Title", "Canonicalization", "Schema.org (JSON-LD)", "Schema.org (Microdata)")}
        return out

    def structured(self):
        if self.sd is None:
            return []
        item_cols = [c for c in self.sd.columns if c.endswith(" items")]
        out = []
        for _, r in self.sd.iterrows():
            items = [c[:-6] for c in item_cols if (pd.to_numeric(r[c], errors="coerce") or 0) > 0]
            out.append({"url": r["url"], "jsonld": bool(clean(r.get("Schema.org (JSON-LD)"), 0)), "microdata": bool(clean(r.get("Schema.org (Microdata)"), 0)),
                        "items": items})
        return out

    def markup_errors(self):
        if self.issues is None:
            return None
        r = self.issues[self.issues["Issue"] == "Structured data that contains markup errors"]
        return None if not len(r) else (int(r["Failed checks"].iloc[0]), int(r["Total checks"].iloc[0]))
