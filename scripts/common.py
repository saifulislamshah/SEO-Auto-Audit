"""Shared helpers for seo-auto-audit scripts."""
import os, re, sys, json, html as _html
from urllib.parse import urlparse

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REQUIRED = ["pandas", "openpyxl", "requests", "bs4", "lxml", "PIL"]


def ensure_deps():
    missing = []
    for m in REQUIRED:
        try:
            __import__(m)
        except ImportError:
            missing.append({"bs4": "beautifulsoup4", "PIL": "pillow"}.get(m, m))
    if missing:
        print("MISSING PYTHON PACKAGES: " + " ".join(missing))
        print("Install with:  python -m pip install " + " ".join(missing))
        sys.exit(2)


def work_dir(client_folder):
    d = os.path.join(client_folder, ".seo-audit-work")
    os.makedirs(d, exist_ok=True)
    return d


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)


def unesc(s):
    return _html.unescape(str(s)) if s is not None else s


def path_of(url, base):
    u = str(url)
    if base and u.startswith(base):
        u = u[len(base):]
    return u or "/"


def host_of(url):
    return urlparse(str(url)).netloc.lower().removeprefix("www.")


SIZE_RE = re.compile(r"-\d+x\d+(?=\.[A-Za-z0-9]+$)")


def norm_img(url):
    """Strip WordPress size suffixes so sized variants map to the original file."""
    u = SIZE_RE.sub("", str(url))
    return u


def is_caps(s):
    letters = re.sub(r"[^A-Za-z]", "", str(s).split(" - ")[0].split(" | ")[0])
    return len(letters) > 3 and letters.isupper()


def isnan(v):
    try:
        return v is None or (isinstance(v, float) and v != v)
    except Exception:
        return False


def clean(v, default=""):
    return default if isnan(v) else v


SEVERITIES = ["Error / Critical", "Warning", "Notice / Opportunity"]
PRIORITIES = ["High", "Medium", "Low"]
SEV_ORDER = {s: i for i, s in enumerate(SEVERITIES)}
PRI_ORDER = {p: i for i, p in enumerate(PRIORITIES)}

# ---------- Excel styling (shared by both report levels) ----------
NAVY = "1F4E78"; GREEN_HDR = "548235"; FIX = "E2EFDA"
SEV_FILL = {"Error / Critical": "F8CBAD", "Warning": "FFE699", "Notice / Opportunity": "DDEBF7"}
PRI_FILL = {"High": "F8CBAD", "Medium": "FFE699", "Low": "E2EFDA"}
STATUS_FILL = {"OK": "E2EFDA", "Issue": "F8CBAD", "Problem": "F8CBAD", "Manual check": "FFE699",
               "Needs manual check": "FFE699", "N/A": "EDEDED", "Not applicable": "EDEDED", "Info": "DDEBF7", "Improve": "FFE699"}


def _x():
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    return PatternFill, Font, Alignment, Border, Side


def fill(c):
    PatternFill = _x()[0]
    return PatternFill("solid", fgColor=c)


def border():
    _, _, _, Border, Side = _x()
    t = Side(style="thin", color="BFBFBF")
    return Border(left=t, right=t, top=t, bottom=t)


def write_table(ws, headers, rows, widths, fix_cols=(), sev_col=None, pri_col=None, status_col=None):
    _, Font, Alignment, _, _ = _x()
    B = border()
    ws.append(headers)
    for i, h in enumerate(headers, 1):
        c = ws.cell(1, i)
        c.fill = fill(GREEN_HDR if h in fix_cols else NAVY)
        c.font = Font(bold=True, color="FFFFFF")
        c.alignment = Alignment(wrap_text=True, vertical="center")
        c.border = B
    for r in rows:
        ws.append([("" if isnan(v) else v) for v in r])
    fix_idx = {headers.index(h) + 1 for h in fix_cols if h in headers}
    idx = lambda name: headers.index(name) + 1 if name and name in headers else None
    s_i, p_i, st_i = idx(sev_col), idx(pri_col), idx(status_col)
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, max_col=len(headers)):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
            c.border = B
            if c.column in fix_idx:
                c.fill = fill(FIX)
            if c.column == s_i and c.value in SEV_FILL:
                c.fill = fill(SEV_FILL[c.value])
            if c.column == p_i and c.value in PRI_FILL:
                c.fill = fill(PRI_FILL[c.value])
            if c.column == st_i and c.value in STATUS_FILL:
                c.fill = fill(STATUS_FILL[c.value])
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{ws.cell(1, len(headers)).column_letter}{max(ws.max_row, 2)}"
    ws.row_dimensions[1].height = 30


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9]+", "", str(s)) or "Client"
