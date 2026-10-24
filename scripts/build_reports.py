"""Build the Beginner and/or Expert audit workbooks from audit_data.json + content.json.

Usage: python build_reports.py <client_folder> [--mode beginner|expert|both] [--made-by "Name"] [--out <dir>]
"""
import os, sys, re, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (ensure_deps, work_dir, load_json, path_of, host_of, norm_img, is_caps, isnan, safe_name, write_table, fill, border,
                    SEVERITIES, SEV_ORDER, PRI_ORDER, NAVY, FIX, SEV_FILL)
ensure_deps()
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, Alignment
from openpyxl.formatting.rule import CellIsRule
import catalog as C
import fixes as FX

E, W, N = "Error / Critical", "Warning", "Notice / Opportunity"
ap = argparse.ArgumentParser()
ap.add_argument("folder"); ap.add_argument("--mode", default="both"); ap.add_argument("--made-by", default=None); ap.add_argument("--out", default=None)
a = ap.parse_args()
FOLDER = os.path.abspath(a.folder); WD = work_dir(FOLDER)
D = load_json(os.path.join(WD, "audit_data.json")); CT = load_json(os.path.join(WD, "content.json"))
if D is None or CT is None:
    sys.exit("audit_data.json or content.json missing - run collect.py and write content.json first")
BASE = D["meta"]["base"]; DOMAIN = D["meta"]["domain"]
CL = CT.get("client", {}); CLIENT = CL.get("name") or DOMAIN
MADE_BY = a.made_by or CL.get("made_by") or ""
DATE = CL.get("date") or D["meta"]["collected"]
OUT = a.out or FOLDER
ST = D.get("stack", {}) or {}
CTX = {"cms": ST.get("cms", "Unknown"), "seo_plugin": ST.get("seo_plugin"), "builder": ST.get("builder"), "domain": DOMAIN, "cdn": ST.get("cdn")}
PAGES = D["pages"]; PM = {p["url"]: p for p in PAGES}; NP = len(PAGES)
CP = CT.get("pages", {})
P = lambda u: path_of(u, BASE)
HOME = BASE + "/"
SEM = D.get("semrush") or {}
PSI = CT.get("psi") or {}

# ------------------------------------------------------------------ issues
ISS = {k: dict(v) for k, v in D["issues"].items()}
for v in ISS.values():
    v["urls"] = {u: list(s) for u, s in v["urls"].items()}

def add(key, title, sev, pri, eff, urls, source, why, fix_b, fix_e, data="", group="Other"):
    it = ISS.setdefault(key, dict(id=key, title=title, severity=sev, priority=pri, effort=eff, group=group, why=why, fix_key=None,
                                  fix_expert=fix_e, urls={}, counts={}, tool_names=[], notes=[], targets=[]))
    it["fix_beginner_text"] = fix_b; it["data"] = data
    for u in urls: it["urls"].setdefault(u, []); src = it["urls"][u]; src.append(source) if source not in src else None

# PageSpeed-derived issues
def num(x):
    try:
        return float(str(x).replace(",", "").replace("s", "").replace("ms", "").strip())
    except Exception:
        return None
for dev in ("mobile", "desktop"):
    m = PSI.get(dev) or {}
    perf = num(m.get("performance"))
    if perf is None: continue
    dd = f"Perf {int(perf)} · FCP {m.get('fcp')} · LCP {m.get('lcp')} · TBT {m.get('tbt')} · CLS {m.get('cls')} · SI {m.get('si')}"
    if m.get("lcp_element"): dd += f" · LCP element: {m['lcp_element']}"
    if perf < 90:
        add(f"psi_{dev}", f"{dev.capitalize()} PageSpeed performance {int(perf)}/100", E if perf < 50 else W, "High" if perf < 50 or dev == "mobile" else "Medium",
            "Hard", [HOME], "PageSpeed Insights", "Slow pages rank lower (Core Web Vitals) and lose visitors before the page appears.",
            FX.render("speed", CTX), "Fix LCP element render, defer/delay JS, remove unused CSS/JS, compress images", dd, "Performance")
    tbt = num(m.get("tbt"))
    if tbt and tbt > 600 and dev == "mobile":
        add("psi_tbt", f"Total Blocking Time {m.get('tbt')} (goal < 200 ms)", W, "High", "Hard", [HOME], "PageSpeed Insights",
            "Long JavaScript tasks block taps and scrolling.", FX.render("speed", CTX), "Delay non-critical JS; unload unused widgets/plugins", m.get("notes", ""), "Performance")
    kib = num(m.get("payload_kib"))
    if kib and kib > 4000 and dev == "mobile":
        add("psi_weight", f"Heavy page: {m.get('payload_kib')} KiB", W, "High", "Medium", [HOME], "PageSpeed Insights",
            "Large pages are slow on mobile data.", FX.render("img_compress", CTX), "Compress images; remove unused JS/CSS",
            f"Unused JS {m.get('unused_js_kib')} KiB · render-blocking {m.get('render_blocking_ms')} ms", "Performance")
if PSI and not any((PSI.get(x) or {}).get("performance") is not None for x in ("mobile", "desktop")):
    add("psi_missing", "PageSpeed not measured", N, "Medium", "Easy", [HOME], "—", "Speed is a ranking factor.",
        "Needs manual check: run pagespeed.web.dev for mobile and desktop and add screenshots to the folder.", "Run PSI", "", "Performance")
if PSI.get("field_data") and "no data" in str(PSI.get("field_data")).lower():
    add("crux", "No real-user Core Web Vitals data (CrUX)", N, "Low", "Easy", [HOME], "PageSpeed Insights", "Google has too little real-user data for this site.",
        "Verify the site in Google Search Console and watch the Core Web Vitals report.", "Monitor in GSC", "", "Performance")

# analysis-based checks (need focus keywords)
STOP = {"in", "the", "a", "an", "and", "of", "for", "to", "with", "near", "me", "best", "&", "ca", "-"}
def kw_terms(k):
    return [w for w in re.findall(r"[a-z0-9]+", (k or "").lower().split("(")[0]) if w not in STOP and len(w) > 2]
