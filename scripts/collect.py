"""Collect + merge all audit data for one client folder.

Usage: python collect.py <client_folder> [--url https://example.com] [--no-live] [--no-fetch] [--max-pages 500]
Outputs (in <client_folder>/.seo-audit-work/):
  audit_data.json        merged, de-duplicated data used by build_reports.py
  page_digest.json       text/headings per page so Claude can write keywords, titles, descriptions, H1s
  content_template.json  skeleton Claude fills in -> content.json
"""
import os, sys, re, argparse, collections, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import ensure_deps, work_dir, save_json, load_json, path_of, host_of, norm_img, unesc, isnan, clean
ensure_deps()
import pandas as pd
from inventory import inventory
from sf_loader import SF
from semrush_loader import Semrush
import live_check as LC
import catalog as C

ap = argparse.ArgumentParser()
ap.add_argument("folder"); ap.add_argument("--url"); ap.add_argument("--no-live", action="store_true")
ap.add_argument("--no-fetch", action="store_true"); ap.add_argument("--max-pages", type=int, default=500)
ap.add_argument("--no-head", action="store_true", help="skip HEAD requests for media-library image sizes")
a = ap.parse_args()
FOLDER = os.path.abspath(a.folder); WD = work_dir(FOLDER)
inv = inventory(FOLDER); save_json(inv, os.path.join(WD, "inventory.json"))
log = lambda *x: print("[collect]", *x, flush=True)

sf = SF(inv["screaming_frog"]["dir"]) if inv["screaming_frog"] else None
sem = Semrush(inv["semrush"]) if inv["semrush"] else None
if sem is not None and not sem.ok: sem = None

# ---------- base URL ----------
base = a.url
if not base and sf is not None:
    ov = sf.crawl_overview(); base = ov.get("Site Crawled") or (sf.html["Address"].iloc[0] if len(sf.html) else None)
if not base and sem is not None and sem.mega is not None:
    col = "Domain" if "Domain" in sem.mega.columns else "url"
    base = re.match(r"https?://[^/]+", str(sem.mega[col].mode().iloc[0])).group(0)
if not base:
    base = "https://" + inv["folder_name"].strip("/")
base = base.rstrip("/")
if not base.startswith("http"): base = "https://" + base
log("site:", base)
F = LC.Fetcher(delay=1.5)

def canon(u):
    u = str(u)
    return base + "/" if u.rstrip("/") == base else u

# ---------- live site checks ----------
site = {}
if not a.no_live:
    log("live site checks ..."); site = LC.site_checks(base, F)
    log("stack:", site.get("stack"))
stack = site.get("stack", {"cms": "Unknown"})
if sf is not None and (stack.get("cms") in (None, "Unknown") or not stack.get("seo_plugin")):
    allu = sf.read("internal_all.csv")
    if allu is not None:
        stack = LC.stack_from_urls(list(allu["Address"]), stack)
        site["stack"] = stack
        log("stack (from Screaming Frog URLs):", {k: stack.get(k) for k in ("cms", "seo_plugin", "builder", "theme")})
if site.get("home_blocked"):
    log(f"WARNING: the live site is behind {site.get('blocked_by')}; live checks marked 'Needs manual check'.")

# ---------- pages ----------
mode = "screaming_frog" if sf is not None and len(sf.html) else "live"
live_statuses = {}
if mode == "screaming_frog":
    allp = sf.pages()
else:
    seeds = site.get("sitemap", {}).get("urls", []) + (list(sem.mega["url"]) if sem is not None and sem.mega is not None else [])
    log(f"no Screaming Frog export -> live crawl (max {a.max_pages}) ...")
    allp, live_statuses = LC.crawl(base, F, seeds=seeds, max_pages=a.max_pages)
    if F.blocked:
        log("WARNING: site served bot-protection/403 during crawl; results may be partial. Whitelist your IP or provide a Screaming Frog export.")
pages = [p for p in allp if p.get("status") == 200]
pages = [dict(p, url=canon(p["url"])) for p in pages]
PURLS = {p["url"] for p in pages}
log(f"HTML 200 pages: {len(pages)} ({mode})")

