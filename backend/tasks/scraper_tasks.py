"""
Celery tasks that run each scraper and upsert results into PostgreSQL.
"""
import logging
from backend.celery_app import celery_app
from backend.db.database import SessionLocal
from backend.api.crud import upsert_listing

logger = logging.getLogger(__name__)


@celery_app.task(name="backend.tasks.scraper_tasks.run_all_scrapers", bind=True, max_retries=1)
def run_all_scrapers(self):
    """Runs all three scrapers sequentially and returns a summary."""
    results = {}
    db = SessionLocal()
    try:
        from scraper.internshala import scrape_internshala
        from scraper.linkedin import scrape_linkedin
        from scraper.wellfound import scrape_wellfound

        for name, fn in [
            ("internshala", scrape_internshala),
            ("linkedin", scrape_linkedin),
            ("wellfound", scrape_wellfound),
        ]:
            try:
                logger.info(f"Starting {name} scraper...")
                listings = fn()
                count = 0
                for data in listings:
                    upsert_listing(db, data)
                    count += 1
                results[name] = {"status": "ok", "upserted": count}
                logger.info(f"{name}: upserted {count} listings")
            except Exception as e:
                logger.error(f"{name} scraper failed: {e}", exc_info=True)
                results[name] = {"status": "error", "detail": str(e)}
    finally:
        db.close()

    return results


@celery_app.task(name="backend.tasks.scraper_tasks.run_single_scraper")
def run_single_scraper(platform: str):
    """Run just one scraper by name. Used by the manual trigger endpoint."""
    db = SessionLocal()
    try:
        if platform == "internshala":
            from scraper.internshala import scrape_internshala as fn
        elif platform == "linkedin":
            from scraper.linkedin import scrape_linkedin as fn
        elif platform == "wellfound":
            from scraper.wellfound import scrape_wellfound as fn
        else:
            return {"status": "error", "detail": f"Unknown platform: {platform}"}

        listings = fn()
        count = 0
        for data in listings:
            upsert_listing(db, data)
            count += 1
        return {"status": "ok", "platform": platform, "upserted": count}
    except Exception as e:
        logger.error(f"{platform} scraper failed: {e}", exc_info=True)
        return {"status": "error", "platform": platform, "detail": str(e)}
    finally:
        db.close()