caps_t, nokw_h1, caps_h1 = [], [], []
for p in PAGES:
    t = p.get("title") or ""; h = (p.get("h1") or [""])[0]
    if t and is_caps(t): caps_t.append(p["url"])
    if h and is_caps(h): caps_h1.append(p["url"])
    terms = kw_terms(CP.get(p["url"], {}).get("focus_keyword"))
    if h and terms and not any(w in h.lower() for w in terms[:2]): nokw_h1.append(p["url"])
if caps_t:
    add("title_caps", "Title written in ALL CAPS", N, "Low", "Easy", caps_t, "Analysis", "ALL-CAPS titles look like shouting in search results and get fewer clicks.",
        FX.render("title", CTX), "Sentence/title case (see 'Meta Titles')", group="Titles")
if nokw_h1:
    add("h1_keyword", "H1 does not contain the focus keyword", N, "Medium", "Easy", nokw_h1, "Analysis", "The H1 is a strong relevance signal; generic H1s ('ABOUT US', slogans) waste it.",
        FX.render("h1", CTX), "Keyword H1 (see 'H1 & Headings')", group="Headings")

# Claude's findings
for i, f in enumerate(CT.get("findings", [])):
    urls = f.get("urls") or [HOME]
    if urls in ("site-wide", ["site-wide"]): urls = ["SITEWIDE"]
    add(f"finding_{i}", f["issue"], f.get("severity", N), f.get("priority", "Medium"), f.get("effort", "Easy"), urls, f.get("source", "Live check"),
        f.get("why", ""), f.get("fix", ""), f.get("fix_expert", f.get("fix", "")), f.get("data", ""), f.get("group", "Other"))

def fix_b(it):
    if it.get("fix_beginner_text"): return it["fix_beginner_text"]
    if "cloudflare_email" in it.get("notes", []) and it["id"] == "internal_4xx":
        return ("These links are created by Cloudflare 'Email Address Obfuscation' (it rewrites mailto: links to /cdn-cgi/l/email-protection, which returns 404 to crawlers). "
                "Cloudflare dashboard > Scrape Shield > turn OFF 'Email Address Obfuscation' (or show the email as plain text / use a contact form). Then re-crawl.")
    return FX.render(it.get("fix_key") or "generic", CTX)

def fix_e(it):
    if "cloudflare_email" in it.get("notes", []) and it["id"] == "internal_4xx":
        return "Disable Cloudflare Scrape Shield › Email Obfuscation (links to /cdn-cgi/l/email-protection 404)"
    return it.get("fix_expert") or "See tool guidance"

def sources(it):
    s = set()
    for v in it["urls"].values(): s.update(v)
    s.update(it.get("counts", {}).keys())
    order = ["SF", "Semrush", "Live crawl", "Live check", "PageSpeed Insights", "Analysis"]
    return " + ".join(sorted(s, key=lambda x: order.index(x) if x in order else 9)) or "—"

for it in ISS.values():
    if it["severity"] not in SEVERITIES: it["severity"] = N
    if it["priority"] not in PRI_ORDER: it["priority"] = "Low"
ISSUES = sorted(ISS.values(), key=lambda x: (SEV_ORDER[x["severity"]], PRI_ORDER[x["priority"]], x["title"]))

# ------------------------------------------------------------------ evidence helpers
IMGS = D.get("images", [])
IMG_BY_PAGE = collections.defaultdict(list)
for im in IMGS:
    for pg in im.get("pages", []): IMG_BY_PAGE[pg].append(im)
LINKS = D.get("links", {})
LINK_BY_SRC = collections.defaultdict(list)
for kind in ("internal", "external"):
    for l in LINKS.get(kind, []): LINK_BY_SRC[l["source"]].append(dict(l, kind=kind))

def evidence(it, u):
    p = PM.get(u, {}); k = it["id"]
    if k.startswith("title"): return f"{p.get('title_len', len(p.get('title') or ''))} chars" + (f" / {p['title_px']} px" if p.get("title_px") else "") + f": '{p.get('title', '')}'"
    if k == "desc_multiple": return f"2nd description: '{p.get('desc2', '')}'"
    if k.startswith("desc"): return f"{p.get('desc_len', 0)} chars: '{(p.get('desc') or '')[:90]}'" if p.get("desc") else "No meta description"
    if k.startswith("h1"): return " | ".join(p.get("h1") or []) or "No H1"
    if k == "h2_issues": return "H2s: " + (" | ".join(p.get("h2") or []) or "none")
    if k in ("thin_content", "text_ratio"): return f"{p.get('words', '?')} words · text ratio {p.get('text_ratio', '?')}%" + (f" · {p['html_words']} words in raw HTML" if p.get("html_words") else "")
    if k == "img_alt_missing": return f"{sum(1 for i in IMG_BY_PAGE.get(u, []) if i.get('missing_alt'))} image(s) without alt text"
    if k == "img_large":
        big = [i for i in IMG_BY_PAGE.get(u, []) if (i.get("bytes") or 0) > 102400]
        return f"{len(big)} image(s) over 100 KB; largest {max((i['bytes'] for i in big), default=0) // 1024} KB" if big else "Image(s) over 100 KB"
    if k in ("internal_4xx", "internal_3xx", "redirect_chain", "external_errors"):
        want = {"internal_4xx": lambda l: l["kind"] == "internal" and l["status"] >= 400, "internal_3xx": lambda l: l["kind"] == "internal" and 300 <= l["status"] < 400,
                "redirect_chain": lambda l: l["kind"] == "internal" and 300 <= l["status"] < 400, "external_errors": lambda l: l["kind"] == "external"}[k]
        ls = [l for l in LINK_BY_SRC.get(u, []) if want(l)]
        return "; ".join(f"{P(l['target']) if l['kind'] == 'internal' else l['target']} ({l['status']})" for l in ls[:3]) or ", ".join(it.get("targets", [])[:3])
    if it.get("data"): return it["data"]
    return "; ".join(it.get("tool_names", [])[:2])