# ---------- gap fill: sitemap pages Screaming Frog did not crawl (throttled / stopped early) ----------
digest = load_json(os.path.join(WD, "page_digest.json"), {}) or {}
gap_pages = []
if mode == "screaming_frog" and not a.no_live and not a.no_fetch and not site.get("home_blocked"):
    gap = [canon(u) for u in site.get("sitemap", {}).get("urls", [])]
    gap = [u for u in dict.fromkeys(gap) if u not in PURLS and not re.search(r"\.(jpe?g|png|webp|gif|svg|pdf|xml)$", u, re.I)][:a.max_pages]
    if gap:
        log(f"{len(gap)} sitemap URLs missing from the Screaming Frog crawl -> fetching them live (polite) ...")
        from bs4 import BeautifulSoup
        for u in gap:
            r = F.get(u)
            if r is None or r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", "") or LC.CHALLENGE.search(r.text[:4000] or ""):
                continue
            fu = canon(r.url)
            if fu in PURLS: continue
            p = LC.parse_page(fu, r.text); p.update(status=200, source="Live crawl",
                indexability="Non-Indexable" if "noindex" in (p["robots"] or "").lower() else "Indexable")
            s = BeautifulSoup(r.text, "lxml")
            for t in s(["script", "style", "noscript", "header", "footer", "nav"]): t.decompose()
            digest[fu] = {"title": p["title"], "h": p["headings"][:40], "text": s.get_text(" ", strip=True)[:3000],
                          "images": p["images"], "links": p["links"], "jsonld": p["jsonld"]}
            gap_pages.append(p); PURLS.add(fu)
        pages += gap_pages
        save_json(digest, os.path.join(WD, "page_digest.json"))
        log(f"added {len(gap_pages)} pages from live fetch; total HTML pages: {len(pages)}")

# ---------- page digest (text for writing fixes) ----------
if mode == "live":
    for p in pages:
        digest[p["url"]] = {"title": p["title"], "h": p["headings"][:40], "text": "", "images": p["images"], "links": p["links"], "jsonld": p["jsonld"]}
elif not a.no_fetch and not a.no_live:
    todo = [p["url"] for p in pages if p["url"] not in digest] if not site.get("home_blocked") else []
    log(f"fetching page text for {len(todo)} pages (polite, cached) ...")
    for u in todo:
        r = F.get(u)
        if r is None or r.status_code != 200 or LC.CHALLENGE.search(r.text[:4000] or ""):
            continue
        pp = LC.parse_page(u, r.text)
        from bs4 import BeautifulSoup
        s = BeautifulSoup(r.text, "lxml")
        for t in s(["script", "style", "noscript", "header", "footer", "nav"]): t.decompose()
        digest[u] = {"title": pp["title"], "h": pp["headings"][:40], "text": s.get_text(" ", strip=True)[:3000],
                     "images": pp["images"], "links": pp["links"], "jsonld": pp["jsonld"]}
        save_json(digest, os.path.join(WD, "page_digest.json"))
    if F.blocked and len(digest) < len(pages) and stack.get("cms") == "WordPress":
        log("HTML blocked -> WordPress REST fallback for page text ...")
        rt = F.get(base + "/wp-json/wp/v2/types")
        try:
            bases = [v["rest_base"] for k, v in rt.json().items() if v.get("rest_base") and k not in ("attachment", "nav_menu_item", "wp_block", "wp_template", "wp_template_part", "wp_global_styles", "wp_navigation", "wp_font_family", "wp_font_face")]
        except Exception:
            bases = ["pages", "posts"]
        from bs4 import BeautifulSoup
        for rb in bases:
            r = F.get(f"{base}/wp-json/wp/v2/{rb}?per_page=100&_fields=link,title,content")
            try:
                for it in r.json():
                    u = canon(it["link"])
                    if u in PURLS and u not in digest:
                        s = BeautifulSoup(it["content"]["rendered"], "lxml")
                        digest[u] = {"title": unesc(it["title"]["rendered"]), "h": [(h.name, h.get_text(" ", strip=True)) for h in s.find_all(re.compile(r"^h[1-6]$"))][:40],
                                     "text": s.get_text(" ", strip=True)[:3000], "images": [], "links": [], "jsonld": [], "via": "wp-rest"}
            except Exception:
                pass
