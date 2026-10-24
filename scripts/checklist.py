"""Fill the 'SEO AUDIT CHECK LIST' tab for a client (Beginner mode).

Usage: python checklist.py <client_folder> [--master <xlsx>] [--template-tab <name>] [--tab <name>] [--made-by <name>]
- If a master checklist workbook is found (a workbook whose sheets start with 'SEO AUDIT CHECK LIST'),
  it is backed up and a NEW tab is added (copy of the template tab, values only changed). Other tabs are verified unchanged.
- Otherwise a new <Client>_SEO_Checklist_<date>.xlsx is created from the bundled template.
"""
import os, sys, re, glob, shutil, argparse, hashlib, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ensure_deps, work_dir, load_json, path_of, safe_name, is_caps
ensure_deps()
import openpyxl
from copy import copy

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(HERE, "..", "assets", "checklist_template.xlsx")
ap = argparse.ArgumentParser()
ap.add_argument("folder"); ap.add_argument("--master"); ap.add_argument("--template-tab"); ap.add_argument("--tab"); ap.add_argument("--made-by")
a = ap.parse_args()
FOLDER = os.path.abspath(a.folder); WD = work_dir(FOLDER)
D = load_json(os.path.join(WD, "audit_data.json")); CT = load_json(os.path.join(WD, "content.json")); S = load_json(os.path.join(WD, "report_summary.json"), {})
BASE = D["meta"]["base"]; PAGES = D["pages"]; NP = len(PAGES); ISS = D["issues"]; CP = CT.get("pages", {})
CLIENT = CT.get("client", {}).get("name") or D["meta"]["domain"]
MADE_BY = a.made_by or CT.get("client", {}).get("made_by") or S.get("made_by") or ""
DATE = datetime.date.fromisoformat(CT.get("client", {}).get("date") or D["meta"]["collected"])
PSI = CT.get("psi", {}); SITE = D.get("site", {})

def is_checklist(ws):
    return str(ws["A1"].value or "").strip().upper().startswith("SEO AUDIT CHECK LIST")

def find_master():
    if a.master: return a.master
    roots = [os.path.dirname(FOLDER), FOLDER]
    for r in roots:
        for p in glob.glob(os.path.join(r, "**", "*.xlsx"), recursive=True):
            if "backup" in p.lower() or ".seo-audit-work" in p or os.path.basename(p).startswith("~$"): continue
            if p.count(os.sep) - r.count(os.sep) > 2: continue
            try:
                wb = openpyxl.load_workbook(p, read_only=True)
                ok = sum(1 for ws in wb.worksheets if str(ws["A1"].value or "").strip().upper().startswith("SEO AUDIT CHECK LIST")) >= 1
                wb.close()
                if ok: return p
            except Exception:
                pass
    return None

# ---------------- answers ----------------
def n_urls(k): return len([u for u in ISS.get(k, {}).get("urls", {}) if u != "SITEWIDE"])
def nz(*pairs): return ", ".join(f"{n} {t}" for n, t in pairs if n)
STOP = {"in", "the", "a", "an", "and", "of", "for", "to", "with", "near", "me", "best", "ca"}
def no_kw_h1():
    n = 0
    for p in PAGES:
        h = (p.get("h1") or [""])[0].lower()
        terms = [w for w in re.findall(r"[a-z0-9]+", (CP.get(p["url"], {}).get("focus_keyword") or "").lower().split("(")[0]) if w not in STOP and len(w) > 2]
        if h and terms and not any(w in h for w in terms[:2]): n += 1
    return n
def has(k): return k in ISS
NM = "Needs manual check"
def psi_res(dev):
    m = PSI.get(dev) or {}
    p = m.get("performance")
    if p is None: return ("N/A", NM + " (no PageSpeed data provided)")
    p = float(p)
    return ("Pass", None) if p >= 90 else (("Need To Improve" if p >= 50 else "Fail"), f"{dev.capitalize()} PageSpeed {int(p)}, LCP {m.get('lcp')}, TBT {m.get('tbt')}")
def kw_in_url():
    hit = 0
    for p in PAGES:
        terms = [w for w in re.findall(r"[a-z0-9]+", (CP.get(p["url"], {}).get("focus_keyword") or "").lower()) if len(w) > 3]
        if terms and any(t in p["url"].lower() for t in terms[:2]): hit += 1
    r = hit / max(NP, 1)
    return ("Pass" if r >= .7 else "Need To Improve" if r >= .3 else "Fail"), (None if r >= .7 else f"{hit} of {NP} URLs contain their focus keyword")
