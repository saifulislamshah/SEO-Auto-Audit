"""Live checks against the website: site-level checks, CMS detection, WordPress media library,
image sizes, link status, and a polite fallback crawler (used when no Screaming Frog export exists)."""
import re, time, json
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from common import host_of, norm_img

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
CHALLENGE = re.compile(r"One moment, please|Just a moment\.\.\.|cf-browser-verification|Attention Required! \| Cloudflare|captcha-delivery|sgcaptcha|_Incapsula_Resource|px-captcha", re.I)


class Fetcher:
    def __init__(self, delay=1.5):
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
        self.delay = delay
        self.blocked = False
        self.last = 0

    def get(self, url, allow_redirects=True, timeout=30, head=False, retries=2):
        if self.blocked and host_of(url) == getattr(self, "site_host", None):
            retries = 0  # site already challenged us: don't keep retrying / sleeping
        for attempt in range(retries + 1):
            wait = self.delay - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            self.last = time.time()
            try:
                if head:
                    r = self.s.head(url, allow_redirects=allow_redirects, timeout=timeout)
                else:
                    r = self.s.get(url, allow_redirects=allow_redirects, timeout=timeout)
            except Exception as e:
                if attempt < retries:
                    time.sleep(5 * (attempt + 1)); continue
                return None
            if not head and r.status_code in (200, 202) and CHALLENGE.search(r.text[:4000] or ""):
                self.blocked = True
                if attempt < retries:
                    time.sleep(10 * (attempt + 1)); continue
            if r.status_code in (403, 429) and attempt < retries and host_of(url) == getattr(self, "site_host", None):
                self.blocked = True
                time.sleep(20 * (attempt + 1)); continue
            return r
        return r


PLUGIN_SEO = {"wordpress-seo": "Yoast", "seo-by-rank-math": "Rank Math", "all-in-one-seo-pack": "AIOSEO", "wp-seopress": "SEOPress"}
BUILDERS = {"elementor": "Elementor", "divi-builder": "Divi", "js_composer": "WPBakery", "bb-plugin": "Beaver Builder", "oxygen": "Oxygen", "bricks": "Bricks"}


def stack_from_urls(urls, base_stack=None):
    """Fallback CMS detection from crawled asset URLs (e.g. Screaming Frog internal_all)."""
    st = dict(base_stack or {})
    joined = " ".join(map(str, urls)).lower()
    if "/wp-content/" in joined or "/wp-includes/" in joined:
        st["cms"] = "WordPress"
        plugins = sorted(set(re.findall(r"/wp-content/plugins/([a-z0-9_\-]+)/", joined)))
        st["plugins"] = sorted(set(st.get("plugins") or []) | set(plugins))
        for k, v in PLUGIN_SEO.items():
            if k in plugins: st["seo_plugin"] = st.get("seo_plugin") or v
        for k, v in BUILDERS.items():
            if k in plugins or f"/themes/{k}" in joined: st["builder"] = st.get("builder") or v
        m = re.search(r"/wp-content/themes/([a-z0-9_\-]+)/", joined)
        if m: st["theme"] = st.get("theme") or m.group(1)
        if m and m.group(1) in ("divi", "bricks", "oxygen-is-not-a-theme"): st["builder"] = st.get("builder") or m.group(1).capitalize()
    elif "cdn.shopify.com" in joined: st["cms"] = "Shopify"
    elif "static.wixstatic.com" in joined: st["cms"] = "Wix"
    elif "squarespace" in joined: st["cms"] = "Squarespace"
    return st