save_json(digest, os.path.join(WD, "page_digest.json"))

# ---------- issues ----------
ISS = {}
def add_issue(key, url, source, title=None, sev=None, pri=None, eff=None, tool_name=None, how=None, count=None):
    if key in C.CATALOG:
        e = C.entry(key)
    else:
        e = dict(id=key, title=title, severity=sev, priority=pri, effort=eff or "Medium", group="Other", why=how or "", fix_key="generic", fix_expert=how or "See tool guidance")
    it = ISS.setdefault(key, dict(e, urls={}, counts={}, name_counts={}, tool_names=set(), notes=[]))
    if url:
        it["urls"].setdefault(canon(url), set()).add(source)
    if tool_name: it["tool_names"].add(f"{source}: {tool_name}")
    if count is not None: it["counts"][source] = it["counts"].get(source, 0) + count

LINK_IDS = {"internal_4xx", "internal_3xx", "redirect_chain", "external_errors", "internal_5xx", "internal_noresponse", "meta_refresh"}
img_pages = collections.defaultdict(set)
if sf is not None:
    ii = sf.read("all_image_inlinks.csv")
    if ii is not None:
        for s_, d_ in zip(ii["Source"], ii["Destination"]): img_pages[d_].add(canon(s_))

if sf is not None:
    for name in sf.issue_names():
        if name in C.IGNORE_SF: continue
        key = C.SF_INDEX.get(name)
        meta = sf.issue_meta(name)
        if key is None:
            sev, pri = C.sf_generic(meta)
            key = "sf::" + name
        urls = sf.issue_urls(name)
        if key in LINK_IDS:
            inl = sf.issue_inlinks(name)
            srcs = list(inl["Source"].dropna().unique()) if inl is not None and "Source" in inl.columns else []
            for u in srcs: add_issue(key, u, "SF", tool_name=name, title=name if key.startswith("sf::") else None, sev=None, pri=None)
            ISS[key]["counts"]["SF"] = ISS[key]["counts"].get("SF", 0) + (len(inl) if inl is not None else len(urls))
            ISS[key]["name_counts"][f"SF|{name}"] = (len(inl) if inl is not None else len(urls))
            ISS[key].setdefault("targets", set()).update(urls)
            if not srcs:
                for u in urls: add_issue(key, u, "SF", tool_name=name)
            continue
        if key == "img_large" or key == "img_alt_missing" or key == "img_size_attr":
            for img in urls:
                for pg in img_pages.get(img, []) or []:
                    add_issue(key, pg, "SF", tool_name=name)
            add_issue(key, None, "SF", tool_name=name, count=len(urls))
            ISS[key]["name_counts"][f"SF|{name}"] = len(urls)
            if key == "img_alt_missing":
                inl = sf.issue_inlinks(name) if sf.issue_inlinks(name) is not None else sf.read("images_missing_alt_text_inlinks.csv")
                if inl is not None:
                    for s_ in inl["Source"].unique(): add_issue(key, s_, "SF")
            continue
        for u in urls:
            if key.startswith("sf::"):
                add_issue(key, u, "SF", title=name, sev=sev, pri=pri, eff="Medium", tool_name=name, how=clean(meta.get("How To Fix"), ""))
            else:
                add_issue(key, u, "SF", tool_name=name)
        if key in ISS:
            ISS[key]["counts"]["SF"] = ISS[key]["counts"].get("SF", 0) + len(urls)
            ISS[key]["name_counts"][f"SF|{name}"] = len(urls)

