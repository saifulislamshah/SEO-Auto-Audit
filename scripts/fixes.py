"""Beginner fix steps, adapted to the detected CMS / SEO plugin / page builder.
ctx = {"cms": "WordPress|Shopify|Wix|Squarespace|Webflow|Unknown", "seo_plugin": "Yoast|Rank Math|AIOSEO|None",
       "builder": "Elementor|Divi|Gutenberg|...", "domain": "example.com", "cdn": "Cloudflare|None", "host": "..."}"""


def _wp(ctx):
    plugin = ctx.get("seo_plugin")
    edit = "'Edit with Elementor'" if ctx.get("builder") == "Elementor" else "'Edit'"
    login = f"1) Log in to WordPress ({ctx.get('domain', 'your-site.com')}/wp-admin). 2) Pages, Posts or the custom post type (left menu) > hover the item > {edit}."
    if plugin == "Rank Math":
        box = "3) Open the Rank Math panel (Elementor: 'SEO' tab bottom-left; block editor: Rank Math icon top-right) > 'Edit Snippet'."
        tf, df = "'Title'", "'Description'"
    elif plugin == "AIOSEO":
        box = "3) Scroll to the 'AIOSEO Settings' box below the editor."
        tf, df = "'Post Title'", "'Meta Description'"
    elif plugin == "Yoast":
        box = "3) Open the Yoast SEO box (below the editor; in Elementor click the Yoast icon in the top bar)."
        tf, df = "'SEO title'", "'Meta description'"
    else:
        box = ("3) Open your SEO plugin panel: Yoast SEO box below the editor (field 'SEO title' / 'Meta description'), or Rank Math (Elementor: 'SEO' tab bottom-left; "
               "block editor: Rank Math icon top-right > 'Edit Snippet' > 'Title' / 'Description'). If no SEO plugin is installed: Plugins > Add New > 'Yoast SEO' > Install > Activate.")
        tf, df = "the SEO title field", "the meta description field"
    return login, box, tf, df


