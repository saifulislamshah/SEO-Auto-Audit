# content.json guide

`content.json` holds everything that needs judgement. Start from `.seo-audit-work/content_template.json`
(it already lists every page and image number). `validate_content.py` enforces the hard rules.

## client
```json
"client": {"name": "Acme Roofing", "business_type": "Roofing contractor", "location": "Denver, CO",
           "service_area": "Denver metro", "phone": "(303) 555-0100", "address": "123 Main St, Denver, CO 80202",
           "made_by": "", "date": "2026-10-24", "notes": "Assumed business type from homepage"}
```
`made_by` stays empty unless the user named someone. `date` = report date (YYYY-MM-DD).

## semrush_overview / psi
Numbers read from screenshots. Keep units as shown (`"55.1 s"`, `"1,700 ms"`). `payload_kib`, `unused_js_kib`,
`render_blocking_ms` as shown. `field_data`: e.g. `"No Data (CrUX)"` or the CWV assessment. Leave `null` if absent:
the reports then say "Needs manual check".

## pages (one entry per crawled HTML page, keyed by full URL)
| field | rule |
|---|---|
| focus_keyword | The query this page should rank for. Service + city for local businesses ("roof repair Denver"). Legal pages: "(legal page)". Secondary keyword may follow in brackets: `"roofer Denver (secondary: roof replacement Denver)"`. |
| title | 50-60 chars. Keyword near the front, brand at the end after ` \| `. Unique. Sentence/title case, not ALL CAPS. |
| description | 140-160 chars. Includes keyword (or close variant), a concrete benefit/detail from the page, and a CTA (Call…, Book…, Get a quote…, Read…). Unique. |
| h1 | One per page, contains the keyword naturally, different wording from the title. |
| h2_note | One line: what to change in the H2s ("Add H2s: process, pricing, FAQ"; "OK"). |

Base titles/descriptions on the page's real content (`page_digest.json`), not on the URL alone.

## alts
`{"1": "Kitchen remodel with white oak island and pendant lights in Austin", "2": "DECORATIVE", ...}`.
Every number in `img_index.json`. < 125 chars. Look at the image first (contact sheets).

## findings (issues the tools miss)
```json
{"issue": "NAP mismatch between website and directories", "severity": "Warning", "priority": "High", "effort": "Medium",
 "urls": ["site-wide"], "source": "Live check",
 "why": "Google trusts businesses whose name, address and phone match everywhere.",
 "fix": "Decide the official address and phone, then update Google Business Profile, Yelp, ... and the footer.",
 "fix_expert": "Align NAP across GBP, directories and site",
 "data": "Site: 123 Main St · (303) 555-0100 | Yelp: 99 Oak Ave · (303) 555-0199"}
```
Severity one of `Error / Critical`, `Warning`, `Notice / Opportunity`. Priority `High|Medium|Low`. Effort `Easy|Medium|Hard`.
Typical findings: typos in key copy, wrong city in slug/title, NAP mismatch, AI/stock renderings presented as real
projects, duplicate theme/plugin tags, cookie banner covering content, missing service/location pages.

## opportunities
`{"type": "Content gap|Local SEO|Internal linking|Quick win|Reviews|E-E-A-T|Content refresh|Cannibalization",
  "area": "New page | URL | Whole site", "opportunity": "...", "why": "...", "action": "beginner steps",
  "priority": "High", "effort": "Hard"}`. 8-15 items, specific to this business.

## internal_links
`{"from": "https://site/blog/post/", "to": "https://site/service/", "anchor": "roof repair in Denver"}`.
Prioritise pages Semrush/SF flag as weakly linked (1 incoming link, crawl depth 3+).

## top_fixes (10, in order)
`{"fix": "plain-language fix", "fix_expert": "short technical fix", "why": "...", "severity": "...", "effort": "...",
  "issue_id": "desc_missing"}`. `issue_id` = a key in `audit_data.json` → issues (or `psi_mobile`, `psi_desktop`,
`psi_tbt`, `psi_weight`, `finding_<n>`) so the Beginner summary pulls the right click-by-click steps.
Or give `"how": "..."` to write the steps yourself.

## schema
`{"type": "Plumber", "jsonld": "{...valid JSON-LD...}", "notes": "Confirm NAP before publishing"}`. Pick the most
specific LocalBusiness subtype (GeneralContractor, Plumber, Dentist, MedicalClinic, LegalService, Restaurant...).
Only verified NAP/URLs; `sameAs` only for profiles you found.

## search_console (only when GSC data exists)
`{"summary": "1,240 clicks / 3 months; 38 pages with impressions",
  "striking_distance": [{"query": "...", "page": "...", "clicks": 3, "impressions": 900, "ctr": "0.3%", "position": 8.4, "action": "Add query to H2 + FAQ; internal link from ..."}],
  "low_ctr_pages": [{"page": "...", "impressions": 4000, "ctr": "0.4%", "position": 5.1, "action": "Rewrite title/description (see sheets)"}]}`

## checklist_overrides (optional)
`{"backlinks come from trustworthy": ["Need To Improve", "42 referring domains; 6 toxic (Semrush)"],
  "google business profile optimized": ["Fail", "No GBP found for the business name"]}` - the key is a
lowercase fragment of the checklist question.