if sem is not None:
    for f_ in sem.failed():
        name, typ = f_["issue"], f_["type"]
        key = C.SEM_INDEX.get(name)
        if key is None:
            sev, pri = C.sem_generic(typ); key = "sem::" + name
        urls = sem.issue_urls(name)
        if not urls:
            add_issue(key, None, "Semrush", title=name, sev=sev if key.startswith("sem::") else None, pri=pri if key.startswith("sem::") else None, tool_name=name)
        for u, n in urls.items():
            add_issue(key, u, "Semrush", title=name, sev=sev if key.startswith("sem::") else None, pri=pri if key.startswith("sem::") else None, tool_name=name)
        ISS[key]["counts"]["Semrush"] = ISS[key]["counts"].get("Semrush", 0) + f_["failed"]
        ISS[key]["name_counts"][f"Semrush|{name}"] = f_["failed"]

# live-mode issue detection (no Screaming Frog, or pages added by the gap fill)
live_pages = pages if mode == "live" else gap_pages
if live_pages:
    by_title = collections.defaultdict(list); by_desc = collections.defaultdict(list)
    for p in live_pages:
        u = p["url"]; t = p["title"] or ""; d = p["desc"] or ""
        if not t: add_issue("title_missing", u, "Live crawl")
        elif len(t) > 60: add_issue("title_long", u, "Live crawl")
        elif len(t) < 30: add_issue("title_short", u, "Live crawl")
        if t: by_title[t].append(u)
        if not d: add_issue("desc_missing", u, "Live crawl")
        else:
            by_desc[d].append(u)
            if len(d) > 160: add_issue("desc_long", u, "Live crawl")
            if len(d) < 70: add_issue("desc_short", u, "Live crawl")
        if p.get("desc2"): add_issue("desc_multiple", u, "Live crawl")
        if not p["h1"]: add_issue("h1_missing", u, "Live crawl")
        elif len(p["h1"]) > 1: add_issue("h1_multiple", u, "Live crawl")
        if not p["h2"]: add_issue("h2_issues", u, "Live crawl")
        if any(not (im.get("alt") or "").strip() for im in p["images"]): add_issue("img_alt_missing", u, "Live crawl")
        if p["http_resources"]: add_issue("https", u, "Live crawl")
        if not p["canonical"]: add_issue("canonical", u, "Live crawl")
        if "noindex" in (p["robots"] or "").lower(): add_issue("noindex", u, "Live crawl")
        if any(l["target"] == "_blank" and "noopener" not in l["rel"] and host_of(l["href"]) != host_of(base) for l in p["links"]): add_issue("unsafe_links", u, "Live crawl")
        if any((l["text"] or "").strip().lower() in ("read more", "click here", "here", "learn more", "more") for l in p["links"]): add_issue("anchor_text", u, "Live crawl")
    if mode != "live":  # duplicates against the Screaming Frog pages too
        for p in pages:
            if p not in live_pages:
                if p.get("title"): by_title[p["title"]].append(p["url"])
                if p.get("desc"): by_desc[p["desc"]].append(p["url"])
    for t, us in by_title.items():
        if len(us) > 1:
            for u in us: add_issue("title_duplicate", u, "Live crawl")
    for d, us in by_desc.items():
        if len(us) > 1:
            for u in us: add_issue("desc_duplicate", u, "Live crawl")

# site-level live checks -> issues
if site and not site.get("home_blocked"):
    if site.get("llms_status") and site["llms_status"] >= 400:
        add_issue("llms", base + "/llms.txt", "Live check")
    if site.get("robots", {}).get("status") not in (200, None):
        add_issue("robots_txt", base + "/robots.txt", "Live check")
    if site.get("robots", {}).get("disallow_all"):
        add_issue("robots_txt", base + "/robots.txt", "Live check")
    if not site.get("sitemap", {}).get("files"):
        add_issue("sitemap", base + "/", "Live check")
    hv = site.get("variants", {}).get("http", {})
    if hv.get("status") and hv["status"] not in (301, 308):
        add_issue("https", hv.get("url"), "Live check")
    if sf is None and site.get("security_headers") and not all(site["security_headers"].values()):
        add_issue("security_headers", base + "/", "Live check")

