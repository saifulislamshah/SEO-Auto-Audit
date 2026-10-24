"""Scan a client folder and classify every input file.

Usage: python inventory.py <client_folder>
Writes <client_folder>/.seo-audit-work/inventory.json and prints a short summary.
"""
import os, re, sys, glob, csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import work_dir, save_json

IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
REPORT_PAT = re.compile(r"(SEO[_ ]Audit[_ ]Report|_SEO_Audit_Final_|_SEO_Audit_Expert_|_SEO_Checklist_)", re.I)


def csv_header(path):
    try:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            return next(csv.reader(f), [])
    except Exception:
        return []


def count_rows(path):
    try:
        with open(path, encoding="utf-8-sig", errors="replace", newline="") as f:
            return max(sum(1 for _ in csv.reader(f)) - 1, 0)
    except Exception:
        return 0


def find_sf_dirs(root):
    hits = []
    for d, _, files in os.walk(root):
        if ".seo-audit-work" in d:
            continue
        fs = set(files)
        if {"internal_all.csv", "internal_html.csv"} & fs:
            hits.append(d)
    if not hits:  # export contains only the issues report
        for d, _, files in os.walk(root):
            if "issues_overview_report.csv" in files and ".seo-audit-work" not in d:
                hits.append(d)
    return sorted(hits)  # dated sub-folders sort chronologically; last = newest


def find_semrush(root):
    out = {}
    for f in glob.glob(os.path.join(root, "**", "*.xlsx"), recursive=True):
        b = os.path.basename(f).lower()
        if REPORT_PAT.search(os.path.basename(f)) or ".seo-audit-work" in f:
            continue
        if "_issues_" in b: out["issues"] = f
        elif "_mega_export_" in b: out["mega"] = f
        elif "_pages_structured_data_" in b: out["structured_data"] = f
        elif "_pages_" in b: out["pages"] = f
    return out


def classify_csv(path):
    h = [x.strip().lower() for x in csv_header(path)]
    hs = " | ".join(h)
    if ("top queries" in hs or "query" in h) and "impressions" in hs: return "gsc_queries"
    if "top pages" in hs and "impressions" in hs: return "gsc_pages"
    if "impressions" in hs and "clicks" in hs: return "gsc_other"
    if "referring page url" in hs or "source url" in hs or "referring domain" in hs: return "backlinks"
    if "sessions" in hs or "landing page" in hs: return "ga4"
    if "keyword" in hs and ("position" in hs or "search volume" in hs or "volume" in hs): return "keywords"
    return "other_csv"


def inventory(root):
    root = os.path.abspath(root)
    sf_dirs = find_sf_dirs(root)
    sf_dir = sf_dirs[-1] if sf_dirs else None
    inv = {"client_folder": root, "folder_name": os.path.basename(root), "screaming_frog": None, "screaming_frog_all": sf_dirs,
           "semrush": find_semrush(root), "images": {"pagespeed": [], "semrush_overview": [], "other": []},
           "text_notes": [], "extra_data": {}, "existing_reports": [], "other_files": []}
    if sf_dir:
        csvs = glob.glob(os.path.join(sf_dir, "**", "*.csv"), recursive=True)
        nonempty = [c for c in csvs if count_rows(c) > 0]
        inv["screaming_frog"] = {"dir": sf_dir, "csv_files": len(csvs), "csv_with_data": len(nonempty),
                                 "seospider_file": bool(glob.glob(os.path.join(sf_dir, "*.seospider")))}
    sf_set = set(sf_dirs)
    for d, dirs, files in os.walk(root):
        if ".seo-audit-work" in d or any(d.startswith(s) for s in sf_set):
            continue
        for f in files:
            p = os.path.join(d, f); fl = f.lower(); ext = os.path.splitext(fl)[1]
            if REPORT_PAT.search(f):
                inv["existing_reports"].append(p); continue
            if ext in IMG_EXT:
                if "pagespeed" in fl or "lighthouse" in fl or "psi" in fl:
                    inv["images"]["pagespeed"].append(p)
                elif "semrush" in fl or "over view" in fl or "overview" in fl or "site audit" in fl:
                    inv["images"]["semrush_overview"].append(p)
                else:
                    inv["images"]["other"].append(p)
            elif ext in (".txt", ".md"):
                inv["text_notes"].append(p)
            elif ext == ".csv":
                kind = classify_csv(p)
                inv["extra_data"].setdefault(kind, []).append(p)
            elif ext == ".xlsx" and p not in inv["semrush"].values():
                inv["other_files"].append(p)
    return inv


def main():
    root = sys.argv[1]
    inv = inventory(root)
    save_json(inv, os.path.join(work_dir(root), "inventory.json"))
    print(f"Client folder: {inv['client_folder']}")
    sf = inv["screaming_frog"]
    print("Screaming Frog:", f"{sf['dir']} ({sf['csv_with_data']}/{sf['csv_files']} CSVs with data)" if sf else "NOT FOUND -> live crawl fallback")
    print("Semrush:", ", ".join(f"{k}={os.path.basename(v)}" for k, v in inv["semrush"].items()) or "NOT FOUND")
    for k, v in inv["images"].items():
        print(f"Images [{k}]: {len(v)}", *[os.path.basename(x) for x in v], sep="\n   ")
    print("Text notes:", [os.path.basename(x) for x in inv["text_notes"]])
    print("Extra data:", {k: [os.path.basename(x) for x in v] for k, v in inv["extra_data"].items()})
    print("Existing reports (ignored as input):", [os.path.basename(x) for x in inv["existing_reports"]])


if __name__ == "__main__":
    main()
