"""
Shared utilities for all scrapers:
  - random delay between requests
  - realistic User-Agent header
  - retry logic with exponential backoff
  - Playwright browser launch helper
"""
import asyncio
import logging
import random
import time
from typing import Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
]


def random_user_agent() -> str:
    return random.choice(USER_AGENTS)


def human_delay(min_s: float = 2.0, max_s: float = 4.5) -> None:
    """Sleep for a random duration to mimic human browsing."""
    time.sleep(random.uniform(min_s, max_s))


def get_browser_context(playwright, headless: bool = True) -> tuple:
    """
    Launch Chromium and return (browser, context) with realistic settings.
    Caller is responsible for closing both.
    """
    browser = playwright.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    )
    context = browser.new_context(
        user_agent=random_user_agent(),
        viewport={"width": 1366, "height": 768},
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        extra_http_headers={
            "Accept-Language": "en-IN,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        },
    )
    # Hide webdriver fingerprint
    context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
    """)
    return browser, context


def safe_text(page: Page, selector: str, default: str = "") -> str:
    """Extract text from a selector, returning default if not found."""
    try:
        el = page.query_selector(selector)
        return el.inner_text().strip() if el else default
    except Exception:
        return default


def safe_attr(page: Page, selector: str, attr: str, default: str = "") -> str:
    """Extract an attribute from a selector, returning default if not found."""
    try:
        el = page.query_selector(selector)
        return (el.get_attribute(attr) or default).strip() if el else default
    except Exception:
        return default