# ---------- links ----------
links = {"internal": [], "external": [], "blocked_external": []}
recheck_note = None
if sf is not None:
    links = sf.link_issues()
    # Screaming Frog "no response" often means the server throttled the crawler: re-check those URLs live
    nr = sorted({l["target"] for l in links["internal"] if not l.get("status")})
    if nr and not a.no_live and not site.get("home_blocked"):
        log(f"re-checking {len(nr)} URLs Screaming Frog got no response from ...")
        st = LC.link_status(nr, F)
        ok = {u for u, s in st.items() if s["status"] == 200 or (s["final"] and s["final"][1] == 200)}
        for l in links["internal"]:
            s_ = st.get(l["target"])
            if s_ and not l.get("status"):
                l["status"] = s_["status"]; l["final"] = (s_["final"] or [None])[0]
        links["internal"] = [l for l in links["internal"] if l["target"] not in ok or 300 <= (l.get("status") or 0) < 400]
        recheck_note = f"Screaming Frog got no response from {len(nr)} URLs; live re-check: {len(ok)} of them respond normally (server throttled the crawl, not broken). Re-crawl with a lower speed (1-2 URL/s)."
        if "internal_noresponse" in ISS:
            still = [u for u in nr if u not in ok]
            if not still:
                del ISS["internal_noresponse"]
            else:
                bad_src = {canon(l["source"]) for l in links["internal"] if l["target"] in still}
                ISS["internal_noresponse"]["urls"] = {u: s for u, s in ISS["internal_noresponse"]["urls"].items() if u in bad_src}
                ISS["internal_noresponse"]["targets"] = set(still)
                ISS["internal_noresponse"]["counts"]["SF"] = sum(1 for l in links["internal"] if l["target"] in still)
else:
    targets_int = collections.defaultdict(list); targets_ext = collections.defaultdict(list)
    for p in pages:
        for l in p["links"]:
            h = l["href"].split("#")[0]
            if not h.startswith("http"): continue
            (targets_int if host_of(h) == host_of(base) else targets_ext)[h].append((p["url"], l["text"]))
    known = {u: v for u, v in live_statuses.items()}
    check_int = [u for u in targets_int if u not in known and canon(u) not in PURLS]
    if len(check_int) > 300:
        log(f"{len(check_int)} uncrawled internal link targets; checking the 300 most-linked (raise --max-pages for full coverage)")
        check_int = sorted(check_int, key=lambda u: -len(targets_int[u]))[:300]
    log(f"checking {len(check_int)} internal + {len(targets_ext)} external link targets ...")
    st = LC.link_status(check_int, F); st.update(LC.link_status(list(targets_ext), F))
    for u, v in known.items(): st.setdefault(u, {"status": v.get("status"), "final": (v.get("redirect"), None) if v.get("redirect") else None})
    for kind, tg in (("internal", targets_int), ("external", targets_ext)):
        for u, srcs in tg.items():
            s_ = st.get(u)
            if not s_ or s_["status"] in (200, None) or (canon(u) in PURLS): continue
            for src, txt in srcs:
                links[kind].append({"source": src, "target": u, "status": s_["status"], "final": (s_["final"] or [None])[0], "anchor": txt})
                if kind == "internal":
                    add_issue("internal_3xx" if 300 <= s_["status"] < 400 else "internal_4xx", src, "Live crawl")
                else:
                    add_issue("external_errors", src, "Live crawl")
cf_email = any("/cdn-cgi/l/email-protection" in l["target"] for l in links["internal"])

# ---------- images ----------
IMG = {}
def img_rec(u):
    k = norm_img(u)
    return IMG.setdefault(k, {"url": k, "variants": set(), "pages": set(), "alt": None, "bytes": None, "missing_alt": False, "sources": set(), "parent": None})
if sf is not None:
    si = sf.images()
    for m in si["missing_alt"]:
        r = img_rec(m["img"]); r["variants"].add(m["img"]); r["pages"].add(canon(m["page"])); r["missing_alt"] = True; r["sources"].add("SF"); r["alt"] = ""
    for u, b in si["sizes"].items():
        if norm_img(u) in IMG or b > 100 * 1024:
            r = img_rec(u); r["variants"].add(u); r["bytes"] = max(r["bytes"] or 0, b) if norm_img(u) != u else b
    for d_, srcs in img_pages.items():
        if norm_img(d_) in IMG: IMG[norm_img(d_)]["pages"].update(srcs)
