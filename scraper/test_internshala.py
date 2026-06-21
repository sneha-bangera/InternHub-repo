"""
Standalone test — runs the Internshala scraper directly (no Celery)
and prints what it finds. Run from internhub\ root:

  $env:PYTHONPATH = "."
  python scraper/test_internshala.py
"""
import sys, os
sys.path.insert(0, os.path.abspath("."))

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

from scraper.internshala import scrape_internshala

print("\n── Running Internshala scraper ──────────────────────")
results = scrape_internshala()
print(f"\n✅ Total collected: {len(results)}")
for i, r in enumerate(results[:5], 1):
    print(f"  {i}. {r['title']} @ {r['company']} | {r['location']} | {r['external_id']}")
if len(results) > 5:
    print(f"  ... and {len(results)-5} more")
