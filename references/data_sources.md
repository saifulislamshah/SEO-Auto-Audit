# Data sources

Put everything for one client in one folder (any sub-folder names). The skill detects files automatically.

## Supported now
| Source | What to put in the folder | Used for |
|---|---|---|
| Screaming Frog SEO Spider | Full export: *Reports > Crawl Overview* + *Bulk Export > All* + *Reports > Issues* (the usual multi-CSV export folder). Dated sub-folders are fine; the newest is used. | Pages, titles (chars + px), descriptions, H1/H2, status codes, redirects, broken links, images (alt, size), canonicals, directives, security headers, JS rendering, pagination, issues report |
| Semrush Site Audit | Exports: *Issues* (`_issues_`), *Mega export* (`_mega_export_`), *Crawled pages* (`_pages_`), *Structured data* (`_pages_structured_data_`) xlsx | Issue counts + affected URLs, Site Health inputs, internal linking, structured data items, AI-search checks |
| Semrush overview | Screenshot of Site Audit overview (file name containing "semrush" or "overview") | Site Health %, AI Search Health %, thematic scores |
| PageSpeed Insights | Full-page screenshots of pagespeed.web.dev for mobile and desktop (name contains "pagespeed"), or pasted text in a .txt/.md file | Scores, Core Web Vitals, LCP element, payload, render-blocking |
| Nothing from Screaming Frog | — | The skill crawls the site itself (max 500 pages) |

## Recommended extra inputs (make the audit sharper)
| Input | How to export | What it adds |
|---|---|---|
| **Google Search Console - Performance** | Search results > last 3 months > Export > CSV (gives `Queries.csv`, `Pages.csv`, ...) | Real queries, striking-distance keywords (position 4-20), low-CTR pages, better focus keywords |
| **Search Console - Page indexing** | Indexing > Pages > Export | Which pages are actually indexed and why others aren't (answers "Is the page indexed?") |
| **Search Console - Core Web Vitals** | Experience > Core Web Vitals > Open report > Export | Real-user CWV instead of lab-only data |
| **Google Business Profile** | Screenshots of the profile (categories, services, NAP, reviews) or a local rank grid (BrightLocal / Local Falcon) | GBP checklist answers, NAP consistency, local opportunities |
| **GA4** | Reports > Engagement > Landing page > Export CSV | Which pages bring traffic/leads → prioritisation |
| **Backlinks** | Semrush Backlink Analytics or Ahrefs: Referring domains + Backlinks CSV, Authority Score / DR screenshot | Off-page checklist, toxic links, anchor distribution |
| **Keywords** | Semrush Organic Research positions or Keyword Magic export | Focus keywords with volume; ranking gaps |
| **Competitors** | 2-3 competitor URLs in a `brief.txt` | Content gaps and positioning |
| **Client brief** | `brief.txt`: brand name, NAP, services, service areas, target keywords, priority pages | Removes guesswork |
| **PSI for key templates** | Screenshots for one service page and one blog post too | Speed beyond the homepage |

## Screaming Frog settings that help
- Configuration > Spider > Rendering: JavaScript (catches JS-only content/links).
- Configuration > Spider > Extraction: enable JSON-LD / Microdata + Schema.org and Google validation.
- Configuration > API Access: connect PageSpeed Insights, Search Console, GA4 (fills speed/traffic per URL).
- Crawl the XML sitemap too (Configuration > Spider > Crawl > XML Sitemaps) to find orphan URLs.
- Configuration > Content > Spelling & Grammar for copy errors.
- If the site has bot protection (Cloudflare / Hostinger), whitelist your IP or lower the crawl speed.

## How Claude should use extra data
- GSC queries/pages: fill `search_console` in content.json; prefer real queries as focus keywords.
- Indexing export: answer "Is the page indexed?" via `checklist_overrides`; add findings for important non-indexed pages.
- GBP / backlinks: `checklist_overrides` for the Off-page, GBP and Website Overview rows; opportunities.
- GA4: weight `top_fixes` toward pages with traffic/conversions.
