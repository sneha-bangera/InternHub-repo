"""
Debug script — opens Internshala / Wellfound in a VISIBLE browser window
and prints what HTML structure it finds. Run this when scrapers return 0 results
to discover the current CSS selectors.

Usage (venv active, from internhub\ root):
  PowerShell:  $env:PYTHONPATH="."; python scraper/debug_selectors.py internshala
  PowerShell:  $env:PYTHONPATH="."; python scraper/debug_selectors.py wellfound
"""
import sys
from playwright.sync_api import sync_playwright
from scraper.base import get_browser_context, human_delay

URLS = {
    "internshala": "https://internshala.com/internships/python-internship/",
    "wellfound": "https://wellfound.com/jobs?jobType=internship&locationNames=India",
}

PROBE_SELECTORS = {
    "internshala": [
        ".individual_internship",
        "[id^='internship_']",
        ".profile",
        "h3.profile",
        "div[class*='internship']",
        "a[href*='/internship/detail/']",
        ".internship_meta",
        "[class*='InternshipList']",
        "[class*='listing']",
    ],
    "wellfound": [
        "[data-test='StartupResult']",
        "div[class*='JobListing']",
        "div[class*='job-listing']",
        "div[class*='styles_component']",
        "article",
        "a[href*='/jobs/']",
        "a[href*='/role/']",
        "h2", "h3",
        "[class*='Result']",
    ],
}


def debug(site: str):
    url = URLS[site]
    selectors = PROBE_SELECTORS[site]

    print(f"\n🔍 Debugging {site}: {url}\n")
    with sync_playwright() as p:
        # headless=False so you can SEE the browser
        browser, context = get_browser_context(p, headless=False)
        page = context.new_page()
        page.goto(url, timeout=30_000, wait_until="domcontentloaded")
        human_delay(4, 6)

        # Scroll to load lazy content
        for _ in range(3):
            page.evaluate("window.scrollBy(0, 700)")
            human_delay(1, 2)

        print(f"Final URL: {page.url}\n")
        print("Selector probe results:")
        print("-" * 50)
        for sel in selectors:
            try:
                els = page.query_selector_all(sel)
                if els:
                    sample = els[0].inner_text().strip()[:80].replace("\n", " ")
                    print(f"  ✅ {sel:45s} → {len(els)} elements  |  sample: '{sample}'")
                else:
                    print(f"  ❌ {sel}")
            except Exception as e:
                print(f"  ⚠  {sel:45s} → error: {e}")

        print("\n📋 Page title:", page.title())
        print("\nPress Enter to close the browser...")
        input()
        browser.close()


if __name__ == "__main__":
    site = sys.argv[1] if len(sys.argv) > 1 else "internshala"
    if site not in URLS:
        print(f"Usage: python scraper/debug_selectors.py [internshala|wellfound]")
        sys.exit(1)
    debug(site)