def detect_stack(html, headers):
    h = html or ""
    hl = h.lower()
    hd = {k.lower(): v for k, v in (headers or {}).items()}
    cms = "Unknown"
    if "/wp-content/" in hl or 'name="generator" content="wordpress' in hl: cms = "WordPress"
    elif "cdn.shopify.com" in hl or "x-shopify" in " ".join(hd): cms = "Shopify"
    elif "wix.com" in hl or "x-wix-request-id" in hd: cms = "Wix"
    elif "squarespace" in hl: cms = "Squarespace"
    elif "webflow" in hl: cms = "Webflow"
    elif "drupal" in hl: cms = "Drupal"
    elif "joomla" in hl: cms = "Joomla"
    plugin = None
    if "yoast seo" in hl or "yoast-schema-graph" in hl: plugin = "Yoast"
    elif "rank math" in hl or "rank-math" in hl: plugin = "Rank Math"
    elif "aioseo" in hl or "all in one seo" in hl: plugin = "AIOSEO"
    elif "seopress" in hl: plugin = "SEOPress"
    builder = None
    for b, pat in (("Elementor", "elementor"), ("Divi", "et_pb_"), ("WPBakery", "vc_row"), ("Beaver Builder", "fl-builder"), ("Bricks", "brxe-"), ("Oxygen", "oxygen-")):
        if pat in hl:
            builder = b; break
    if not builder and cms == "WordPress" and "wp-block-" in hl: builder = "Gutenberg"
    theme = None
    m = re.search(r"/wp-content/themes/([a-z0-9_\-]+)/", hl)
    if m: theme = m.group(1)
    plugins = sorted(set(re.findall(r"/wp-content/plugins/([a-z0-9_\-]+)/", hl)))
    cdn = "Cloudflare" if ("cloudflare" in hd.get("server", "").lower() or "cf-ray" in hd) else None
    ga = sorted(set(re.findall(r"\b(G-[A-Z0-9]{6,12}|GTM-[A-Z0-9]{4,10}|UA-\d{4,10}-\d{1,3})\b", h)))
    return {"cms": cms, "seo_plugin": plugin, "builder": builder, "theme": theme, "plugins": plugins, "cdn": cdn, "analytics": ga,
            "server": hd.get("server"), "host_hint": "Hostinger" if ("hostinger" in hl or "hcdn" in " ".join(hd)) else None}


SEC_HEADERS = {"strict-transport-security": "HSTS", "content-security-policy": "CSP", "x-content-type-options": "X-Content-Type-Options",
               "x-frame-options": "X-Frame-Options", "referrer-policy": "Referrer-Policy"}


