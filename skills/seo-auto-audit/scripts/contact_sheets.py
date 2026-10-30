"""Download every image that needs alt text and build numbered contact sheets (12 per sheet)
so Claude can look at each photo and write accurate alt text.

Usage: python contact_sheets.py <client_folder>
Reads .seo-audit-work/img_index.json, writes .seo-audit-work/sheets/sheet_XX.jpg
"""
import os, sys, io, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import work_dir, load_json, ensure_deps
ensure_deps()
import requests
from PIL import Image, ImageDraw, ImageFont

folder = os.path.abspath(sys.argv[1]); WD = work_dir(folder)
idx = load_json(os.path.join(WD, "img_index.json"), [])
IM = os.path.join(WD, "imgs"); SH = os.path.join(WD, "sheets")
os.makedirs(IM, exist_ok=True); os.makedirs(SH, exist_ok=True)
s = requests.Session(); s.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"

def fetch(url, fn):
    if os.path.exists(fn): return True
    for attempt in range(3):
        try:
            r = s.get(url, timeout=60)
            if r.status_code == 200 and r.content:
                open(fn, "wb").write(r.content); return True
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return False

def load(fn, svg):
    if svg:
        return None
    try:
        return Image.open(fn).convert("RGB")
    except Exception:
        return None

TW, TH, COLS, ROWS = 420, 315, 4, 3
try:
    font = ImageFont.load_default(size=28)
except TypeError:
    font = ImageFont.load_default()
per = COLS * ROWS
failed = []
import hashlib
# cache by URL, not by number: numbers change when img_index.json is rebuilt
cache = lambda it: os.path.join(IM, hashlib.md5(it["url"].encode()).hexdigest()[:16] + ".img")
for i in idx:
    fn = cache(i)
    if not fetch(i["url"], fn): failed.append(i["n"])
    time.sleep(0.2)
for start in range(0, len(idx), per):
    chunk = idx[start:start + per]
    sheet = Image.new("RGB", (TW * COLS, TH * ROWS), "white"); dr = ImageDraw.Draw(sheet)
    for k, it in enumerate(chunk):
        x, y = (k % COLS) * TW, (k // COLS) * TH
        im = load(cache(it), it.get("svg"))
        if im is not None:
            im.thumbnail((TW - 6, TH - 6)); sheet.paste(im, (x + 3, y + 3))
        else:
            name = it["url"].rsplit("/", 1)[-1]
            dr.text((x + 10, y + 120), ("SVG: " if it.get("svg") else "NO PREVIEW: ") + name[:34], fill="black")
            dr.text((x + 10, y + 150), name[34:68], fill="black")
        dr.rectangle([x + 3, y + 3, x + 80, y + 40], fill="yellow")
        dr.text((x + 8, y + 6), str(it["n"]), fill="black", font=font)
    sheet.save(os.path.join(SH, f"sheet_{start // per + 1:02d}.jpg"), quality=80)
print(f"images: {len(idx)}  sheets: {(len(idx) + per - 1) // per}  folder: {SH}")
if failed: print("download failed for image numbers:", failed)