else:
    for p in pages:
        for im in p["images"]:
            if not im["src"] or im["src"].startswith("data:"): continue
            r = img_rec(im["src"]); r["variants"].add(im["src"]); r["pages"].add(p["url"]); r["sources"].add("Live crawl")
            if not (im.get("alt") or "").strip():
                r["missing_alt"] = True; r["alt"] = ""
            elif r["alt"] is None:
                r["alt"] = im["alt"]
media = []
if not a.no_live and stack.get("cms") == "WordPress":
    log("WordPress media library ..."); media = LC.wp_media(base, F)
    for m in media:
        if not re.search(r"\.(jpe?g|png|webp|gif|svg|avif)$", m["url"], re.I): continue
        r = img_rec(m["url"]); r["sources"].add("WP Media"); r["parent"] = m["parent"]
        if not m["alt"]:
            r["missing_alt"] = True; r["alt"] = r["alt"] or ""
        else:
            r["alt"] = m["alt"]; r["missing_alt"] = r["missing_alt"] and "SF" in r["sources"]
    if not a.no_head:
        need = [k for k, r in IMG.items() if r["bytes"] is None and not k.lower().endswith(".svg")]
        log(f"HEAD sizes for {len(need)} images ..."); F.delay = 0.3
        for k, v in LC.head_sizes(need, F).items(): IMG[k]["bytes"] = v
        F.delay = 1.5
# gallery links to image files count as placements
for u, d in digest.items():
    for l in d.get("links", []):
        k = norm_img(l["href"])
        if k in IMG and re.search(r"\.(jpe?g|png|webp|gif)$", k, re.I): IMG[k]["pages"].add(u)
alt_needed = sorted([r for r in IMG.values() if r["missing_alt"]], key=lambda r: (sorted(r["pages"])[0] if r["pages"] else "~" + (r["parent"] or ""), r["url"]))
img_index = []
for n, r in enumerate(alt_needed, 1):
    r["n"] = n
    img_index.append({"n": n, "url": r["url"], "pages": sorted(r["pages"]), "parent": r["parent"], "bytes": r["bytes"], "svg": r["url"].lower().endswith(".svg")})
save_json(img_index, os.path.join(WD, "img_index.json"))
large = [r for r in IMG.values() if (r["bytes"] or 0) > 100 * 1024]
for r in large:
    for pg in r["pages"]: add_issue("img_large", pg, "Live check" if "SF" not in r["sources"] else "SF")
for r in alt_needed:
    for pg in r["pages"]: add_issue("img_alt_missing", pg, "Live check" if not (r["sources"] & {"SF"}) else "SF")

# ---------- Semrush extras ----------
sem_info = {}
if sem is not None:
    sem_info = {"totals": sem.totals(), "failed": sem.failed(), "page_info": {canon(k): v for k, v in sem.page_info().items()},
                "structured": [dict(s, url=canon(s["url"])) for s in sem.structured()], "markup_errors": sem.markup_errors(),
                "urls": len(sem.mega) if sem.mega is not None else None}

# ---------- technical facts ----------
T = []
def tech(area, finding, status, source, evidence="", fix_key=None):
    T.append({"area": area, "finding": finding, "status": status, "source": source, "evidence": evidence, "fix_key": fix_key})
if sf is not None:
    ov = sf.crawl_overview()
    tech("Crawl", f"{ov.get('Total URLs Encountered', '?')} URLs encountered · {ov.get('Total Internal URLs', '?')} internal · {len(pages) - len(gap_pages)} HTML 200 pages"
         + (f" · +{len(gap_pages)} sitemap pages fetched live (missing from the SF crawl)" if gap_pages else ""), "Info", "SF")
    if recheck_note: tech("Crawl completeness", recheck_note, "Issue", "SF + Live check")
    sc = sf.security_counts()
    if any(sc.values()):
        tech("Security headers", "Missing: " + ", ".join(f"{k} ({v})" for k, v in sc.items() if v), "Issue", "SF", fix_key="headers")
    st = sf.structured()
    if st is not None and not st["enabled"]:
        tech("Structured data (SF)", "Structured-data extraction was not enabled in this Screaming Frog crawl", "Info", "SF")