def underscores():
    n = sum(1 for p in PAGES if "_" in path_of(p["url"], BASE))
    return ("Pass", None) if not n else ("Fail", f"{n} URLs use underscores")
def url_friendly():
    long_ = sum(1 for p in PAGES if len(p["url"]) > 115); bad = n_urls("url_format")
    return ("Pass", None) if not (long_ or bad) else ("Need To Improve", nz((long_, "URLs over 115 chars"), (bad, "URL format issues")))
def titles():
    miss, dup, lng, sht, caps = n_urls("title_missing"), n_urls("title_duplicate"), n_urls("title_long"), n_urls("title_short"), sum(1 for p in PAGES if is_caps(p.get("title") or ""))
    if not any((miss, dup, lng, sht, caps)): return ("Pass", None)
    parts = [nz((miss, "missing"), (dup, "duplicate"), (lng, "too long"), (sht, "too short"), (caps, "ALL CAPS"))]
    bad = miss + dup + lng + sht
    return ("Fail" if (miss or dup or bad > NP * .25) else "Need To Improve", ", ".join(parts) + " titles, see Meta Titles sheet")
def descs():
    miss, dup, oth = n_urls("desc_missing"), n_urls("desc_duplicate"), n_urls("desc_multiple") + n_urls("desc_short") + n_urls("desc_long")
    if not any((miss, dup, oth)): return ("Pass", None)
    return ("Fail" if miss > NP * .25 or dup else "Need To Improve", nz((miss, "missing"), (dup, "duplicate"), (oth, "other")) + " meta description issues, see Meta Descriptions sheet")
def dup_titles():
    n = n_urls("title_duplicate"); return ("Pass", None) if not n else ("Fail", f"{n} pages with duplicate title tags, need to be fixed")
def h1():
    m, mu, kw = n_urls("h1_missing"), n_urls("h1_multiple"), no_kw_h1()
    if not any((m, mu, kw)): return ("Pass", None)
    return ("Fail" if m > NP * .25 else "Need To Improve", nz((m, "pages missing H1"), (mu, "with multiple H1s"), (kw, "H1s without the focus keyword")) + ", see H1 & Headings sheet")
def images_opt():
    big = sum(1 for i in D.get("images", []) if (i.get("bytes") or 0) > 102400)
    return ("Pass", None) if not big else ("Fail" if big > 20 else "Need To Improve", f"{big} images over 100 KB, need compression")
def alt():
    n = sum(1 for i in D.get("images", []) if i.get("missing_alt"))
    return ("Pass", None) if not n else ("Fail", f"{n} images without ALT, need to be fixed")
def kw_mentions():
    return ("N/A", NM + " (keyword density per page)")
def orphan():
    o, s = n_urls("orphan"), n_urls("sitemap")
    return ("Pass", None) if not (o or s) else ("Need To Improve", nz((o, "weakly linked/orphan pages"), (s, "sitemap URLs not linked/crawled")))
def broken():
    n = len([l for l in D["links"].get("internal", []) if l["status"] >= 400])
    return ("Pass", None) if not n else ("Fail", f"{n} broken internal links found, need to be fixed")
def broken_all():
    i = len([l for l in D["links"].get("internal", []) if l["status"] >= 400]); e = len([l for l in D["links"].get("external", []) if l["status"] >= 400 or l["status"] == 0])
    return ("Pass", None) if not (i or e) else ("Fail" if i else "Need To Improve", nz((i, "broken internal"), (e, "external")) + " link issues found")
def thin():
    n = n_urls("thin_content"); return ("Pass", None) if not n else ("Need To Improve", f"{n} thin pages (low word count)")
def mobile():
    return ("Pass", None) if SITE.get("viewport", True) and not has("mobile") else ("Fail", "Mobile viewport/usability issues found")
def redirects():
    ch = n_urls("redirect_chain"); rl = len([l for l in D["links"].get("internal", []) if 300 <= l["status"] < 400])
    if ch: return ("Fail", f"{ch} redirect chains/loops")
    return ("Pass", None) if not rl else ("Need To Improve", f"{rl} links point to redirects")
def https():
    return ("Fail", "HTTPS / mixed content issues found") if has("https") or has("certificate") else ("Pass", None)
def analytics():
    tags = (D.get("stack") or {}).get("analytics") or []
    return ("N/A", NM + (f": tags found {', '.join(tags)}; confirm sessions in GA4" if tags else ": no analytics tag found on the homepage"))
