"""
Internshala scraper.
Confirmed working selectors:
  cards:  .individual_internship  (40 per page)
  title:  a[href*='/internship/detail/']
  meta:   .internship_meta
"""
import logging
import re
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
from scraper.base import get_browser_context, human_delay

logger = logging.getLogger(__name__)

BASE_URL = "https://internshala.com"
SEARCH_URLS = [
    f"{BASE_URL}/internships/python-internship/",
    f"{BASE_URL}/internships/web-development-internship/",
    f"{BASE_URL}/internships/machine-learning-internship/",
    f"{BASE_URL}/internships/data-science-internship/",
]


def _parse_deadline(text: str) -> datetime:
    text = (text or "").strip().lower()
    try:
        m = re.search(r"(\d+)\s*day", text)
        if m:
            return datetime.now(timezone.utc) + timedelta(days=int(m.group(1)))
        m = re.search(r"(\d{1,2})\s+([a-z]{3})", text)
        if m:
            day, mon = int(m.group(1)), m.group(2)
            return datetime.strptime(
                f"{day} {mon} {datetime.now().year}", "%d %b %Y"
            ).replace(tzinfo=timezone.utc)
    except Exception:
        pass
    return datetime.now(timezone.utc) + timedelta(days=30)


def _safe(el, selector: str) -> str:
    try:
        found = el.query_selector(selector)
        return found.inner_text().strip() if found else ""
    except Exception:
        return ""


def _scrape_url(page, url: str, seen_ids: set) -> list[dict]:
    listings = []
    logger.info(f"Internshala: loading {url}")

    try:
        page.goto(url, timeout=40_000, wait_until="domcontentloaded")
    except PWTimeout:
        logger.warning(f"Internshala: goto timeout for {url}")
        return []

    # Wait explicitly for the card container — this is the key fix
    try:
        page.wait_for_selector(".individual_internship", timeout=20_000)
    except PWTimeout:
        logger.warning(f"Internshala: cards never appeared on {url}")
        return []

    # Extra wait + scroll to ensure all 40 cards are rendered
    page.wait_for_timeout(2000)
    for _ in range(4):
        page.evaluate("window.scrollBy(0, 600)")
        page.wait_for_timeout(800)

    cards = page.query_selector_all(".individual_internship")
    logger.info(f"Internshala: {len(cards)} cards found on {url}")

    for card in cards:
        try:
            # ── Title + URL ──────────────────────────────────────────────────
            link_el = card.query_selector("a[href*='/internship/detail/']")
            if not link_el:
                continue
            title = link_el.inner_text().strip()
            href = link_el.get_attribute("href") or ""
            if not title or not href:
                continue

            apply_url = href if href.startswith("http") else urljoin(BASE_URL, href)
            external_id = href.rstrip("/").split("/")[-1]
            if not external_id or external_id in seen_ids:
                continue
            seen_ids.add(external_id)

            # ── Company ──────────────────────────────────────────────────────
            company = (
                _safe(card, ".company_name a")
                or _safe(card, ".company_name")
                or _safe(card, "a[href*='/company/']")
                or "Unknown"
            )

            # ── Location ─────────────────────────────────────────────────────
            location = (
                _safe(card, ".location_link")
                or _safe(card, ".locations_name")
                or _safe(card, "div[class*='location']")
                or "India"
            )

            # ── Stipend ──────────────────────────────────────────────────────
            stipend = _safe(card, ".stipend") or None

            # ── Duration ─────────────────────────────────────────────────────
            duration_els = card.query_selector_all(".other_detail_item .item_body")
            duration = duration_els[0].inner_text().strip() if duration_els else None

            # ── Deadline ─────────────────────────────────────────────────────
            deadline_text = (
                _safe(card, ".apply-by-text span")
                or _safe(card, ".apply_by")
            )
            deadline = _parse_deadline(deadline_text)

            # ── Skills ───────────────────────────────────────────────────────
            skill_els = card.query_selector_all(".round_tabs span, .skill-tag")
            skills = ", ".join(
                el.inner_text().strip() for el in skill_els if el.inner_text().strip()
            ) or None

            listings.append({
                "title": title[:255],
                "company": company[:255],
                "location": location[:255],
                "stipend": stipend,
                "duration": duration,
                "deadline": deadline,
                "apply_url": apply_url,
                "source_platform": "internshala",
                "external_id": f"internshala-{external_id}",
                "skills_required": skills,
                "description": None,
            })

        except Exception as e:
            logger.warning(f"Internshala: card parse error — {e}")
            continue

    logger.info(f"Internshala: extracted {len(listings)} listings from {url}")
    return listings


def scrape_internshala() -> list[dict]:
    all_listings = []
    seen_ids: set[str] = set()

    with sync_playwright() as p:
        browser, context = get_browser_context(p, headless=True)
        page = context.new_page()
        try:
            for url in SEARCH_URLS:
                results = _scrape_url(page, url, seen_ids)
                all_listings.extend(results)
                human_delay(3, 5)   # polite delay between pages
        except Exception as e:
            logger.error(f"Internshala fatal: {e}", exc_info=True)
        finally:
            page.close()
            context.close()
            browser.close()

    logger.info(f"Internshala: finished — {len(all_listings)} unique listings total")
    return all_listings