HTMLSET = set(PM)
def url_rows(it):
    urls = list(it["urls"].items())
    html_urls = [(u, s) for u, s in urls if u in HTMLSET]
    other = [(u, s) for u, s in urls if u not in HTMLSET]
    if any(u == "SITEWIDE" for u, _ in urls) or (NP >= 10 and len(html_urls) >= 0.9 * NP):
        src = sorted({x for _, s in urls for x in s})
        return [(f"All {NP} HTML pages (site-wide)", " + ".join(src), it.get("data") or "; ".join(it.get("tool_names", [])[:3]))]
    rows = [(u, " + ".join(s), evidence(it, u)) for u, s in html_urls]
    if len(other) > 15:
        rows.append((f"{len(other)} non-HTML URLs (images/files)", " + ".join(sorted({x for _, s in other for x in s})), "; ".join(P(u) for u, _ in other[:5]) + " ..."))
    else:
        rows += [(u, " + ".join(s), it.get("data") or "; ".join(it.get("tool_names", [])[:2])) for u, s in other if u != "SITEWIDE"]
    if not rows:
        rows = [(f"{DOMAIN} (site-level)", sources(it), it.get("data") or "; ".join(it.get("tool_names", [])[:3]))]
    return rows

def affected(it):
    urls = [u for u in it["urls"] if u != "SITEWIDE"]
    html_urls = [u for u in urls if u in HTMLSET]
    if "SITEWIDE" in it["urls"] or (NP >= 10 and len(html_urls) >= 0.9 * NP): return "All", "All pages"
    show = html_urls + [u for u in urls if u not in HTMLSET]
    if not show: return "Site", DOMAIN
    lst = ", ".join(P(u) for u in show[:60]) + (f" … (+{len(show) - 60})" if len(show) > 60 else "")
    return len(show), lst

def data_summary(it):
    parts = []
    nc = it.get("name_counts", {})
    if nc:
        for tool in ("SF", "Semrush"):
            xs = [f"{k.split('|', 1)[1].split(': ', 1)[-1]} {v}" for k, v in nc.items() if k.startswith(tool + "|")]
            if xs: parts.append(" · ".join(xs) + f" ({tool})")
    if it["id"] == "img_alt_missing":
        parts.append(f"{len(idx)} images need alt text in total ({sum(1 for i in idx if i.get('pages'))} used on crawled pages)")
    if it["id"] == "img_large":
        big = [i for i in IMGS if (i.get("bytes") or 0) > 102400]
        if big: parts.append(f"{len(big)} files >100 KB · {sum(1 for i in big if i['bytes'] > 512000)} >500 KB · largest {max(i['bytes'] for i in big) // 1024} KB")
    if it.get("data"): parts.append(it["data"])
    if it["id"].startswith("title") and it["id"] != "title_missing":
        lens = [PM[u]["title_len"] for u in it["urls"] if u in PM and PM[u].get("title_len")]
        if lens: parts.append(f"{min(lens)}–{max(lens)} chars")
    return " · ".join(parts)

# ------------------------------------------------------------------ page sheets data
dup_titles = {t for t in [p.get("title") for p in PAGES] if t and [q.get("title") for q in PAGES].count(t) > 1}
dup_desc = {t for t in [p.get("desc") for p in PAGES] if t and [q.get("desc") for q in PAGES].count(t) > 1}
H2ISS = set(ISS.get("h2_issues", {}).get("urls", {}))
def title_problem(p, short=False):
    t = p.get("title") or ""; out = []
    if not t: out.append("missing")
    if len(t) > 60: out.append(">60" if short else f"Too long ({len(t)} chars)")
    if p.get("title_px", 0) > 561: out.append(">561px" if short else f"over 561 px ({p['title_px']} px)")
    if t and len(t) < 30: out.append("<30" if short else f"Too short ({len(t)} chars)")
    if t in dup_titles: out.append("duplicate")
    if t and is_caps(t): out.append("ALL CAPS")
    terms = kw_terms(CP.get(p["url"], {}).get("focus_keyword"))
    if t and terms and not any(w in t.lower() for w in terms[:2]): out.append("no focus keyword" if not short else "no keyword")
    return ", ".join(out) or ("keyword placement" if short else "Length OK; rewritten to lead with the focus keyword")
def desc_problem(p, short=False):
    d = p.get("desc") or ""; out = []
    if not d: return "missing" if short else "Missing (Google writes its own snippet)"
    if p.get("desc2"): out.append("multiple" if short else "Two meta descriptions output (theme + SEO plugin)")
    if len(d) > 160: out.append(f"long ({len(d)})")
    if len(d) < 140: out.append(f"short ({len(d)})")
    if d in dup_desc: out.append("duplicate")
    if not re.search(r"\b(call|contact|book|get|request|read|learn|see|start|schedule|shop|order|visit|try)\b", d, re.I): out.append("no CTA")
    return ", ".join(out) or "OK"
def h1_problem(p, short=False):
    h = p.get("h1") or []; out = []
    if not h: return "missing" if short else "Missing H1"
    if len(h) > 1: out.append("multiple")
    if len(h[0]) > 70: out.append(">70")
    if is_caps(h[0]): out.append("ALL CAPS")
    if p["url"] in nokw_h1: out.append("no keyword" if short else "No focus keyword")
    if h[0].strip().lower() == (p.get("title") or "").split(" - ")[0].split(" | ")[0].strip().lower(): out.append("= title")
    return ", ".join(out) or "OK"

def kwshort(k): return (k or "").split(" (")[0]

# ------------------------------------------------------------------ images
idx = load_json(os.path.join(WD, "img_index.json"), [])
ALTS = CT.get("alts", {})
ALT_BY_URL = {i["url"]: (ALTS.get(str(i["n"])) or "").strip() for i in idx}
def alt_text(u):
    v = ALT_BY_URL.get(norm_img(u), "")
    return "Keep alt empty (decorative)" if v == "DECORATIVE" else (v or "Needs manual check")