idx = [p for p in pages if str(p.get("indexability", "Indexable")).startswith("Indexable")]
tech("Indexability", f"{len(idx)}/{len(pages)} HTML pages indexable", "OK" if len(idx) == len(pages) else "Issue", "SF" if sf is not None else "Live crawl", fix_key="noindex")
selfcan = sum(1 for p in pages if p.get("canonical") and p["canonical"].rstrip("/") == p["url"].rstrip("/"))
tech("Canonicals", f"{selfcan}/{len(pages)} pages self-canonical", "OK" if selfcan == len(pages) else "Issue", "SF" if sf is not None else "Live crawl", fix_key="canonical")
if site and site.get("home_blocked"):
    tech("Live checks", f"Site served {site.get('blocked_by')} challenge to automated requests: robots.txt, sitemap, redirects, headers and llms.txt could not be checked live",
         "Manual check", "Live check", "Whitelist the auditing IP or check these in a browser")
if site and not site.get("home_blocked"):
    rb = site.get("robots", {})
    tech("robots.txt", f"HTTP {rb.get('status')} · sitemap lines: {len(rb.get('sitemaps', []))}" + (" · DISALLOW ALL" if rb.get("disallow_all") else ""),
         "OK" if rb.get("status") == 200 and not rb.get("disallow_all") else "Issue", "Live check", rb.get("text", "")[:300], "robots")
    sm = site.get("sitemap", {})
    notcrawled = [u for u in sm.get("urls", []) if canon(u) not in PURLS]
    tech("XML sitemap", f"{len(sm.get('files', []))} sitemap files · {len(sm.get('urls', []))} URLs · {len(notcrawled)} not found among crawled HTML pages",
         "OK" if sm.get("files") and not notcrawled else ("Issue" if sm.get("files") else "Issue"), "Live check", "; ".join(notcrawled[:30]), "sitemap")
    for u in notcrawled: add_issue("sitemap", u, "Live check")
    hv = site.get("variants", {})
    tech("HTTPS / host", f"http → {hv.get('http', {}).get('status')} {hv.get('http', {}).get('location') or ''} · www/non-www → {hv.get('www_swap', {}).get('status')} {hv.get('www_swap', {}).get('location') or ''}",
         "OK" if hv.get("http", {}).get("status") in (301, 308) else "Issue", "Live check", fix_key="https")
    sh = site.get("security_headers", {})
    if sh: tech("Security headers (home)", ", ".join(f"{k}: {'yes' if v else 'MISSING'}" for k, v in sh.items()), "OK" if all(sh.values()) else "Issue", "Live check", fix_key="headers")
    tech("llms.txt", f"HTTP {site.get('llms_status')}", "OK" if site.get("llms_status") == 200 else "Issue", "Live check", fix_key="llms")
    tech("Homepage response", f"{site.get('home_time')} s (live) " + (f"· SF {next((p['response_time'] for p in pages if p['url'] == base + '/'), '')} s" if sf is not None else ""), "Info", "Live check")
    tech("Mobile viewport", "viewport meta present" if site.get("viewport") else "viewport meta MISSING", "OK" if site.get("viewport") else "Issue", "Live check")
    tech("Language", f"html lang = {site.get('lang')}", "OK" if site.get("lang") else "Issue", "Live check")
    tech("Structured data (home)", ", ".join(site.get("home_jsonld", [])) or "none found", "Info", "Live check", fix_key="schema")
if site:
    s = site.get("stack", {})
    tech("Stack", " · ".join(x for x in [s.get("cms"), s.get("seo_plugin"), s.get("builder"), s.get("theme") and "theme: " + s["theme"], s.get("cdn"), s.get("host_hint")] if x), "Info", "Live check")
    if s.get("analytics"): tech("Analytics", "Tags found: " + ", ".join(s["analytics"]), "Info", "Live check")
    if F.blocked and not site.get("home_blocked"):
        tech("Bot protection", "Site served a bot-challenge / 403 to automated requests during this audit", "Info", "Live check", "Whitelist your crawler IP before running Screaming Frog")

