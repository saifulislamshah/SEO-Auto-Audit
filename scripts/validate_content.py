"""Validate .seo-audit-work/content.json before building reports.

Usage: python validate_content.py <client_folder>
Rules: every HTML page has focus keyword, title (50-60), description (140-160), H1 (different from title);
every image needing alt has alt text (<125 chars) or "DECORATIVE"; required client fields present.
Exit code 1 if anything must be fixed.
"""
import os, sys, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import work_dir, load_json

folder = os.path.abspath(sys.argv[1]); WD = work_dir(folder)
data = load_json(os.path.join(WD, "audit_data.json"))
c = load_json(os.path.join(WD, "content.json"))
if c is None:
    print("content.json not found. Copy content_template.json to content.json and fill it in."); sys.exit(1)
errs, warns = [], []
pages = [p["url"] for p in data["pages"]]
cp = c.get("pages", {})
brand_seen = set()
for u in pages:
    e = cp.get(u)
    if not e:
        errs.append(f"page missing in content.json: {u}"); continue
    for k in ("focus_keyword", "title", "description", "h1"):
        if not (e.get(k) or "").strip(): errs.append(f"{u}: empty {k}")
    t, d, h = e.get("title", ""), e.get("description", ""), e.get("h1", "")
    if t and not 50 <= len(t) <= 60: errs.append(f"{u}: title {len(t)} chars (need 50-60): {t}")
    if d and not 140 <= len(d) <= 160: errs.append(f"{u}: description {len(d)} chars (need 140-160)")
    if h and t and h.strip().lower() == re.split(r"\s[|\-–]\s", t)[0].strip().lower(): errs.append(f"{u}: H1 identical to title text")
    if t and "|" in t: brand_seen.add(t.split("|")[-1].strip())
titles = [cp.get(u, {}).get("title", "") for u in pages]
dups = {t for t in titles if t and titles.count(t) > 1}
for t in dups: errs.append(f"duplicate new title: {t}")
descs = [cp.get(u, {}).get("description", "") for u in pages]
for d in {d for d in descs if d and descs.count(d) > 1}: errs.append(f"duplicate new description: {d[:60]}...")
idx = load_json(os.path.join(WD, "img_index.json"), [])
alts = c.get("alts", {})
for i in idx:
    v = (alts.get(str(i["n"])) or "").strip()
    if not v: errs.append(f"image #{i['n']} has no alt text: {i['url']}")
    elif v != "DECORATIVE" and len(v) > 125: errs.append(f"image #{i['n']} alt over 125 chars")
cl = c.get("client", {})
for k in ("name", "business_type", "location"):
    if not (cl.get(k) or "").strip(): warns.append(f"client.{k} empty")
psi = c.get("psi", {})
if not any((psi.get(x) or {}).get("performance") is not None for x in ("mobile", "desktop")):
    warns.append("no PageSpeed numbers in content.json (speed will be marked 'Needs manual check')")
if not c.get("top_fixes"): warns.append("top_fixes empty (summary will use the highest-severity issues)")
if not c.get("opportunities"): warns.append("opportunities empty")
if len(brand_seen) > 1: warns.append(f"inconsistent brand suffix in titles: {brand_seen}")
for w in warns: print("WARN:", w)
for e in errs: print("ERROR:", e)
print(f"pages {len(pages)} · images {len(idx)} · errors {len(errs)} · warnings {len(warns)}")
sys.exit(1 if errs else 0)
