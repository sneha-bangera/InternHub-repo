"""
LinkedIn scraper.
LinkedIn aggressively blocks bots, so this scraper:
  - Uses realistic browser fingerprinting
  - Implements exponential backoff retry (3 attempts)
  - Gracefully skips/logs on block instead of crashing
  - Scrapes public job search results (no login required)
"""
import logging
import re
import time
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin, quote

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from scraper.base import get_browser_context, human_delay

logger = logging.getLogger(__name__)

SEARCH_URL = (
    "https://www.linkedin.com/jobs/search/"
    "?keywords=python%20intern&location=India&f_E=1&f_JT=I&position=1&pageNum=0"
)


def _parse_posted(text: str) -> datetime | None:
    text = text.strip().lower()
    try:
        m = re.search(r"(\d+)\s*(hour|day|week|month)", text)
        if not m:
            return None
        n, unit = int(m.group(1)), m.group(2)
        delta = {
            "hour": timedelta(hours=n),
            "day": timedelta(days=n),
            "week": timedelta(weeks=n),
            "month": timedelta(days=n * 30),
        }.get(unit, timedelta(days=30))
        return datetime.now(timezone.utc) - delta
    except Exception:
        return None


def _scrape_attempt() -> list[dict]:
    listings = []
    with sync_playwright() as p:
        browser, context = get_browser_context(p, headless=True)
        page = context.new_page()
        try:
            logger.info("LinkedIn: navigating to job search...")
            page.goto(SEARCH_URL, timeout=30_000, wait_until="domcontentloaded")
            human_delay(3, 5)

            # Check if we're blocked
            if "authwall" in page.url or "checkpoint" in page.url:
                raise Exception("LinkedIn blocked: auth wall detected")

            # Scroll to load more results
            for _ in range(3):
                page.evaluate("window.scrollBy(0, 800)")
                human_delay(1.5, 2.5)

            try:
                page.wait_for_selector(".jobs-search__results-list li, .base-card", timeout=10_000)
            except PWTimeout:
                logger.warning("LinkedIn: no job cards found — possibly blocked or layout changed")
                return []

            cards = page.query_selector_all(".jobs-search__results-list li, .base-card")
            logger.info(f"LinkedIn: found {len(cards)} job cards")

            for card in cards[:20]:   # cap at 20
                try:
                    title_el = card.query_selector("h3.base-search-card__title, h3")
                    title = title_el.inner_text().strip() if title_el else ""
                    if not title:
                        continue

                    company_el = card.query_selector("h4.base-search-card__subtitle, a.hidden-nested-link")
                    company = company_el.inner_text().strip() if company_el else "Unknown"

                    location_el = card.query_selector(".job-search-card__location, span.job-result-card__location")
                    location = location_el.inner_text().strip() if location_el else "India"

                    time_el = card.query_selector("time")
                    deadline = _parse_posted(time_el.inner_text()) if time_el else None

                    link_el = card.query_selector("a.base-card__full-link, a")
                    href = link_el.get_attribute("href") if link_el else None
                    if not href:
                        continue
                    # Strip tracking params
                    apply_url = href.split("?")[0]
                    external_id = apply_url.rstrip("/").split("/")[-1]

                    listings.append({
                        "title": title,
                        "company": company,
                        "location": location,
                        "deadline": deadline,
                        "apply_url": apply_url,
                        "source_platform": "linkedin",
                        "external_id": f"linkedin-{external_id}",
                        "skills_required": None,
                        "description": None,
                        "stipend": None,
                        "duration": None,
                    })
                    human_delay(0.5, 1.0)
                except Exception as e:
                    logger.warning(f"LinkedIn: card parse error — {e}")
                    continue

        except Exception as e:
            logger.error(f"LinkedIn scraper error: {e}")
            raise
        finally:
            page.close()
            context.close()
            browser.close()

    return listings


def scrape_linkedin() -> list[dict]:
    """
    Scrape LinkedIn with retry + graceful failure.
    If blocked after 3 retries, logs a warning and returns empty list (does not crash).
    """
    for attempt in range(1, 4):
        try:
            logger.info(f"LinkedIn scraper attempt {attempt}/3")
            results = _scrape_attempt()
            logger.info(f"LinkedIn: collected {len(results)} listings")
            return results
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"LinkedIn attempt {attempt} failed: {e}. Waiting {wait}s...")
            if attempt < 3:
                time.sleep(wait)
            else:
                logger.warning("LinkedIn: all 3 attempts failed — skipping gracefully")
                return []
    return []