def site_checks(base, f):
    """base like https://example.com  (no trailing slash)."""
    out = {"base": base}
    f.site_host = host_of(base)
    t0 = time.time(); r = f.get(base + "/"); out["home_time"] = round(time.time() - t0, 2)
    out["home_status"] = r.status_code if r is not None else None
    html = r.text if (r is not None and r.status_code == 200) else ""
    raw = r.text if r is not None else ""
    out["home_blocked"] = bool(r is not None and (r.status_code in (403, 429, 202) or CHALLENGE.search(raw[:4000] or "")))
    if out["home_blocked"]:
        f.blocked = True
        out["blocked_by"] = "SiteGround sgcaptcha" if "sgcaptcha" in raw else ("Hostinger" if "One moment, please" in raw else ("Cloudflare" if "cloudflare" in raw.lower() else "bot protection"))
        html = ""
    out["stack"] = detect_stack(html, dict(r.headers) if r is not None else {})
    out["security_headers"] = {v: (k in {x.lower() for x in r.headers}) for k, v in SEC_HEADERS.items()} if r is not None else {}
    soup = BeautifulSoup(html, "lxml") if html else None
    out["home_jsonld"] = jsonld_types(soup) if soup else []
    out["home_text"] = soup.get_text(" ", strip=True)[:8000] if soup else ""
    out["lang"] = (soup.html.get("lang") if soup and soup.html else None)
    out["viewport"] = bool(soup and soup.find("meta", attrs={"name": "viewport"}))
    # contact page text (for NAP)
    contact = None
    if soup:
        for a in soup.find_all("a", href=True):
            if re.search(r"contact", a["href"], re.I):
                contact = urljoin(base + "/", a["href"]); break
    out["contact_url"] = contact
    if contact and host_of(contact) == host_of(base):
        rc = f.get(contact)
        if rc is not None and rc.status_code == 200:
            out["contact_text"] = BeautifulSoup(rc.text, "lxml").get_text(" ", strip=True)[:6000]
    txt = out["home_text"] + " " + out.get("contact_text", "")
    out["phones"] = sorted(set(re.findall(r"\(?\+?\d{1,3}\)?[\s.-]?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}", txt)))[:6]
    out["emails"] = sorted(set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", txt)))[:6]
    # robots / sitemaps / llms
    rr = f.get(base + "/robots.txt")
    out["robots"] = {"status": rr.status_code if rr is not None else None, "text": (rr.text[:3000] if rr is not None and rr.status_code == 200 else "")}
    sm_lines = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", out["robots"]["text"])
    out["robots"]["sitemaps"] = sm_lines
    out["robots"]["disallow_all"] = bool(re.search(r"(?ims)user-agent:\s*\*\s*(?:\n(?!user-agent).*)*\n\s*disallow:\s*/\s*$", out["robots"]["text"]))
    cands = sm_lines or [base + "/sitemap_index.xml", base + "/sitemap.xml", base + "/wp-sitemap.xml"]
    out["sitemap"] = sitemap_urls(cands, f)
    rl = f.get(base + "/llms.txt")
    out["llms_status"] = rl.status_code if rl is not None else None
    # protocol / host variants
    p = urlparse(base)
    variants = {"http": f"http://{p.netloc}/", "www_swap": f"{p.scheme}://" + (p.netloc[4:] if p.netloc.startswith("www.") else "www." + p.netloc) + "/"}
    out["variants"] = {}
    for k, u in variants.items():
        rv = f.get(u, allow_redirects=False)
        out["variants"][k] = {"url": u, "status": rv.status_code if rv is not None else None, "location": rv.headers.get("Location") if rv is not None else None}
    return out


def jsonld_types(soup):
    types = []
    for sc in soup.find_all("script", type="application/ld+json"):
        try:
            j = json.loads(sc.string or "")
        except Exception:
            types.append("INVALID-JSON"); continue
        items = j.get("@graph", [j]) if isinstance(j, dict) else j
        for g in items if isinstance(items, list) else [items]:
            if isinstance(g, dict):
                t = g.get("@type"); types += t if isinstance(t, list) else [t]
    return sorted({t for t in types if t})


def sitemap_urls(cands, f, limit=5000):
    seen, urls, files = set(), [], []
    queue = list(cands)
    while queue and len(urls) < limit:
        u = queue.pop(0)
        if u in seen: continue
        seen.add(u)
        r = f.get(u)
        if r is None or r.status_code != 200 or "<" not in r.text[:200]:
            continue
        files.append({"url": u, "status": r.status_code})
        locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)
        if "<sitemapindex" in r.text:
            queue += locs
        else:
            urls += [l for l in locs if not re.search(r"\.(jpe?g|png|webp|gif|svg|pdf)$", l, re.I)]
    return {"files": files, "urls": sorted(set(urls))}


def wp_media(base, f):
    """Public WordPress media library: url, alt, parent page link."""
    out, page, total = [], 1, 1
    while page <= min(total, 60):
        r = f.get(f"{base}/wp-json/wp/v2/media?per_page=100&page={page}&_fields=id,source_url,alt_text,post,mime_type")
        if r is None or r.status_code != 200:
            break
        try:
            d = r.json()
        except Exception:
            break
        if not isinstance(d, list) or not d: break
        out += d
        try:
            total = int(r.headers.get("X-WP-TotalPages", total))
        except ValueError:
            pass
        page += 1
    if not out:
        return []
    parents = {}
    rt = f.get(f"{base}/wp-json/wp/v2/types")
    try:
        bases = [v.get("rest_base") for k, v in rt.json().items() if k not in ("attachment", "nav_menu_item", "wp_block", "wp_template", "wp_template_part", "wp_global_styles", "wp_navigation", "wp_font_family", "wp_font_face")]
    except Exception:
        bases = ["pages", "posts"]
    for rb in bases:
        if not rb: continue
        r = f.get(f"{base}/wp-json/wp/v2/{rb}?per_page=100&_fields=id,link")
        try:
            for it in r.json():
                parents[it["id"]] = it["link"]
        except Exception:
            pass
    return [{"url": m["source_url"], "alt": (m.get("alt_text") or "").strip(), "parent": parents.get(m.get("post")), "mime": m.get("mime_type")} for m in out]


def head_sizes(urls, f):
    sizes = {}
    for u in urls:
        r = f.get(u, head=True)
        if r is not None and r.status_code == 200:
            try: sizes[u] = int(r.headers.get("Content-Length", 0))
            except Exception: sizes[u] = 0
        else:
            sizes[u] = None
    return sizes