# ------------------------------------------------------------------ links
def link_fix(l, short=False):
    st, tgt, fin = l["status"], l["target"], l.get("final") or ""
    if "/cdn-cgi/l/email-protection" in tgt:
        return "Disable Cloudflare Email Obfuscation" if short else fix_b({"id": "internal_4xx", "notes": ["cloudflare_email"]})
    if l["kind"] == "internal":
        if 300 <= st < 400: return f"Link to {P(fin) if fin else 'final URL'}" if short else f"Change the link to {fin or 'the final URL'}. " + FX.render("redirect_links", CTX)
        return "Fix/remove link or 301 the URL" if short else FX.render("broken", CTX)
    if 300 <= st < 400: return "Link to final URL" if short else f"Update the link to the final URL: {fin}"
    return "Manual check (bot-blocked?)" if short else FX.render("external", CTX)
def link_type(l):
    if l["kind"] == "internal": return "Internal redirect" if 300 <= l["status"] < 400 else ("Broken internal link" if l["status"] >= 400 else "Internal (no response)")
    return "External redirect" if 300 <= l["status"] < 400 else ("External error" if l["status"] >= 400 else "External (no response / timeout)")

# ------------------------------------------------------------------ technical / schema / opps
TECH = D.get("technical", [])
EXPERT_ACTION = {"headers": "HSTS + security headers (CDN/server)", "robots": "Fix robots.txt", "sitemap": "Sitemap = indexable linked URLs only", "https": "Force HTTPS 301",
                 "llms": "Publish llms.txt", "noindex": "Review noindex", "canonical": "Self-canonical on indexable pages", "schema": "Add LocalBusiness/Organization JSON-LD"}
def psi_rows():
    rows = []
    for dev in ("mobile", "desktop"):
        m = PSI.get(dev) or {}
        if m.get("performance") is None:
            rows.append({"area": f"PageSpeed ({dev})", "finding": "Not measured", "status": "Manual check", "source": "—", "evidence": "", "fix_key": "speed"}); continue
        perf = num(m["performance"])
        rows.append({"area": f"PageSpeed ({dev})", "finding": f"Performance {m.get('performance')} · Accessibility {m.get('accessibility')} · Best Practices {m.get('best_practices')} · SEO {m.get('seo')} | "
                     f"FCP {m.get('fcp')} · LCP {m.get('lcp')} · TBT {m.get('tbt')} · CLS {m.get('cls')} · SI {m.get('si')}",
                     "status": "OK" if (perf or 0) >= 90 else "Issue", "source": PSI.get("source") or "PageSpeed Insights", "evidence": m.get("notes", ""), "fix_key": "speed"})
    if PSI.get("field_data"):
        rows.append({"area": "Core Web Vitals (field)", "finding": PSI["field_data"], "status": "Manual check" if "no data" in PSI["field_data"].lower() else "Info", "source": "PageSpeed Insights", "evidence": "", "fix_key": None})
    return rows
TECH_ALL = TECH + psi_rows()

def schema_rows():
    rows = []
    sd = {s["url"]: s for s in SEM.get("structured", [])}
    me = SEM.get("markup_errors")
    for u in sorted(set(sd) | set(PM)):
        s = sd.get(u, {}); items = ", ".join(s.get("items", [])) or "none"
        rows.append((u, "Yes" if s.get("jsonld") else ("—" if not s else "No"), "Yes" if s.get("microdata") else ("—" if not s else "No"), items,
                     f"{me[0]}/{me[1]} pages with errors (Semrush)" if me else "—"))
    return rows
SCHEMA = CT.get("schema", {}) or {}
OPPS = CT.get("opportunities", []); ILINKS = CT.get("internal_links", [])
TOP = CT.get("top_fixes", []) or [{"fix": it["title"], "why": it["why"], "severity": it["severity"], "effort": it["effort"], "issue_id": it["id"]} for it in ISSUES[:10]]

def top_how(t):
    if t.get("how"): return t["how"]
    iid = t.get("issue_id")
    if iid and iid in ISS: return fix_b(ISS[iid])
    if t.get("fix_key"): return FX.render(t["fix_key"], CTX)
    return "See 'All Issues'."

def summary_metrics():
    so = CT.get("semrush_overview") or {}
    tot = SEM.get("totals") or {}
    m = []
    m.append(("HTML pages (200)", str(NP)))
    if SEM.get("urls"): m.append(("URLs in Semrush audit", str(SEM["urls"])))
    if so.get("site_health") is not None: m.append(("Semrush Site Health", f"{so['site_health']}%"))
    if so.get("ai_search_health") is not None: m.append(("Semrush AI Search Health", f"{so['ai_search_health']}%"))
    if tot: m.append(("Semrush errors / warnings / notices", f"{tot.get('errors')} / {tot.get('warnings')} / {tot.get('notices')}"))
    if so.get("thematic"): m.append(("Semrush thematic scores", so["thematic"]))
    for dev in ("mobile", "desktop"):
        x = PSI.get(dev) or {}
        if x.get("performance") is not None:
            m.append((f"PageSpeed {dev}", f"Perf {x['performance']} · A11y {x.get('accessibility')} · BP {x.get('best_practices')} · SEO {x.get('seo')} · LCP {x.get('lcp')} · TBT {x.get('tbt')} · CLS {x.get('cls')}"))
        else:
            m.append((f"PageSpeed {dev}", "Needs manual check (no PageSpeed data in folder)"))
    br = [l for l in LINKS.get("internal", []) if l["status"] >= 400]
    rd = [l for l in LINKS.get("internal", []) if 300 <= l["status"] < 400]
    m.append(("Broken internal links", f"{len(br)} links on {len({l['source'] for l in br})} pages"))
    m.append(("Links to redirects", str(len(rd))))
    m.append(("CMS / stack", " · ".join(x for x in [ST.get("cms"), ST.get("seo_plugin"), ST.get("builder"), ST.get("cdn")] if x)))
    return m

def sources_line():
    s = []
    src = D["meta"]["sources"]
    if src.get("screaming_frog"): s.append("Screaming Frog crawl")
    elif D["meta"]["mode"] == "live": s.append("live crawl (no Screaming Frog export)")
    if src.get("semrush"): s.append("Semrush Site Audit")
    if any((PSI.get(x) or {}).get("performance") is not None for x in ("mobile", "desktop")): s.append("PageSpeed Insights")
    if CT.get("search_console", {}).get("striking_distance"): s.append("Google Search Console")
    s.append("live site checks")
    return " + ".join(s) + f" · {DATE}" + (f" · Prepared by {MADE_BY}" if MADE_BY else "")