def sitemap():
    files = (SITE.get("sitemap") or {}).get("files")
    if not files and not has("sitemap"): return ("N/A", NM)
    if not files: return ("Fail", "No XML sitemap found")
    return ("Pass", None) if not has("sitemap") else ("Need To Improve", f"{n_urls('sitemap')} sitemap issues (non-indexable / orphan URLs)")
def robots():
    rb = SITE.get("robots") or {}
    if rb.get("status") == 200 and not rb.get("disallow_all"): return ("Pass", None)
    return ("Fail", "robots.txt missing or blocking the site") if rb else ("N/A", NM)
def indexed():
    gsc = (CT.get("search_console") or {}).get("summary")
    return ("N/A", NM + f" in Google Search Console ({sum(1 for p in PAGES if str(p.get('indexability', 'Indexable')).startswith('Indexable'))} pages indexable)") if not gsc else ("Need To Improve", gsc)
def url_structure():
    r1, s1 = url_friendly(); r2, s2 = underscores()
    wrong = [f for f in CT.get("findings", []) if "slug" in f.get("issue", "").lower() or "url" in f.get("issue", "").lower()]
    if r1 == "Pass" and r2 == "Pass" and not wrong: return ("Pass", None)
    return ("Need To Improve", "; ".join(x for x in [s1, s2, f"{len(wrong)} URL/slug findings" if wrong else None] if x))

RULES = [
 ("primary keyword in the url", kw_in_url), ("url short and user-friendly", url_friendly), ("url used by a subdomain", lambda: ("Pass", None)),
 ("hyphens and not underscores", underscores), ("page title optimized", titles), ("meta description optimized", descs),
 ("duplicate title tags", dup_titles), ("h1 tag optimized", h1), ("images optimized", images_opt), ("mentioned at least 2", kw_mentions),
 ("orphan page", orphan), ("latent semantic", lambda: ("N/A", NM)), ("free of broken links", broken), ("page indexed", indexed),
 ("enough crawlable content", thin), ("page load fast", lambda: psi_res("mobile")), ("mobile-friendly/responsive", mobile),
 ("free of redirect issues", redirects), ("speed for desktop", lambda: psi_res("desktop")), ("speed for mobile", lambda: psi_res("mobile")),
 ("gtmetrix", lambda: ("N/A", NM + " (no GTmetrix data provided)")), ("broken link issues", broken_all), ("https/ssl", https),
 ("google analytics", analytics), ("ads on the page", lambda: ("N/A", NM)), ("make sure your pages are indexed", indexed),
 ("increase your page speed", lambda: psi_res("mobile")), ("make sure your pages are mobile", mobile), ("xml sitemap", sitemap),
 ("robots.txt", robots), ("optimize orphan", orphan), ("url structure", url_structure), ("optimize your images", alt),
]
OVR = {k.lower(): v for k, v in (CT.get("checklist_overrides") or {}).items()}
def answer(q):
    ql = re.sub(r"\s+", " ", q.lower())
    for k, v in OVR.items():
        if k in ql: return v[0], (v[1] if len(v) > 1 else None)
    for k, fn in RULES:
        if k in ql:
            r, s = fn(); return r, (None if r == "Pass" else s)
    return "N/A", NM + " (no data provided)"

# ---------------- write ----------------
def snapshot(wb, skip):
    out = {}
    for ws in wb.worksheets:
        if ws.title == skip: continue
        cells = [(c.coordinate, str(float(c.value)) if isinstance(c.value, (int, float)) and not isinstance(c.value, bool) else str(c.value), c.fill.fgColor.rgb if c.fill and c.fill.fill_type else None, c.font.b if c.font else None)
                 for row in ws.iter_rows() for c in row if c.value is not None or c.has_style]
        out[ws.title] = hashlib.md5(repr(cells).encode()).hexdigest() + str(sorted(map(str, ws.merged_cells.ranges)))
    return out

master = find_master()
if master:
    bk = os.path.splitext(master)[0] + f"_backup_{DATE.isoformat()}.xlsx"
    if not os.path.exists(bk): shutil.copy2(master, bk)
    wb = openpyxl.load_workbook(master)
    tabs = [ws for ws in wb.worksheets if is_checklist(ws)]
    src = wb[a.template_tab] if a.template_tab else tabs[-1]
    tab = (a.tab or CLIENT)[:31]
    if tab in wb.sheetnames:
        sys.exit(f"STOP: a tab named '{tab}' already exists in {master}. Pass --tab with another name.")
    before = snapshot(wb, tab); order = list(wb.sheetnames)
    ws = wb.copy_worksheet(src); ws.title = tab
    for k, v in src.row_dimensions.items(): ws.row_dimensions[k].height = v.height
    ws.sheet_view.showGridLines = src.sheet_view.showGridLines
    out_path = master
