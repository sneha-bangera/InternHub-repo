from celery import Celery
from celery.schedules import crontab
from backend.core.config import settings

celery_app = Celery(
    "internhub",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "backend.tasks.scraper_tasks", 
        "backend.tasks.reminder_tasks",
        "backend.tasks.resume_compile_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Kolkata",
    enable_utc=True,
    worker_pool="solo",          # required on Windows
    beat_schedule={
        "scrape-all-every-6-hours": {
            "task": "backend.tasks.scraper_tasks.run_all_scrapers",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "send-deadline-reminders-daily-9am": {
            "task": "backend.tasks.reminder_tasks.send_deadline_reminders",
            "schedule": crontab(minute=0, hour=9),   # 9:00 AM IST daily
        },
    },
)
