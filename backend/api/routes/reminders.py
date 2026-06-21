"""
Manual reminder trigger endpoints for testing.
POST /reminders/test     — sends a real WhatsApp to the current user (if they have a number + upcoming deadlines)
POST /reminders/trigger  — manually fires the Celery task for all users
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.auth.dependencies import get_current_user
from backend.celery_app import celery_app
from backend.db.database import get_db
from backend.db.models import User

router = APIRouter(prefix="/reminders", tags=["Reminders"])


@router.post("/test")
def test_reminder_for_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sends a WhatsApp reminder to the current user immediately.
    Useful for testing Twilio setup without waiting for the scheduled task.
    Requires whatsapp_number to be set on your profile.
    """
    if not current_user.whatsapp_number:
        raise HTTPException(
            status_code=400,
            detail="No WhatsApp number on your profile. Update it at POST /auth/me or on the profile page.",
        )

    from datetime import datetime, timezone, timedelta
    from sqlalchemy import select, and_
    from sqlalchemy.orm import joinedload
    from backend.db.models import Application, Listing
    from backend.tasks.reminder_tasks import _send_whatsapp, _format_message

    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=3)

    apps = db.scalars(
        select(Application)
        .options(joinedload(Application.listing))
        .join(Application.listing)
        .where(
            and_(
                Application.user_id == current_user.id,
                Application.status.in_(["saved", "applied"]),
                Listing.deadline >= now,
                Listing.deadline <= cutoff,
                Listing.is_active == True,
            )
        )
    ).all()

    if not apps:
        return {
            "message": "No upcoming deadlines within 3 days for your saved/applied listings.",
            "tip": "Save some listings with deadlines within 3 days to test the reminder.",
        }

    items = [(app.listing, (app.listing.deadline - now).days) for app in apps]
    message = _format_message(current_user.full_name, items)
    success = _send_whatsapp(current_user.whatsapp_number, message)

    return {
        "sent": success,
        "to": current_user.whatsapp_number,
        "listings_count": len(items),
        "message_preview": message[:300] + "..." if len(message) > 300 else message,
    }


@router.post("/trigger")
def trigger_reminder_task(_: User = Depends(get_current_user)):
    """Manually enqueue the reminder Celery task for all users."""
    task = celery_app.send_task("backend.tasks.reminder_tasks.send_deadline_reminders")
    return {
        "message": "Reminder task queued for all users",
        "task_id": task.id,
        "check_status": f"/scraper/status/{task.id}",
    }