def render(key, ctx):
    cms = ctx.get("cms", "Unknown")
    wp = cms == "WordPress"
    if wp:
        login, box, tf, df = _wp(ctx)
    builder = ctx.get("builder")
    cdn = ctx.get("cdn")
    T = {}
    # ---------- titles / descriptions ----------
    if key == "title":
        if wp: return f"Paste the ✅ fixed title from 'Meta Titles'. {login} {box} 4) Replace the text in {tf} with the ✅ title. 5) Click 'Update'."
        if cms == "Shopify": return "Paste the ✅ fixed title from 'Meta Titles'. Shopify admin > Online Store > Pages (or Products / Collections / Blog posts) > open the item > 'Search engine listing' > Edit > 'Page title' > Save."
        if cms == "Wix": return "Paste the ✅ fixed title from 'Meta Titles'. Wix Editor > Pages menu > '⋯' next to the page > SEO basics > 'Title tag' > Save & Publish."
        if cms == "Squarespace": return "Paste the ✅ fixed title from 'Meta Titles'. Pages > gear icon next to the page > SEO tab > 'SEO title' > Save."
        return "Paste the ✅ fixed title from 'Meta Titles' into the page's SEO title field in your CMS (page settings > SEO), then publish."
    if key == "desc":
        if wp: return f"Paste the ✅ fixed description from 'Meta Descriptions'. {login} {box} 4) Paste it into {df}. 5) Click 'Update'."
        if cms == "Shopify": return "Paste the ✅ description from 'Meta Descriptions'. Online Store > Pages/Products/Collections > open item > 'Search engine listing' > Edit > 'Meta description' > Save."
        if cms == "Wix": return "Paste the ✅ description from 'Meta Descriptions'. Pages menu > '⋯' > SEO basics > 'Meta description' > Publish."
        if cms == "Squarespace": return "Paste the ✅ description from 'Meta Descriptions'. Pages > gear icon > SEO tab > 'SEO description' > Save."
        return "Paste the ✅ description from 'Meta Descriptions' into the page's meta description field in your CMS, then publish."
    if key == "duplicate_output":
        if wp: return ("Two tags are being output by the theme and the SEO plugin. 1) Appearance > Themes: note the theme. 2) Hello Elementor: Appearance > Hello Theme Settings (or Elementor > Hello) > turn ON "
                       "'Disable description meta tag'. Other themes: check theme options for 'SEO'/'meta description' and switch it off, or deactivate a second SEO plugin (Plugins > Installed). "
                       "3) View page source (Ctrl+U) and search 'name=\"description\"': only one should remain.")
        return "Your theme/app and SEO settings both output this tag. Turn off the duplicate in theme or app settings, then check page source (Ctrl+U) shows only one."
    # ---------- headings ----------
    if key == "h1":
        if wp and builder == "Elementor": return (f"Use the ✅ fixed H1 from 'H1 & Headings'. {login} 3) Click the main heading at the top. 4) Left panel (Content): type the ✅ H1 and set 'HTML Tag' = H1. "
                                                 "5) Any other heading set to H1 > change to H2. 6) Update. Blog posts/projects: Templates > Theme Builder > Single template > 'Post Title' widget > HTML Tag = H1.")
        if wp: return f"Use the ✅ fixed H1 from 'H1 & Headings'. {login} 3) Select the main heading block > set it to 'H1' in the block toolbar and type the ✅ H1. 4) Make sure no other block is H1. 5) Update."
        return "Use the ✅ fixed H1 from 'H1 & Headings'. In your page editor make the main heading 'Heading 1' with this text and set every other heading to Heading 2 or 3."
    if key == "h2":
        return ("See '✅ H2' column on 'H1 & Headings'. In the editor give each main section a 'Heading 2' with descriptive words, sub-sections 'Heading 3'. "
                "Don't jump from H1 straight to H4/H5, and don't reuse the same generic H2 text on many pages.")
    # ---------- images ----------
    if key == "alt":
        if wp: return (f"Paste the ✅ alt text from 'Image Alt Text'. 1) Log in to WordPress > Media > Library (List view). 2) Click the file > paste into 'Alternative Text' (saves automatically). "
                       + ("3) Elementor image widgets: open the page in Elementor > click the image > 'Choose Image' > re-select it so the new alt is used > Update. " if builder == "Elementor" else "")
                       + "Gallery images use the Media Library alt automatically.")
        if cms == "Shopify": return "Paste the ✅ alt text. Products > open product > click the image > 'Add alt text' > Save. Other images: Content > Files, or edit the section in the theme editor."
        if cms == "Wix": return "Paste the ✅ alt text. Click the image in the Editor > Settings (gear) > 'What's in the image? Tell Google' > Publish."
        if cms == "Squarespace": return "Paste the ✅ alt text. Edit the page > click the image block > pencil > 'Image alt text' (or the image caption field) > Save."
        return "Paste the ✅ alt text into the image's 'alt text' / 'alternative text' field in your CMS media library or image settings."
    if key == "img_compress":
        if wp: return ("1) BACK UP the site. 2) Plugins > Add New > install ONE image optimiser ('ShortPixel', 'EWWW Image Optimizer', 'Imagify', or LiteSpeed Cache image optimisation on LiteSpeed hosting). "
                       "3) Settings: lossy/glossy compression, 'resize large images' to max 1920 px wide, create WebP/AVIF. 4) Run 'Bulk Optimize' on the Media Library. 5) Re-test in PageSpeed Insights.")
        if cms == "Shopify": return "Shopify serves WebP automatically; re-upload very large originals resized to max 2048 px, or use an app like 'TinyIMG' / 'Crush.pics' to compress existing images."
        return "Resize images to max 1920 px wide and compress them (e.g. squoosh.app or tinypng.com) before uploading; use WebP where your platform allows. Re-upload and replace the old files."
    # ---------- speed ----------
    if key == "speed":
        if wp:
            s = ("1) BACK UP the site. 2) Use ONE caching/optimisation plugin (LiteSpeed Cache on LiteSpeed/Hostinger hosting; otherwise WP Rocket, or Autoptimize + WP Super Cache) and remove overlapping ones. "
                 "3) Turn on page cache, CSS/JS minify, 'Delay JavaScript execution', 'Remove unused CSS', lazy-load images. ")
            if builder == "Elementor":
                s += "4) Elementor > Settings > Features/Performance: enable 'Improved Asset Loading', 'Optimized DOM Output', 'Improved CSS Loading', 'Lazy Load Background Images'; disable unused widgets. "
            s += "5) Make the first (hero) image load immediately (no lazy-load, no slider fade). 6) Re-test mobile in PageSpeed Insights."
            return s
        return "Remove unused apps/scripts, compress images, avoid sliders/animations at the top of the page, and enable your platform's caching/CDN options. Re-test in PageSpeed Insights."
    # ---------- links ----------
    if key == "broken":
        return ("Find each broken link on the source page (see 'Broken Links & Redirects'). " + (f"{login} " if wp else "Open the page in your editor. ") +
                "Click the link > replace it with a working URL or remove it > Update. If the broken URL is an old page with backlinks, add a 301 redirect to the best replacement "
                + ("(Plugins > 'Redirection' > Add new)." if wp else "(your CMS's URL redirect settings)."))
    if key == "redirect_links":
        return ("Change each link to point straight to the final URL shown in 'Broken Links & Redirects'. " +
                ("Menus: Appearance > Menus; header/footer: Templates > Theme Builder > Header/Footer > Edit with Elementor; in-content links: edit the page > click the link > paste the final URL > Update."
                 if wp else "Edit the menu/footer/page where the link lives and paste the final URL."))
    if key == "external":
        return "Open each external link from 'Broken Links & Redirects' in a normal browser. If it works, no action (the site blocks bots). If it is dead, edit the page and link to a working source or remove the link."
    if key == "server":
        return "Contact your host with the URL and time of the error; check the hosting error log; temporarily disable recently added plugins/apps; re-crawl."
    if key == "pagination":
        return ("The 'next page / load more' control is not a real link, so Google can't reach older items. " +
                ("In Elementor/JetEngine/Posts widget settings set Pagination to 'Numbers' (real links) instead of 'Load more' / AJAX, or show all items on the archive page."
                 if wp else "Switch the listing to numbered pagination with real links, or show all items on one page."))
    if key == "internal_link":
        return ("Add links from related pages to the weak pages using descriptive anchor text (see 'Internal Links' / 'Opportunities'). " +
                (f"{login} 3) Select the words to link > link icon > paste the URL > Update. Add important pages to the menu (Appearance > Menus) or footer." if wp
                 else "Select the words in your editor > insert link > paste the URL. Add important pages to the menu/footer."))
    if key == "anchor":
        return ("Replace 'Read more' / empty links with descriptive text (e.g. 'Read: kitchen remodel cost guide'). For icon links (social icons, logo) add an aria-label: " +
                ("in Elementor > Advanced > Attributes: aria-label|<Brand> on Instagram. " if builder == "Elementor" else "in the link/icon settings add an accessible name. ") +
                "For image links make sure the image has alt text.")
    if key == "noopener":
        return "Links that open in a new tab need rel=\"noopener\". " + ("Elementor > click the icon/link > Link options (gear) > 'Open in new window' + add 'noopener' in Custom Attributes: rel|noopener." if builder == "Elementor" else "In the link settings add rel=\"noopener\" (most modern editors add it automatically when you re-save the link).")
    # ---------- indexing ----------
    if key == "canonical":
        if wp: return f"{login} {box} 4) Advanced tab > 'Canonical URL': leave empty (the plugin then self-canonicalises) unless the page is a deliberate duplicate. 5) Update. Check page source shows ONE canonical with the full https:// URL."
        return "Each indexable page should have one canonical tag pointing to its own full https:// URL. Fix the canonical field in your SEO settings."
    if key == "noindex":
        if wp: return f"Confirm each listed page should be hidden from Google. If it should rank: {login} {box} 4) Advanced > 'Allow search engines to show this page' = Yes. 5) Update. Also check Settings > Reading > 'Discourage search engines' is OFF."
        return "Confirm each listed page should be hidden from Google. If not, remove the 'noindex' / 'hide from search engines' setting in its SEO settings."
    if key == "nofollow":
        return "Remove rel=\"nofollow\" from links to your own pages (edit the link > uncheck 'nofollow'); keep it only for paid/untrusted external links."
    if key == "sitemap":
        if wp and ctx.get("seo_plugin") == "Yoast":
            return "Yoast SEO > Settings > Content types / Taxonomies / Advanced (Author archives): for tag, category, author and other archives you don't want in Google set 'Show in search results' = Off. This removes them from the sitemap. Then resubmit sitemap_index.xml in Google Search Console."
        if wp and ctx.get("seo_plugin") == "Rank Math":
            return "Rank Math > Sitemap Settings > Taxonomies/Authors: turn off sitemap inclusion for tag/author/empty archives; Titles & Meta > set those archives to noindex. Resubmit the sitemap in Search Console."
        return "Make sure the XML sitemap lists only indexable pages that are linked on the site; remove archives/tags you don't want in Google, then resubmit the sitemap in Search Console."
    if key == "robots":
        return "Open your-site.com/robots.txt. It should allow crawling (no 'Disallow: /' for all bots), not block CSS/JS, and contain 'Sitemap: https://your-site.com/sitemap.xml'. " + ("Edit it in Yoast > Tools > File editor or Rank Math > General Settings > Edit robots.txt." if wp else "Edit it in your platform's SEO settings.")
    # ---------- security ----------
    if key == "https":
        if wp: return "1) BACK UP. 2) Settings > General: both URLs start with https://. 3) Install 'Really Simple SSL' > enable 301 redirect. 4) Install 'Better Search Replace' > search http://your-domain > replace https://your-domain > all tables > run. 5) Clear caches and re-check pages for 'Not secure'."
        return "Turn on 'Force HTTPS/SSL' in your platform or hosting settings and update any hard-coded http:// links and images to https://."
    if key == "headers":
        if cdn == "Cloudflare":
            return "Cloudflare dashboard > SSL/TLS > Edge Certificates > enable 'HTTP Strict Transport Security (HSTS)' (max-age 6 months). Rules > Transform Rules > Modify Response Header: add X-Content-Type-Options: nosniff, X-Frame-Options: SAMEORIGIN, Referrer-Policy: strict-origin-when-cross-origin."
        if wp: return "Install 'Headers Security Advanced & HSTS WP' (or ask your host) and enable HSTS, X-Content-Type-Options, X-Frame-Options and Referrer-Policy. Keep CSP off until tested."
        return "Ask your host/platform support to add HSTS, X-Content-Type-Options, X-Frame-Options and Referrer-Policy response headers."
    if key == "llms":
        if wp and ctx.get("seo_plugin") == "Yoast": return "Yoast SEO > Settings > Site features > turn ON 'llms.txt'. Then open your-site.com/llms.txt to confirm it loads."
        return "Create a plain-text file 'llms.txt' (brand, services, locations, key page URLs) and upload it to the site root; confirm your-site.com/llms.txt loads."
    # ---------- content / schema ----------
    if key == "thin":
        return ("Open the page in the editor and add 300–500+ words of original, helpful text: what was done, who it is for, process, size/specs, timeline, location, and 3–5 FAQs. "
                "Mention the focus keyword and city naturally, link to the related service page, then Update.")
    if key == "duplicate_content":
        return "Merge duplicate pages into one (301 the others to it), or rewrite each so it is clearly unique; for deliberate duplicates set the canonical to the main version."
    if key == "readability":
        return "Use shorter sentences (under 20 words), short paragraphs, bullet lists and plain words; fix spelling/grammar."
    if key == "ai_content":
        return "Add a 2–3 sentence summary at the top that answers the main question, use question-style H2s, bullet lists, a short FAQ, and concrete facts (prices, timelines, names) with sources."
    if key == "schema":
        if wp: return "Copy the ✅ JSON-LD from 'Structured Data'. Install 'WPCode' > Code Snippets > Add Snippet > HTML Snippet > paste inside <script type=\"application/ld+json\">…</script> > Location: Site Wide Header > Activate. Test at search.google.com/test/rich-results."
        return "Copy the ✅ JSON-LD from 'Structured Data' into your site's header code area (Settings > Custom code / Code injection) and test at search.google.com/test/rich-results."
    if key == "js":
        return "Check that important text and links appear in the page source (Ctrl+U), not only after scripts run. Where they don't, use standard widgets/blocks that output plain HTML."
    if key == "url_rename":
        return "Rename files/URLs to lowercase-hyphenated English (images: re-upload or use a media-rename plugin), and 301-redirect old page URLs to new ones."
    if key == "hreflang":
        return "Each language version must list all versions (including itself) with correct codes (e.g. en-us) and link back; fix in your multilingual plugin settings (WPML / Polylang / Weglot)."
    return "See the Data/Evidence column and fix on the affected pages; re-crawl to confirm."
