# seo-auto-audit (Claude Code skill)

Created by **Saiful Islam Shah**.

Turn a folder of SEO exports into a finished Excel audit with ready-to-paste fixes.

```
/seo-auto-audit acme.com beginner
/seo-auto-audit acme.com expert
/seo-auto-audit acme.com both made by Jane Doe
```

- **Beginner** → `<Client>_Full_SEO_Audit_Report_<date>.xlsx`: every issue per URL with "why it matters" and
  click-by-click fixes for the site's CMS (WordPress + Yoast / Rank Math / AIOSEO, Elementor, Shopify, Wix,
  Squarespace, generic), plus a tab in your "SEO AUDIT CHECK LIST" workbook (or a new checklist file).
- **Expert** → `<Client>_SEO_Audit_Expert_<date>.xlsx`: grouped issue types with per-tool counts, affected URLs and
  one-line fixes. No explanations.
- Both include new titles (50-60 chars), descriptions (140-160), H1s, alt text written after viewing every image,
  broken links/redirects, technical SEO, structured data with ready JSON-LD, opportunities and internal links.

## Install
Copy this folder to `~/.claude/skills/seo-auto-audit/` (all projects) or `<project>/.claude/skills/seo-auto-audit/`.
Requires Python 3.10+ and: `python -m pip install -r requirements.txt`.

## Folder layout (anything optional)
```
acme.com/
  screaming frog export/        (Screaming Frog CSV export; dated sub-folders OK)
  Semrush Audit/                (Semrush Site Audit xlsx: issues, mega export, pages, structured data)
  pagespeed.web.dev-mobile.png  (PageSpeed Insights screenshots)
  pagespeed.web.dev-desktop.png
  semrush overview.png
  Queries.csv / Pages.csv       (Search Console export, optional)
  brief.txt                     (brand, NAP, services, target keywords, optional)
```
No Screaming Frog export? The skill crawls the site itself. See `references/data_sources.md` for every
supported input and which extra data improves the audit.

## How it works
`scripts/collect.py` parses and merges the exports and runs live checks → `audit_data.json`.
Claude reads screenshots, researches the business, views every image and writes `content.json`
(keywords, titles, descriptions, H1s, alt text, findings, opportunities). `validate_content.py` enforces the
rules; `build_reports.py` builds and verifies the workbooks; `checklist.py` fills the checklist tab.
Intermediate files go to `<client folder>/.seo-audit-work/` (safe to delete).

## Privacy
Everything runs locally. Reports are never uploaded. The skill only sends normal HTTP requests to the audited site.

MIT licensed © 2026 Saiful Islam Shah.
