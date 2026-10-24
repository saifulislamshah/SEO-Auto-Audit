# Report layouts (built by scripts/build_reports.py)

Common: header row frozen, filters on, severity colours (red = Error / Critical, yellow = Warning,
blue = Notice / Opportunity), every "✅" fix column on light green.

## Beginner: `<Client>_Full_SEO_Audit_Report_<date>.xlsx`
For a non-SEO person who will make the changes. Plain language, click-by-click steps for the detected CMS.
1. **Summary** - health overview (pages, Semrush health, PSI, broken links, stack), issue rows by severity and priority, Top 10 fixes with full steps.
2. **All Issues** - one row per issue per URL (site-wide issues collapsed into one row): URL | Issue | Severity | Source | Priority | Effort | Why it matters | ✅ How to fix | Evidence.
3. **Meta Titles** - URL | Focus Keyword | Current Title | Length | Pixels | Problem | ✅ Fixed Title | New Length.
4. **Meta Descriptions** - URL | Focus Keyword | Current | Length | 2nd description (duplicate tag) | Problem | ✅ Fixed Description | New Length.
5. **H1 & Headings** - URL | Focus Keyword | Current H1 | Problem | ✅ Fixed H1 | Current H2s | ✅ H2 fix.
6. **Image Alt Text** - one row per page × image + oversized images: Page URL | Image URL | Current Alt | Problem | ✅ Fixed Alt Text | KB | Source.
7. **Broken Links & Redirects** - one row per link: Source | Target | Status | Type | ✅ Fix.
8. **Technical SEO** - indexability, canonicals, robots, sitemap, HTTPS, headers, llms.txt, speed, stack, per-page speed.
9. **Structured Data** - per URL + recommended JSON-LD.
10. **Opportunities** - content gaps, local SEO, internal links, quick wins.
11. **Search Console** - only when GSC data was provided.
12. **Sources & Checks** - per issue: report rows vs Screaming Frog and Semrush counts.
Plus (Beginner/both): checklist tab in the master "SEO AUDIT CHECK LIST" workbook.

## Expert: `<Client>_SEO_Audit_Expert_<date>.xlsx`
For an SEO specialist. No explanations, grouped, short.
1. **Summary** - key metrics, issue types by severity, 10 priority fixes (one line each).
2. **Issues** - one row per issue type: Severity | Priority | Effort | Source | Issue | Data (counts per tool check) | URLs | Affected | ✅ Fix.
3. **Meta Titles / Meta Descriptions / H1 & Headings** - path-based, short issue codes, ✅ new values.
4. **Image Alt Text** - one row per image: File | Used on | KB (colour-coded) | ✅ Alt text.
5. **Links & Redirects** - grouped by target: Type | Found on | Links | Target | Status | ✅ Fix.
6. **Technical** - Area | Finding | Status | ✅ Action.
7. **Structured Data** - grouped by schema set + JSON-LD.
8. **Opportunities**, **Internal Links**, **Search Console** (if data).