# ================================================================== BEGINNER
def build_beginner(path):
    wb = Workbook(); ws = wb.active; ws.title = "Summary"; B = border()
    ws["A1"] = f"{CLIENT} ({DOMAIN}): Full SEO Audit, {DATE}"; ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    ws["A2"] = "Sources: " + sources_line()
    r = 4; ws.cell(r, 1, "Health overview").font = Font(bold=True, size=12, color=NAVY); r += 1
    for k, v in summary_metrics(): ws.cell(r, 1, k); ws.cell(r, 2, v); r += 1
    rows_all = []
    for it in ISSUES:
        for u, src, ev in url_rows(it):
            rows_all.append([u, it["title"], it["severity"], src, it["priority"], it["effort"], it.get("why", ""), fix_b(it), ev])
    r += 1; ws.cell(r, 1, "Issues by severity (rows in 'All Issues')").font = Font(bold=True, size=12, color=NAVY); r += 1
    sc = collections.Counter(x[2] for x in rows_all)
    SUMMARY["beginner_rows"] = dict(sc); SUMMARY["beginner_file"] = os.path.basename(path)
    for s in SEVERITIES: ws.cell(r, 1, s).fill = fill(SEV_FILL[s]); ws.cell(r, 2, sc[s]); r += 1
    ws.cell(r, 1, "TOTAL issue rows").font = Font(bold=True); ws.cell(r, 2, len(rows_all)); r += 2
    ws.cell(r, 1, "Issues by priority").font = Font(bold=True, size=12, color=NAVY); r += 1
    pc = collections.Counter(x[4] for x in rows_all)
    for s in ("High", "Medium", "Low"): ws.cell(r, 1, s); ws.cell(r, 2, pc[s]); r += 1
    r += 1; ws.cell(r, 1, "Top 10 priority fixes").font = Font(bold=True, size=12, color=NAVY); r += 1
    for i, h in enumerate(["#", "Fix", "Why", "Severity", "Effort", "✅ How to fix (beginner steps)"], 1):
        c = ws.cell(r, i, h); c.fill = fill(NAVY); c.font = Font(bold=True, color="FFFFFF"); c.border = B
    for n, t in enumerate(TOP[:10], 1):
        r += 1
        vals = [n, t.get("fix"), t.get("why", ""), t.get("severity", W), t.get("effort", ""), top_how(t)]
        for i, v in enumerate(vals, 1):
            c = ws.cell(r, i, v); c.alignment = Alignment(wrap_text=True, vertical="top"); c.border = B
        ws.cell(r, 4).fill = fill(SEV_FILL.get(vals[3], "FFFFFF")); ws.cell(r, 6).fill = fill(FIX)
    for col, w in zip("ABCDEF", (52, 48, 50, 20, 10, 110)): ws.column_dimensions[col].width = w
    ws.freeze_panes = "A4"

    write_table(wb.create_sheet("All Issues"), ["URL", "Issue", "Severity", "Source", "Priority", "Effort", "Why it matters", "✅ How to fix (beginner steps)", "Evidence / data"],
                rows_all, [55, 42, 18, 18, 10, 9, 55, 90, 45], fix_cols=("✅ How to fix (beginner steps)",), sev_col="Severity", pri_col="Priority")
    mt, md, hh = [], [], []
    for p in PAGES:
        c = CP.get(p["url"], {})
        mt.append([p["url"], c.get("focus_keyword"), p.get("title") or "(missing)", len(p.get("title") or ""), p.get("title_px") or "", title_problem(p), c.get("title"), len(c.get("title") or "")])
        md.append([p["url"], c.get("focus_keyword"), p.get("desc") or "(missing)", len(p.get("desc") or ""), p.get("desc2") or "", desc_problem(p), c.get("description"), len(c.get("description") or "")])
        hh.append([p["url"], c.get("focus_keyword"), " | ".join(p.get("h1") or []) or "(none)", h1_problem(p), c.get("h1"), " | ".join((p.get("h2") or [])[:3]) or "(none)", c.get("h2_note") or "OK"])
    write_table(wb.create_sheet("Meta Titles"), ["URL", "Focus Keyword", "Current Title", "Length", "Pixels", "Problem", "✅ Fixed Title", "New Length"], mt,
                [55, 32, 50, 8, 8, 40, 60, 10], fix_cols=("✅ Fixed Title", "New Length"))
    write_table(wb.create_sheet("Meta Descriptions"), ["URL", "Focus Keyword", "Current Description", "Length", "2nd description (duplicate tag)", "Problem", "✅ Fixed Description", "New Length"], md,
                [55, 32, 60, 8, 30, 40, 75, 10], fix_cols=("✅ Fixed Description", "New Length"))
    write_table(wb.create_sheet("H1 & Headings"), ["URL", "Focus Keyword", "Current H1", "Problem", "✅ Fixed H1", "Current H2s (first 3)", "✅ H2 fix"], hh,
                [55, 32, 45, 35, 55, 55, 60], fix_cols=("✅ Fixed H1", "✅ H2 fix"))
    ia = []
    for i in idx:
        im = next((x for x in IMGS if x["url"] == i["url"]), {})
        kb = (i.get("bytes") or 0) // 1024 if i.get("bytes") else ""
        prob = 'Empty alt text (alt="")' + (f"; file {kb} KB (over 100 KB): compress" if kb and kb > 100 else "")
        src = " + ".join(im.get("sources", [])) or "—"
        pages_ = i.get("pages") or []
        if pages_:
            for pg in pages_: ia.append([pg, i["url"], "(empty)", prob, alt_text(i["url"]), kb, src])
        else:
            ia.append([f"Media Library only (attached to {i.get('parent') or 'no page'})", i["url"], "(empty)", prob, alt_text(i["url"]), kb, src])
    for im in IMGS:
        if not im.get("missing_alt") and (im.get("bytes") or 0) > 102400:
            for pg in (im.get("pages") or ["Media Library"]):
                ia.append([pg, im["url"], im.get("alt") or "", f"File {im['bytes'] // 1024} KB (over 100 KB): compress", "Alt OK: keep current alt", im["bytes"] // 1024, " + ".join(im.get("sources", []))])
    wsI = wb.create_sheet("Image Alt Text")
    write_table(wsI, ["Page URL", "Image URL", "Current Alt", "Problem", "✅ Fixed Alt Text", "File size (KB)", "Source"], ia, [45, 70, 20, 40, 70, 12, 18], fix_cols=("✅ Fixed Alt Text",))
    bl = []
    for kind in ("internal", "external"):
        for l in LINKS.get(kind, []):
            l = dict(l, kind=kind)
            st = f"{l['status']}" + (f" > {l.get('final')}" if l.get("final") else "")
            bl.append([l["source"], l["target"], st, link_type(l), link_fix(l)])
    for b_ in LINKS.get("blocked_external", []):
        if b_.get("inlinks"): bl.append([f"{b_['inlinks']} page(s)", b_["target"], "Blocked by the other site's robots.txt", "External (not checkable)", "Needs manual check: open the link in a browser."])
    for k, v in (D.get("site", {}).get("variants") or {}).items():
        bl.append([v.get("url"), v.get("location") or "", str(v.get("status")), "HTTP > HTTPS redirect" if k == "http" else "www / non-www redirect",
                   "OK, no action needed." if v.get("status") in (301, 308) else "Add a 301 redirect to the main https:// address. " + FX.render("https", CTX)])
    write_table(wb.create_sheet("Broken Links & Redirects"), ["Source URL", "Target URL", "Status", "Type", "✅ Fix"], bl, [50, 70, 28, 28, 90], fix_cols=("✅ Fix",))
    ts = [[t["area"], DOMAIN, t["finding"], t["status"], t.get("source", ""), t.get("evidence", ""),
           (FX.render(t["fix_key"], CTX) if t.get("fix_key") and t["status"] not in ("OK", "Info", "N/A") else "No action needed.")] for t in TECH_ALL]
    for u, pi in sorted((SEM.get("page_info") or {}).items()):
        if u in PM:
            ts.append(["Page speed (per page)", u, f"HTML load {pi.get('Page (HTML) Load Time, sec')} s · {pi.get('JS and CSS Number')} JS/CSS files ({pi.get('JS and CSS Size, KB')} KB)",
                       "Info", "Semrush", f"crawl depth {pi.get('Crawl Depth')} · incoming internal links {pi.get('Incoming Internal Links')}", "See 'All Issues' for speed fixes."])
    write_table(wb.create_sheet("Technical SEO"), ["Area", "URL / Scope", "Finding", "Status", "Source", "Evidence", "✅ Fix (beginner steps)"], ts,
                [22, 40, 70, 14, 18, 45, 90], fix_cols=("✅ Fix (beginner steps)",), status_col="Status")
    sd = []
    for u, j, mi, items, err in schema_rows():
        need = u in (HOME,) or any(x in u for x in ("contact", "about"))
        prob = "No LocalBusiness/Organization details" if need and SCHEMA.get("jsonld") else ("No structured data" if j == "No" else "No errors")
        sd.append([u, j, mi, items, err, prob, FX.render("schema", CTX) if need and SCHEMA.get("jsonld") else "No action needed."])
    if SCHEMA.get("jsonld"):
        sd.append([f"Recommended: {SCHEMA.get('type') or 'LocalBusiness'} (site-wide)", "-", "-", "-", "-", SCHEMA.get("notes", ""), FX.render("schema", CTX) + "\n\nJSON-LD:\n" + SCHEMA["jsonld"]])
    write_table(wb.create_sheet("Structured Data"), ["URL", "JSON-LD", "Microdata", "Schema items (Semrush)", "Markup errors", "Problem", "✅ Fix / Recommendation"], sd,
                [55, 9, 10, 35, 25, 45, 90], fix_cols=("✅ Fix / Recommendation",))
    op = [[o.get("type"), o.get("area"), o.get("opportunity"), o.get("why", ""), o.get("action", ""), o.get("priority", "Medium"), o.get("effort", "Medium")] for o in OPPS]
    op += [["Internal linking", l["from"], f"Link to {l['to']} with anchor '{l['anchor']}'", l.get("why", "Pass authority to a weakly linked page"),
            FX.render("internal_link", CTX), l.get("priority", "Medium"), "Easy"] for l in ILINKS]
    write_table(wb.create_sheet("Opportunities"), ["Type", "Page / Area", "Opportunity", "Why", "✅ Action steps", "Priority", "Effort"], op,
                [18, 50, 50, 50, 90, 10, 9], fix_cols=("✅ Action steps",), pri_col="Priority")
    gsc = CT.get("search_console") or {}
    if gsc.get("striking_distance") or gsc.get("low_ctr_pages"):
        rows = [["Striking distance", x.get("query"), x.get("page"), x.get("clicks"), x.get("impressions"), x.get("ctr"), x.get("position"), x.get("action")] for x in gsc.get("striking_distance", [])]
        rows += [["Low CTR page", x.get("query", ""), x.get("page"), x.get("clicks"), x.get("impressions"), x.get("ctr"), x.get("position"), x.get("action")] for x in gsc.get("low_ctr_pages", [])]
        write_table(wb.create_sheet("Search Console"), ["Type", "Query", "Page", "Clicks", "Impressions", "CTR", "Position", "✅ Action"], rows, [18, 40, 50, 8, 11, 8, 8, 70], fix_cols=("✅ Action",))
    chk = []
    for it in ISSUES:
        c = it.get("counts", {})
        n_rows = sum(1 for x in rows_all if x[1] == it["title"])
        nc = it.get("name_counts", {})
        sfc = "; ".join(f"{k.split('|', 1)[1]}: {v}" for k, v in nc.items() if k.startswith("SF|"))
        smc = "; ".join(f"{k.split('|', 1)[1]}: {v}" for k, v in nc.items() if k.startswith("Semrush|"))
        chk.append([it["title"], n_rows, len([u for u in it["urls"] if u != "SITEWIDE"]), sfc, smc, ", ".join(sorted(sources(it).split(" + ")))])
    write_table(wb.create_sheet("Sources & Checks"), ["Issue", "Rows in 'All Issues'", "Unique URLs", "Screaming Frog (check: URLs)", "Semrush (check: failed)", "Sources"], chk, [45, 12, 12, 60, 50, 30])
    wb.save(path)
    return wb

# ================================================================== EXPERT
def build_expert(path):
    wb = Workbook(); ws = wb.active; ws.title = "Summary"; B = border()
    ws["A1"] = f"{CLIENT}: SEO Audit"; ws["A1"].font = Font(bold=True, size=16, color=NAVY)
    ws["A2"] = f"{DOMAIN} · " + sources_line(); ws["A2"].font = Font(italic=True, color="595959")
    r = 4; ws.cell(r, 1, "Key metrics").font = Font(bold=True, size=12, color=NAVY); r += 1
    for k, v in summary_metrics():
        ws.cell(r, 1, k).border = B; ws.cell(r, 2, v).border = B; r += 1
    r += 1; ws.cell(r, 1, "Issues by severity").font = Font(bold=True, size=12, color=NAVY); r += 1
    sc = collections.Counter(x["severity"] for x in ISSUES)
    for s in SEVERITIES:
        ws.cell(r, 1, s).fill = fill(SEV_FILL[s]); ws.cell(r, 1).border = B; ws.cell(r, 2, f"{sc[s]} issue types").border = B; r += 1
    r += 1; ws.cell(r, 1, "Priority fixes").font = Font(bold=True, size=12, color=NAVY); r += 1
    for i, h in enumerate(["#", "Fix", "Severity", "Effort"], 1):
        c = ws.cell(r, i, h); c.fill = fill(NAVY); c.font = Font(bold=True, color="FFFFFF"); c.border = B
    for n, t in enumerate(TOP[:10], 1):
        r += 1
        for i, v in enumerate([n, t.get("fix_expert") or t.get("fix"), t.get("severity", W), t.get("effort", "")], 1):
            c = ws.cell(r, i, v); c.border = B; c.alignment = Alignment(vertical="top", wrap_text=True)
        ws.cell(r, 3).fill = fill(SEV_FILL.get(t.get("severity", W), "FFFFFF"))
    for col, w in zip("ABCD", (40, 90, 20, 10)): ws.column_dimensions[col].width = w
    ws.sheet_view.showGridLines = False
    iss = []
    for it in ISSUES:
        n, lst = affected(it)
        iss.append([it["severity"], it["priority"], it["effort"], sources(it), it["title"], data_summary(it), n, lst, fix_e(it)])
    write_table(wb.create_sheet("Issues"), ["Severity", "Priority", "Effort", "Source", "Issue", "Data", "URLs", "Affected", "✅ Fix"], iss,
                [17, 9, 8, 16, 38, 50, 7, 55, 55], fix_cols=("✅ Fix",), sev_col="Severity", pri_col="Priority")
    mt, md, hh = [], [], []
    for p in PAGES:
        c = CP.get(p["url"], {}); pa = P(p["url"])
        mt.append([pa, kwshort(c.get("focus_keyword")), p.get("title") or "—", len(p.get("title") or ""), p.get("title_px") or "", title_problem(p, True), c.get("title"), len(c.get("title") or "")])
        md.append([pa, kwshort(c.get("focus_keyword")), p.get("desc") or "—", len(p.get("desc") or "") or "—", p.get("desc2") or "—", desc_problem(p, True), c.get("description"), len(c.get("description") or "")])
        hh.append([pa, kwshort(c.get("focus_keyword")), (p.get("h1") or ["(none)"])[0], h1_problem(p, True), c.get("h1"), "issue" if p["url"] in H2ISS else "OK", c.get("h2_note") or "OK"])
    write_table(wb.create_sheet("Meta Titles"), ["Path", "Focus keyword", "Current title", "Len", "Px", "Issue", "✅ New title", "Len"], mt, [45, 30, 50, 6, 6, 24, 55, 6], fix_cols=("✅ New title",))
    write_table(wb.create_sheet("Meta Descriptions"), ["Path", "Focus keyword", "Current", "Len", "2nd description", "Issue", "✅ New description", "Len"], md, [45, 28, 42, 6, 24, 18, 70, 6], fix_cols=("✅ New description",))
    write_table(wb.create_sheet("H1 & Headings"), ["Path", "Focus keyword", "Current H1", "H1 issue", "✅ New H1", "H2", "✅ H2 action"], hh, [45, 28, 42, 18, 55, 8, 45], fix_cols=("✅ New H1", "✅ H2 action"))
    ia = []
    for i in idx:
        pages_ = i.get("pages") or []
        used = "All pages" if NP >= 10 and len(pages_) >= 0.9 * NP else (", ".join(P(x) for x in pages_) or f"— (attached to {P(i['parent']) if i.get('parent') else 'none'})")
        ia.append([i["url"].split("/wp-content/uploads/")[-1].replace(BASE, ""), used, (i.get("bytes") or 0) // 1024 if i.get("bytes") else None, alt_text(i["url"])])
    for im in IMGS:
        if not im.get("missing_alt") and (im.get("bytes") or 0) > 102400:
            ia.append([im["url"].split("/wp-content/uploads/")[-1].replace(BASE, ""), ", ".join(P(x) for x in im.get("pages", [])) or "—", im["bytes"] // 1024, "Alt OK: compress only"])
    ia.sort(key=lambda r: (r[1].startswith("—"), r[1], r[0]))
    wsI = wb.create_sheet("Image Alt Text")
    write_table(wsI, ["File", "Used on", "KB", "✅ Alt text"], ia, [55, 50, 7, 75], fix_cols=("✅ Alt text",))
    wsI.conditional_formatting.add(f"C2:C{max(wsI.max_row, 2)}", CellIsRule(operator="greaterThan", formula=["500"], fill=fill("F8CBAD")))
    wsI.conditional_formatting.add(f"C2:C{max(wsI.max_row, 2)}", CellIsRule(operator="between", formula=["101", "500"], fill=fill("FFE699")))
    grp = collections.OrderedDict()
    for kind in ("internal", "external"):
        for l in LINKS.get(kind, []):
            l = dict(l, kind=kind); t = l["target"].split("#")[0] if "email-protection" in l["target"] else l["target"]
            g = grp.setdefault((link_type(l), t, l["status"], l.get("final") or ""), {"src": set(), "n": 0, "l": l})
            g["src"].add(l["source"]); g["n"] += 1
    bl = []
    for (typ, t, st, fin), g in grp.items():
        where = "All pages" if NP >= 10 and len(g["src"]) >= 0.9 * NP else ", ".join(P(s) for s in sorted(g["src"]))
        bl.append([typ, where, g["n"], P(t) if host_of(t) == DOMAIN else t, f"{st}" + (f" → {P(fin) if host_of(fin) == DOMAIN else fin}" if fin else ""), link_fix(g["l"], True)])
    for b_ in LINKS.get("blocked_external", []):
        if b_.get("inlinks"): bl.append(["External (robots-blocked)", f"{b_['inlinks']} links", b_["inlinks"], b_["target"], "not checkable", "Manual check"])
    write_table(wb.create_sheet("Links & Redirects"), ["Type", "Found on", "Links", "Target", "Status", "✅ Fix"], bl, [24, 45, 7, 60, 40, 34], fix_cols=("✅ Fix",))
    ts = [[t["area"], t["finding"], {"Problem": "Issue"}.get(t["status"], t["status"]), EXPERT_ACTION.get(t.get("fix_key"), "See Issues") if t["status"] not in ("OK", "Info", "N/A") else "—"] for t in TECH_ALL]
    write_table(wb.create_sheet("Technical"), ["Area", "Finding", "Status", "✅ Action"], ts, [24, 90, 13, 45], fix_cols=("✅ Action",), status_col="Status")
    groups = collections.OrderedDict()
    for u, j, mi, items, err in schema_rows():
        groups.setdefault((items, err), []).append(P(u))
    sd = [[f"{len(v)} pages: " + ", ".join(v[:6]) + (" …" if len(v) > 6 else ""), k[0], k[1], "—", "No action"] for k, v in groups.items()]
    if SCHEMA.get("jsonld"):
        sd.append([f"{SCHEMA.get('type') or 'LocalBusiness'} JSON-LD (site-wide)", "—", "—", SCHEMA.get("notes", ""), SCHEMA["jsonld"]])
    write_table(wb.create_sheet("Structured Data"), ["Page group", "Schema items (Semrush)", "Errors", "Gap", "✅ Action"], sd, [55, 40, 22, 40, 80], fix_cols=("✅ Action",))
    write_table(wb.create_sheet("Opportunities"), ["Type", "Opportunity", "Priority", "Effort"], [[o.get("type"), o.get("opportunity") + (f" ({o['area']})" if o.get("area") and o["area"] not in o.get("opportunity", "") else ""), o.get("priority", "Medium"), o.get("effort", "Medium")] for o in OPPS],
                [16, 100, 9, 8], pri_col="Priority")
    if ILINKS:
        write_table(wb.create_sheet("Internal Links"), ["From", "To", "✅ Anchor text"], [[P(l["from"]) if str(l["from"]).startswith("http") else l["from"], P(l["to"]) if str(l["to"]).startswith("http") else l["to"], l["anchor"]] for l in ILINKS], [60, 60, 45], fix_cols=("✅ Anchor text",))
    gsc = CT.get("search_console") or {}
    if gsc.get("striking_distance") or gsc.get("low_ctr_pages"):
        rows = [[x.get("query"), P(x.get("page") or ""), x.get("impressions"), x.get("position"), x.get("action")] for x in gsc.get("striking_distance", []) + gsc.get("low_ctr_pages", [])]
        write_table(wb.create_sheet("Search Console"), ["Query", "Page", "Impr.", "Pos.", "✅ Action"], rows, [40, 50, 9, 7, 60], fix_cols=("✅ Action",))
    wb.save(path)
    return wb

# ================================================================== verify
def verify(path):
    wb = load_workbook(path); probs = []
    for ws in wb.worksheets[1:]:
        hdr = [c.value for c in ws[1]]
        fx = [i for i, h in enumerate(hdr) if str(h).startswith("✅")]
        for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
            for i in fx:
                if row[i] in (None, "", "Needs manual check"): probs.append(f"{ws.title}: empty/unresolved fix cell ({row[0]})")
        if ws.freeze_panes != "A2": probs.append(f"{ws.title}: header not frozen")
    for name, col, lo, hi in (("Meta Titles", None, 50, 60), ("Meta Descriptions", None, 140, 160)):
        ws = wb[name]; hdr = [c.value for c in ws[1]]; ci = next(i for i, h in enumerate(hdr) if str(h).startswith("✅"))
        for row in ws.iter_rows(min_row=2, values_only=True):
            if not (lo <= len(row[ci] or "") <= hi): probs.append(f"{name}: length out of range for {row[0]}")
        if ws.max_row - 1 != NP: probs.append(f"{name}: {ws.max_row - 1} rows vs {NP} pages")
    return wb.sheetnames, probs

os.makedirs(OUT, exist_ok=True)
made = []
SUMMARY = {}
cname = safe_name(CLIENT)
if a.mode in ("beginner", "both"):
    p = os.path.join(OUT, f"{cname}_Full_SEO_Audit_Report_{DATE}.xlsx"); build_beginner(p); made.append(p)
if a.mode in ("expert", "both"):
    p = os.path.join(OUT, f"{cname}_SEO_Audit_Expert_{DATE}.xlsx"); build_expert(p); made.append(p)
for p in made:
    sheets, probs = verify(p)
    print("BUILT:", p); print("  sheets:", ", ".join(sheets))
    print("  verification:", "PASS" if not probs else f"{len(probs)} problem(s)")
    for x in probs[:25]: print("   -", x)
print("issue types:", len(ISSUES), dict(collections.Counter(x["severity"] for x in ISSUES)))
SUMMARY.update({"issue_types": dict(collections.Counter(x["severity"] for x in ISSUES)), "top": [t.get("fix") for t in TOP[:10]],
                "files": [os.path.basename(p) for p in made], "made_by": MADE_BY, "client": CLIENT, "date": DATE})
from common import save_json
save_json(SUMMARY, os.path.join(WD, "report_summary.json"))
