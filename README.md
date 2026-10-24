# SEO-Auto-Audit

A Claude Code skill that turns your **Screaming Frog**, **Semrush** and **PageSpeed Insights** exports into a
finished Excel SEO audit with ready-to-paste fixes, in about 30 minutes instead of half a day.

Created by **Saiful Islam Shah**.

```
/seo-auto-audit acme.com beginner
/seo-auto-audit acme.com expert
/seo-auto-audit acme.com both made by Your Name
```

## What you get

| Level | File | For |
|---|---|---|
| **Beginner** | `<Client>_Full_SEO_Audit_Report_<date>.xlsx` | Clients, developers, anyone without SEO experience. Every issue per URL, "why it matters", and click-by-click fixes for the site's CMS (WordPress + Yoast / Rank Math / AIOSEO, Elementor, Shopify, Wix, Squarespace). Also fills an "SEO AUDIT CHECK LIST" tab. |
| **Expert** | `<Client>_SEO_Audit_Expert_<date>.xlsx` | SEO specialists. One row per issue type with per-tool counts, affected URLs and one-line fixes. No explanations. |

Both include:
- New **meta titles** (50-60 chars), **meta descriptions** (140-160 chars) and **H1s** for every page, with character counts.
- **Alt text for every image**, written after Claude looks at each photo.
- Broken links and redirects, technical SEO, structured data with ready JSON-LD, opportunities and internal-link suggestions.
- Issues from Screaming Frog and Semrush **merged and de-duplicated by URL** (`Source: SF + Semrush`).

## Requirements

- [Claude Code](https://claude.com/claude-code)
- Python 3.10+ with: `pandas openpyxl requests beautifulsoup4 lxml pillow`

## Install

### Option A: plugin (recommended)
In Claude Code:
```
/plugin marketplace add saifulislamshah/SEO-Auto-Audit
/plugin install seo-auto-audit@seo-auto-audit
```
Then install the Python packages once:
```
python -m pip install pandas openpyxl requests beautifulsoup4 lxml pillow
```
Plugin skills are namespaced, so type `/seo-auto-audit` and pick the skill from the list
(it may show as `/seo-auto-audit:seo-auto-audit`).

### Option B: copy the skill folder
1. Download this repo (Code > Download ZIP) or `git clone https://github.com/saifulislamshah/SEO-Auto-Audit.git`
2. Copy `skills/seo-auto-audit` into your skills folder:
   - Windows: `C:\Users\<you>\.claude\skills\seo-auto-audit`
   - macOS / Linux: `~/.claude/skills/seo-auto-audit`
3. `python -m pip install -r ~/.claude/skills/seo-auto-audit/requirements.txt`
4. Restart Claude Code and type `/seo-auto-audit`.

## Set up a client folder

```
acme.com/
  screaming frog export/        Screaming Frog: Bulk Export > All + Reports > Issues (CSV)
  Semrush Audit/                Semrush Site Audit exports: Issues, Mega export, Crawled pages, Structured data (xlsx)
  pagespeed-mobile.png          Full-page screenshot of pagespeed.web.dev (mobile)
  pagespeed-desktop.png         ...and desktop
  semrush overview.png          Semrush Site Audit overview screenshot (optional)
  brief.txt                     Brand, address/phone, services, target keywords (optional)
```
Everything is optional: with no Screaming Frog export the skill crawls the site itself.
Open Claude Code in the parent folder and run `/seo-auto-audit acme.com beginner` (or `expert`, or `both`).

## Make the audit even better

Add any of these to the client folder and the skill uses them automatically:
- **Google Search Console**: Performance export (Queries / Pages, last 3 months), Page indexing export.
- **Google Business Profile**: screenshots of categories, address/phone and reviews.
- **Backlinks**: Semrush Backlink Analytics or Ahrefs export.
- **GA4**: landing-page report.

Details: [`skills/seo-auto-audit/references/data_sources.md`](skills/seo-auto-audit/references/data_sources.md)

## How it works

1. `collect.py` reads and merges the exports, checks the live site (robots.txt, sitemaps, redirects, headers,
   CMS detection, image sizes) and writes `audit_data.json`.
2. Claude reads the screenshots, researches the business, views every image and writes `content.json`
   (keywords, titles, descriptions, H1s, alt text, findings, opportunities).
3. `validate_content.py` enforces the rules (lengths, uniqueness, nothing missing).
4. `build_reports.py` builds and verifies the Excel files; `checklist.py` fills the checklist tab.

Intermediate files go to `<client folder>/.seo-audit-work/` (safe to delete). Everything runs locally.

## License

MIT © 2026 Saiful Islam Shah