def link_status(urls, f):
    res = {}
    for u in urls:
        r = f.get(u, allow_redirects=False)
        if r is None:
            res[u] = {"status": 0, "final": None}; continue
        fin = None
        if r.status_code in (301, 302, 303, 307, 308):
            r2 = f.get(u)
            fin = (r2.url, r2.status_code) if r2 is not None else None
        res[u] = {"status": r.status_code, "final": fin}
    return res


# ---------------- fallback crawler ----------------
def parse_page(url, html):
    soup = BeautifulSoup(html, "lxml")
    descs = [m.get("content", "") for m in soup.find_all("meta", attrs={"name": "description"})]
    title = soup.title.get_text(strip=True) if soup.title else ""
    heads = [(h.name, re.sub(r"\s+", " ", h.get_text(" ", strip=True))) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
    can = soup.find("link", rel="canonical"); rob = soup.find("meta", attrs={"name": "robots"})
    imgs = [{"src": urljoin(url, im.get("data-src") or im.get("data-lazy-src") or im.get("src") or ""), "alt": im.get("alt"), "has_alt": im.has_attr("alt")} for im in soup.find_all("img")]
    links = [{"href": urljoin(url, a["href"].strip()), "text": re.sub(r"\s+", " ", a.get_text(" ", strip=True)), "aria": a.get("aria-label") or "",
              "rel": " ".join(a.get("rel") or []), "target": a.get("target") or "", "img": bool(a.find("img"))} for a in soup.find_all("a", href=True)]
    jl = jsonld_types(soup)
    http_res = sorted(set(re.findall(r"""(?:src|href)=["'](http://[^"']+)""", html)))
    for t in soup(["script", "style", "noscript"]): t.decompose()
    text = soup.get_text(" ", strip=True)
    words = len(re.findall(r"[A-Za-z0-9'’-]+", text))
    return {"url": url, "title": title, "title_len": len(title), "title_px": 0, "desc": descs[0] if descs else "", "desc_len": len(descs[0]) if descs else 0,
            "desc2": descs[1] if len(descs) > 1 else "", "h1": [t for n, t in heads if n == "h1"], "h2": [t for n, t in heads if n == "h2"],
            "headings": heads, "canonical": can.get("href") if can else "", "robots": rob.get("content") if rob else "",
            "words": words, "text_ratio": round(len(text.encode()) / max(len(html.encode()), 1) * 100, 2), "images": imgs, "links": links,
            "jsonld": jl, "http_resources": http_res, "transferred": len(html.encode())}


def crawl(base, f, seeds=(), max_pages=500):
    host = host_of(base)
    queue = [base + "/"] + [s for s in seeds if host_of(s) == host]
    seen, pages, statuses = set(), [], {}
    while queue and len(pages) < max_pages:
        u = queue.pop(0).split("#")[0]
        if u in seen or re.search(r"\.(jpe?g|png|webp|gif|svg|pdf|zip|mp4|css|js|xml|txt)(\?|$)", u, re.I):
            continue
        seen.add(u)
        t0 = time.time(); r = f.get(u, allow_redirects=False)
        if r is None:
            statuses[u] = {"status": 0}; continue
        if r.status_code in (301, 302, 307, 308):
            statuses[u] = {"status": r.status_code, "redirect": urljoin(u, r.headers.get("Location", ""))}
            nxt = statuses[u]["redirect"]
            if host_of(nxt) == host: queue.append(nxt)
            continue
        statuses[u] = {"status": r.status_code}
        if r.status_code != 200 or "text/html" not in r.headers.get("Content-Type", ""):
            continue
        if CHALLENGE.search(r.text[:4000]):
            statuses[u] = {"status": 403, "blocked": True}; continue
        p = parse_page(u, r.text); p["status"] = 200; p["response_time"] = round(time.time() - t0, 2)
        p["indexability"] = "Non-Indexable" if "noindex" in (p["robots"] or "").lower() else "Indexable"
        pages.append(p)
        for l in p["links"]:
            h = l["href"].split("#")[0]
            if host_of(h) == host and h not in seen and h.startswith(("http://", "https://")):
                queue.append(h)
    return pages, statuses