else:
    wb = openpyxl.load_workbook(TEMPLATE); src = wb["Template"]; ws = src; ws.title = (a.tab or CLIENT)[:31]
    out_path = os.path.join(FOLDER, f"{safe_name(CLIENT)}_SEO_Checklist_{DATE.isoformat()}.xlsx"); before = None

# locate rows by label
def find_row(label):
    for r in range(1, 80):
        if str(ws.cell(r, 1).value or "").strip().lower().startswith(label): return r
    return None
for lbl, val in (("website / client", CLIENT), ("website url", BASE + "/"), ("made by", MADE_BY or None)):
    r = find_row(lbl)
    if r: ws.cell(r, 2).value = val
r = find_row("date")
if r:
    ref = src.cell(r, 2).value
    if isinstance(ref, (datetime.date, datetime.datetime)): ws.cell(r, 2).value = datetime.datetime(DATE.year, DATE.month, DATE.day)
    else: ws.cell(r, 2).value = DATE.strftime("%d/%m/%y")
for row in ws.iter_rows():
    for c in row:
        if c.hyperlink is not None and c.column > 2: c.hyperlink = None
hdr = find_row(" types") or find_row("types") or 8
act = find_row("action required") or 60
qrows = []
for rr in range(hdr + 1, act):
    q = ws.cell(rr, 2).value
    for cc in (3, 4): ws.cell(rr, cc).value = None
    if q: qrows.append(rr)
for rr in qrows:
    res, sug = answer(str(ws.cell(rr, 2).value))
    ws.cell(rr, 3).value = res; ws.cell(rr, 4).value = sug
top = S.get("top") or [t.get("fix") for t in CT.get("top_fixes", [])]
steps = [rr for rr in range(act + 1, act + 15) if str(ws.cell(rr, 1).value or "").lower().startswith("step")]
for i, rr in enumerate(steps):
    ws.cell(rr, 2).value = top[i] if i < len(top) else None
# clear anything left below the steps (e.g. an old summary block copied from the template tab)
last = steps[-1] if steps else act
for row in ws.iter_rows(min_row=last + 1, max_row=ws.max_row):
    for c in row:
        if c.value is not None: c.value = None
for mr in [m for m in list(ws.merged_cells.ranges) if m.min_row > last]:
    ws.unmerge_cells(str(mr))
# overall summary block
start = last + 3
lab_ref, val_ref, hdr_ref = src.cell(steps[0] if steps else act, 1), src.cell(steps[0] if steps else act, 2), src.cell(act, 1)
br = S.get("beginner_rows", {})
lines = [("Overall Summary", None),
         ("Total Errors", br.get("Error / Critical", 0)), ("Total Warnings", br.get("Warning", 0)), ("Total Notices", br.get("Notice / Opportunity", 0)),
         ("Site Health Score", (f"{CT.get('semrush_overview', {}).get('site_health')}% (Semrush)" if CT.get("semrush_overview", {}).get("site_health") is not None else NM))]
lines += [("Top 5 Priority Fixes" if i == 0 else "", f"{i + 1}) {t}") for i, t in enumerate(top[:5])]
lines += [("Note", "Full details: " + (S.get("beginner_file") or "see the Full SEO Audit Report"))]
for i, (k, v) in enumerate(lines):
    rr = start + i
    ca, cb = ws.cell(rr, 1), ws.cell(rr, 2)
    ca._style = copy((hdr_ref if i == 0 else lab_ref)._style); ca.value = k or None
    if i: cb._style = copy(val_ref._style); cb.value = v
wb.save(out_path)

# verify
wb2 = openpyxl.load_workbook(out_path)
t2 = wb2[ws.title]
ok_res = all(t2.cell(rr, 3).value in ("Pass", "Fail", "Need To Improve", "N/A") for rr in qrows)
ok_pass = all(t2.cell(rr, 4).value in (None, "") for rr in qrows if t2.cell(rr, 3).value == "Pass")
print("CHECKLIST:", out_path, "| tab:", ws.title, "| questions:", len(qrows), "| results valid:", ok_res, "| Pass rows w/o suggestion:", ok_pass)
if before is not None:
    changed = [n for n, h in snapshot(wb2, ws.title).items() if before.get(n) != h]
    print("other tabs changed:", changed or "none", "| backup:", bk)