# ---------- write ----------
for it in ISS.values():
    it["urls"] = {u: sorted(s) for u, s in it["urls"].items()}
    it["tool_names"] = sorted(it["tool_names"]); it["targets"] = sorted(it.get("targets", set()))
if cf_email and "internal_4xx" in ISS:
    ISS["internal_4xx"]["notes"].append("cloudflare_email")
data = {
    "meta": {"folder": FOLDER, "base": base, "domain": host_of(base), "mode": mode, "collected": time.strftime("%Y-%m-%d"),
             "sources": {"screaming_frog": inv["screaming_frog"], "semrush": inv["semrush"], "images": inv["images"], "text_notes": inv["text_notes"], "extra_data": inv["extra_data"]}},
    "stack": stack, "site": {k: v for k, v in site.items() if k not in ("home_text", "contact_text")},
    "pages": [{k: v for k, v in p.items() if k not in ("images", "links", "headings", "http_resources")} for p in pages],
    "issues": ISS, "links": links,
    "images": [{**{k: (sorted(v) if isinstance(v, set) else v) for k, v in r.items()}} for r in IMG.values()],
    "semrush": sem_info, "technical": T, "sf_structured": (sf.structured() if sf is not None else None),
}
save_json(data, os.path.join(WD, "audit_data.json"))
with open(os.path.join(WD, "site_text.txt"), "w", encoding="utf-8") as fh:
    fh.write("HOME:\n" + site.get("home_text", "") + "\n\nCONTACT (" + str(site.get("contact_url")) + "):\n" + site.get("contact_text", "")
             + "\n\nPHONES: " + ", ".join(site.get("phones", [])) + "\nEMAILS: " + ", ".join(site.get("emails", [])))

# content template for Claude
tmpl = load_json(os.path.join(WD, "content_template.json"), None) or {}
tmpl = {
    "client": {"name": "", "business_type": "", "location": "", "service_area": "", "phone": "", "address": "", "made_by": "", "date": time.strftime("%Y-%m-%d"), "notes": ""},
    "semrush_overview": {"site_health": None, "ai_search_health": None, "errors": None, "warnings": None, "notices": None, "crawled": None, "thematic": ""},
    "psi": {"mobile": {"performance": None, "accessibility": None, "best_practices": None, "seo": None, "fcp": None, "lcp": None, "tbt": None, "cls": None, "si": None,
                       "payload_kib": None, "unused_js_kib": None, "render_blocking_ms": None, "lcp_element": "", "notes": ""},
            "desktop": {"performance": None, "accessibility": None, "best_practices": None, "seo": None, "fcp": None, "lcp": None, "tbt": None, "cls": None, "si": None,
                        "payload_kib": None, "unused_js_kib": None, "render_blocking_ms": None, "lcp_element": "", "notes": ""},
            "field_data": "", "source": ""},
    "pages": {p["url"]: {"current_title": p["title"], "current_desc": p["desc"], "current_h1": (p["h1"] or [""])[0],
                         "focus_keyword": "", "title": "", "description": "", "h1": "", "h2_note": ""} for p in pages},
    "alts": {str(i["n"]): "" for i in img_index},
    "findings": [], "opportunities": [], "internal_links": [], "top_fixes": [],
    "schema": {"type": "", "jsonld": "", "notes": ""},
    "search_console": {"summary": "", "striking_distance": [], "low_ctr_pages": []},
}
save_json(tmpl, os.path.join(WD, "content_template.json"))
cnt = collections.Counter(v["severity"] for v in ISS.values())
log(f"DONE. pages={len(pages)} issue types={len(ISS)} {dict(cnt)} images needing alt={len(alt_needed)} large images={len(large)} links: int={len(links['internal'])} ext={len(links['external'])}")
log("next: python contact_sheets.py", FOLDER, " then write content.json")
