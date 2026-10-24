---
name: seo-auto-audit
description: Turn a client folder of SEO exports (Screaming Frog, Semrush Site Audit, PageSpeed Insights screenshots, optional Search Console / GA4 / backlink exports) into a finished Excel SEO audit with ready-to-paste fixes. Two levels - Beginner (step-by-step fixes a non-SEO person can follow, plus checklist tab) and Expert (compact, grouped, no explanations). Use when the user runs /seo-auto-audit, or asks to "audit this folder", "make the SEO audit report for <client>", "beginner/expert SEO audit".
argument-hint: <client folder> [beginner|expert|both] [made by <name>] [checklist <path>] [url <https://site>]
license: MIT (see LICENSE)
author: Saiful Islam Shah
---

# SEO Auto Audit

Created by Saiful Islam Shah.

Builds a complete SEO audit workbook from whatever is in a client folder. Scripts do the parsing, merging,
counting, formatting and verification so every report has the same structure. You (Claude) do the parts that
need judgement: reading screenshots, researching the business, writing keywords / titles / descriptions /
H1s / alt text (after looking at every image), findings, opportunities and the priority list.

Scripts live in `scripts/` next to this file. Below, `$SKILL` = this skill's folder and `$WORK` =
`<client folder>/.seo-audit-work/` (created automatically; all intermediate files go there).

## 0. Parse the request

`$ARGUMENTS` examples: `acme.com beginner` · `clients/acme.com folder - Expert` ·
`acme.com both made by Jane Doe` · `acme.com expert url https://www.acme.com`.

- **Folder**: resolve relative to the current working directory; if not found, search one level down for a
  folder with that name. Stop and ask if still not found.
- **Level**: `beginner`, `expert` or `both` (default **both** when not given). Case-insensitive.
- **Made by**: only if the user gives a name (`made by <name>`). Never invent one; leave it blank otherwise.
- **Checklist**: Beginner/both only. Optional explicit master workbook path after `checklist`.
- Check Python deps once: `python -m pip install -r $SKILL/requirements.txt` if `collect.py` reports missing packages.

Tell the user in one line what you are about to do (folder, level).

## 1. Inventory + collect (scripts)

```
python $SKILL/scripts/collect.py "<folder>" [--url https://site]
```
Runs inventory, loads Screaming Frog (any export layout; newest dated sub-folder) and Semrush xlsx exports,
runs live site checks (robots, sitemaps, llms.txt, redirects, security headers, CMS/plugin/builder detection,
analytics tags, WordPress media library alt + image sizes), fetches page text for writing, merges and
de-duplicates every issue by URL (`Source: SF + Semrush` when both report it), and writes
`$WORK/audit_data.json`, `page_digest.json`, `img_index.json`, `site_text.txt`, `content_template.json`.
- No Screaming Frog export → it crawls the site itself (polite, max 500 pages; `--max-pages`).
- It can take several minutes (HEAD requests for image sizes): run it in the background and keep working.
- If it reports bot protection / 403: say so; results may be partial; suggest whitelisting the IP or running
  Screaming Frog. Do not hammer the site.

Show the user a 5-8 line inventory summary (what was found, what is missing).

## 2. Read what scripts cannot

Use the Read tool on every file listed in `$WORK/inventory.json`:
- `images.pagespeed`: PageSpeed Insights screenshots. Identify mobile vs desktop from the page itself
  ("Emulated Moto G Power" = mobile, "Emulated Desktop" = desktop), not just the filename. Full-page captures
  are very tall: crop the metric area with Pillow into the scratchpad if the numbers are unreadable.
  Capture performance/accessibility/best-practices/SEO scores, FCP, LCP, TBT, CLS, SI, total payload, unused JS,
  render-blocking savings, LCP element, field-data (CrUX) status.
- `text_notes`: pasted PSI text or client notes. If a pasted "desktop" report has identical numbers to mobile,
  flag it and use the screenshot.
- `images.semrush_overview`: Site Health %, AI Search Health %, errors/warnings, crawled pages, thematic scores.
- `extra_data`: Search Console, GA4, backlink, keyword CSVs - see `references/data_sources.md` for what to extract.
- `images.other`: anything else (GBP screenshots, briefs).

## 3. Understand the business

Read `$WORK/site_text.txt` and `page_digest.json`. If the site blocked automated requests (collect.py warns;
`page_digest.json` empty or partial), use WebFetch on the homepage, contact page and key service pages; if that is
blocked too, write from Screaming Frog titles/H1/H2s, Semrush data and web search, and say so in the final message. Work out client name, business type, location /
service area, phone/address (NAP), main services. Use WebSearch (standard mode) 1-3 times to confirm how people
search for these services in that location and to compare NAP with directory listings (Google, Yelp, Houzz,
etc.). Anything you cannot verify → "Needs manual check". State your assumptions in the final message.

## 4. Alt text: look at every image

```
python $SKILL/scripts/contact_sheets.py "<folder>"
```
Then Read **every** `$WORK/sheets/sheet_XX.jpg` (12 numbered images each). Write alt text per number:
describe what is actually in the photo, < 125 characters, include the service/city naturally on some images
(not all), no "image of", no keyword stuffing. Mark renderings as "(rendering)". Icons, arrows, shapes and
spacers → `"DECORATIVE"`. Logos → "<Brand> logo". People → describe role; never guess a name.

## 5. Write `$WORK/content.json`

Copy `content_template.json` → `content.json` and fill it. Full field guide and examples:
`references/content_guide.md`. Essentials:
- `client`, `semrush_overview`, `psi` (from step 2).
- `pages[url]` for **every** page: `focus_keyword` (service + city where relevant; use GSC/Semrush keyword data
  if provided), `title` 50-60 chars keyword first, brand last (`Keyword Phrase | Brand`), `description` 140-160
  chars with keyword + clear CTA, `h1` one per page, contains keyword, different from title, `h2_note` one line.
  Every title and description must be unique.
- `alts`: every number from `img_index.json`.
- `findings`: issues only you can see (typos, wrong-city slugs, NAP mismatch, renderings shown as real work,
  missing service pages...). Each: issue, severity, priority, effort, urls (or ["site-wide"]), why, fix (beginner
  steps), fix_expert (one line), data.
- `opportunities`, `internal_links` (from → to → anchor), `schema` (ready JSON-LD for the right LocalBusiness
  subtype using only verified NAP), `top_fixes` (10, ordered, each with `fix`, `fix_expert`, `why`, `severity`,
  `effort`, and `issue_id` from audit_data issues or a PSI id like `psi_mobile` when it maps to one).
- Optional: `search_console` (striking-distance queries, low-CTR pages) and `checklist_overrides`
  (`{"question text fragment": ["Pass|Fail|Need To Improve|N/A", "suggestion"]}`) when GSC / GBP / backlink data exists.

Never invent data. If something can't be verified, write "Needs manual check" and why.

## 6. Validate, build, verify

```
python $SKILL/scripts/validate_content.py "<folder>"        # must end with errors 0; fix and re-run
python $SKILL/scripts/build_reports.py "<folder>" --mode <beginner|expert|both> [--made-by "<name>"]
python $SKILL/scripts/checklist.py "<folder>" [--made-by "<name>"] [--master "<xlsx>"]   # beginner/both only
```
- `build_reports.py` re-opens each workbook and verifies: fix cells filled, title/description lengths,
  row counts = pages, frozen headers. Fix any reported problem and rebuild.
- `checklist.py` finds a master checklist workbook (a sheet whose A1 is "SEO AUDIT CHECK LIST") in the parent
  folder; backs it up; adds a new tab named after the client (copy of the last checklist tab, values only);
  verifies all other tabs are unchanged. If a tab with that name exists it stops - ask the user for a name.
  With no master it creates `<Client>_SEO_Checklist_<date>.xlsx` from `assets/checklist_template.xlsx`.

Outputs (in the client folder): `<Client>_Full_SEO_Audit_Report_<date>.xlsx` (Beginner),
`<Client>_SEO_Audit_Expert_<date>.xlsx` (Expert). Sheet layouts: `references/report_layout.md`.

## 7. Final message to the user

Lead with the result. Then: total issues by severity, top 5 fixes, file names (as links), the main
"Needs manual check" items, and which extra data would sharpen the audit (see `references/data_sources.md`,
"Recommended extra inputs") if it was missing. Keep it short; no step-by-step recap.

## Rules

- Never modify the client's input files; only add the report files (and the checklist tab with a backup).
- Never publish or share reports anywhere; they stay local.
- Beginner text = plain language, click-by-click for the detected CMS. Expert text = one line, no explanations.
- Respect the site: delays between requests, stop on repeated 403/429.
- Re-running is safe: scripts cache page text and images in `$WORK`.
