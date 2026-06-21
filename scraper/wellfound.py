"""
Wellfound scraper — confirmed selectors from debug run.

Debug showed:
  - Page navigates away (context destroyed) → use wait_until="domcontentloaded" + no networkidle
  - a[href*='/jobs/']  → 49 elements (job links)
  - h3               → 16 elements (company names)
  - a[href*='/role/'] → 42 elements (role/category links — skip these)

Strategy: pair each h3 (company) with the nearest job link inside the same
parent container. Fall back to harvesting all /jobs/ hrefs with their
link text as the title.
"""
import logging
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from scraper.base import get_browser_context, human_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://wellfound.com"
SEARCH_URL = f"{BASE_URL}/jobs?jobType=internship&locationNames=India"


def scrape_wellfound() -> list[dict]:
    listings: list[dict] = []
    seen_ids: set[str] = set()

    with sync_playwright() as p:
        browser, context = get_browser_context(p, headless=True)
        page = context.new_page()
        try:
            logger.info(f"Wellfound: navigating to {SEARCH_URL}")

            # Use domcontentloaded — networkidle causes the "context destroyed" error
            try:
                page.goto(SEARCH_URL, timeout=35_000, wait_until="domcontentloaded")
            except PWTimeout:
                logger.warning("Wellfound: initial load timeout, continuing anyway")

            human_delay(4, 6)

            # If redirected to login/signup, bail early
            if any(x in page.url for x in ("login", "signup", "auth")):
                logger.warning(f"Wellfound: redirected to {page.url} — skipping")
                return []

            # Scroll to trigger lazy-loaded job cards
            for _ in range(5):
                page.evaluate("window.scrollBy(0, 600)")
                human_delay(1.5, 2.5)

            # ── Strategy 1: find job cards as parent containers of h3 + job link ──
            # Each visible job block has an h3 (company name) and a[href*='/jobs/'] nearby
            job_links = page.query_selector_all("a[href*='/jobs/']")
            logger.info(f"Wellfound: found {len(job_links)} job links")

            for link in job_links:
                try:
                    href = link.get_attribute("href") or ""
                    # Skip generic category/search links (they end in just /jobs or /jobs/)
                    if not href or href.rstrip("/") in ("/jobs", f"{BASE_URL}/jobs"):
                        continue
                    # Skip links with query params that look like search pages
                    if "jobType" in href or "locationNames" in href or "role=" in href:
                        continue

                    apply_url = href if href.startswith("http") else urljoin(BASE_URL, href)
                    external_id = href.rstrip("/").split("/")[-1]

                    if not external_id or len(external_id) < 2 or external_id in seen_ids:
                        continue
                    seen_ids.add(external_id)

                    # Title: text of the link itself
                    title = link.inner_text().strip()

                    # If the link text is too short/generic, try its children
                    if not title or len(title) < 4:
                        child = link.query_selector("h2, h3, span, p")
                        title = child.inner_text().strip() if child else ""

                    if not title or len(title) < 4:
                        continue

                    # Company: look for h3 near this link (sibling or parent's h3)
                    company = ""
                    try:
                        # Walk up to find a sibling h3
                        company = page.evaluate("""
                            el => {
                                let p = el.parentElement;
                                for (let i = 0; i < 5; i++) {
                                    if (!p) break;
                                    const h = p.querySelector('h3');
                                    if (h) return h.innerText.trim();
                                    p = p.parentElement;
                                }
                                return '';
                            }
                        """, link)
                    except Exception:
                        pass
                    company = (company or "Unknown")[:255]

                    # Location: look for location text near the link
                    location = ""
                    try:
                        location = page.evaluate("""
                            el => {
                                let p = el.parentElement;
                                for (let i = 0; i < 5; i++) {
                                    if (!p) break;
                                    // look for elements with location-like text
                                    const spans = p.querySelectorAll('span, div');
                                    for (const s of spans) {
                                        const t = s.innerText.trim();
                                        if (t.match(/india|remote|bangalore|mumbai|delhi|hyderabad|pune|chennai/i)) {
                                            return t.split('\\n')[0].trim();
                                        }
                                    }
                                    p = p.parentElement;
                                }
                                return 'India';
                            }
                        """, link)
                    except Exception:
                        pass
                    location = (location or "India")[:255]

                    listings.append({
                        "title": title[:255],
                        "company": company,
                        "location": location,
                        "stipend": None,
                        "duration": None,
                        "deadline": datetime.now(timezone.utc) + timedelta(days=30),
                        "apply_url": apply_url,
                        "source_platform": "wellfound",
                        "external_id": f"wellfound-{external_id}",
                        "skills_required": None,
                        "description": None,
                    })

                    human_delay(0.2, 0.6)

                except Exception as e:
                    logger.warning(f"Wellfound link error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Wellfound fatal: {e}", exc_info=True)
        finally:
            try:
                page.close()
                context.close()
                browser.close()
            except Exception:
                pass

    logger.info(f"Wellfound: collected {len(listings)} listings")
    return listings
