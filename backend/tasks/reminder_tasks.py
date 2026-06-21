"""
Celery task: send WhatsApp reminders for internships with deadlines <= 3 days away.
Runs daily at 9am IST via Celery beat.
"""
import logging
from datetime import datetime, timezone, timedelta

from backend.celery_app import celery_app
from backend.db.database import SessionLocal
from backend.db.models import Application, Listing, User
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload

logger = logging.getLogger(__name__)


def _send_whatsapp(to_number: str, message: str) -> bool:
    """Send a WhatsApp message via Twilio. Returns True on success."""
    try:
        from twilio.rest import Client
        from backend.core.config import settings

        if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN, settings.TWILIO_WHATSAPP_FROM]):
            logger.warning("Twilio credentials not configured — skipping message")
            return False

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        # Ensure number is in whatsapp: format
        to = to_number if to_number.startswith("whatsapp:") else f"whatsapp:{to_number}"

        client.messages.create(
            from_=settings.TWILIO_WHATSAPP_FROM,
            to=to,
            body=message,
        )
        logger.info(f"WhatsApp sent to {to_number}")
        return True
    except Exception as e:
        logger.error(f"Twilio error sending to {to_number}: {e}")
        return False


def _format_message(user_name: str, listings: list[tuple]) -> str:
    """
    Format the WhatsApp reminder message.
    listings: list of (listing, days_left) tuples
    """
    lines = [
        f"👋 Hi {user_name.split()[0]}!",
        "",
        "⏰ *InternHub Deadline Reminder*",
        "",
        "These internships are closing soon:",
        "",
    ]
    for listing, days_left in listings:
        if days_left == 0:
            deadline_str = "🔴 *Today!*"
        elif days_left == 1:
            deadline_str = "🔴 *Tomorrow!*"
        else:
            deadline_str = f"🟡 *{days_left} days left*"

        lines.append(f"• *{listing.title}* at {listing.company}")
        lines.append(f"  {deadline_str}")
        lines.append(f"  Apply: {listing.apply_url}")
        lines.append("")

    lines.append("Good luck! 🚀")
    lines.append("— InternHub")
    return "\n".join(lines)


@celery_app.task(name="backend.tasks.reminder_tasks.send_deadline_reminders")
def send_deadline_reminders():
    """
    Query all users who have saved/applied listings with deadlines within 3 days.
    Send one consolidated WhatsApp message per user.
    """
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=3)
    sent_count = 0
    skipped_count = 0

    try:
        # Find all applications (saved or applied) where deadline is within 3 days
        stmt = (
            select(Application)
            .options(
                joinedload(Application.user),
                joinedload(Application.listing),
            )
            .join(Application.listing)
            .join(Application.user)
            .where(
                and_(
                    Application.status.in_(["saved", "applied"]),
                    Listing.deadline >= now,
                    Listing.deadline <= cutoff,
                    Listing.is_active == True,
                    User.is_active == True,
                    User.whatsapp_number.isnot(None),
                )
            )
        )
        applications = db.scalars(stmt).all()

        if not applications:
            logger.info("No upcoming deadlines to remind about")
            return {"sent": 0, "skipped": 0}

        # Group by user
        user_listings: dict[str, list] = {}
        for app in applications:
            user_id = str(app.user_id)
            if user_id not in user_listings:
                user_listings[user_id] = {"user": app.user, "items": []}

            days_left = (app.listing.deadline - now).days
            user_listings[user_id]["items"].append((app.listing, days_left))

        logger.info(f"Sending reminders to {len(user_listings)} users")

        for user_id, data in user_listings.items():
            user = data["user"]
            items = data["items"]

            if not user.whatsapp_number:
                skipped_count += 1
                continue

            message = _format_message(user.full_name, items)
            success = _send_whatsapp(user.whatsapp_number, message)

            if success:
                sent_count += 1
            else:
                skipped_count += 1

        result = {"sent": sent_count, "skipped": skipped_count, "total_users": len(user_listings)}
        logger.info(f"Reminder task complete: {result}")
        return result

    except Exception as e:
        logger.error(f"Reminder task error: {e}", exc_info=True)
        return {"error": str(e)}
    finally:
        db.close()
