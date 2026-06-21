"""
Manual scraper trigger endpoint.
POST /scraper/run           — runs all 3 scrapers via Celery
POST /scraper/run/{platform} — runs one specific scraper
GET  /scraper/status/{task_id} — check task status
"""
from fastapi import APIRouter, Depends, HTTPException
from celery.result import AsyncResult

from backend.auth.dependencies import get_current_user
from backend.celery_app import celery_app
from backend.db.models import User

router = APIRouter(prefix="/scraper", tags=["Scraper"])


@router.post("/run")
def trigger_all_scrapers(_: User = Depends(get_current_user)):
    """Enqueue all 3 scrapers as a Celery task. Returns the task ID."""
    task = celery_app.send_task("backend.tasks.scraper_tasks.run_all_scrapers")
    return {
        "message": "All scrapers queued",
        "task_id": task.id,
        "check_status": f"/scraper/status/{task.id}",
    }


@router.post("/run/{platform}")
def trigger_single_scraper(
    platform: str,
    _: User = Depends(get_current_user),
):
    """Enqueue a single scraper. platform must be internshala | linkedin | wellfound."""
    if platform not in ("internshala", "linkedin", "wellfound"):
        raise HTTPException(status_code=400, detail="platform must be internshala, linkedin, or wellfound")
    task = celery_app.send_task(
        "backend.tasks.scraper_tasks.run_single_scraper",
        kwargs={"platform": platform},
    )
    return {
        "message": f"{platform} scraper queued",
        "task_id": task.id,
        "check_status": f"/scraper/status/{task.id}",
    }


@router.get("/status/{task_id}")
def task_status(task_id: str, _: User = Depends(get_current_user)):
    """Poll Celery task status by ID."""
    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task_id, "status": result.status}
    if result.ready():
        response["result"] = result.result if not isinstance(result.result, Exception) else str(result.result)
    return response
