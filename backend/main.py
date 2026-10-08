from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.core.config import settings
from backend.db.database import check_db_connection
from backend.core.redis_client import check_redis_connection
from backend.auth.router import router as auth_router
from backend.api.routes.listings import router as listings_router
from backend.api.routes.ranked import router as ranked_router
from backend.api.routes.applications import router as applications_router
from backend.api.routes.skills import router as skills_router
from backend.api.routes.scraper import router as scraper_router
from backend.api.routes.reminders import router as reminders_router
from backend.api.routes.resume_profile import router as resume_profile_router
from backend.api.routes.resume_targets import router as resume_targets_router

app = FastAPI(title="InternHub API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ranked MUST come before listings (so /listings/ranked isn't caught by /listings/{id})
app.include_router(auth_router)
app.include_router(ranked_router)
app.include_router(listings_router)
app.include_router(applications_router)
app.include_router(skills_router)
app.include_router(scraper_router)
app.include_router(reminders_router)
app.include_router(resume_profile_router)
app.include_router(resume_targets_router)


@app.get("/health", tags=["Health"])
def health():
    db_ok = check_db_connection()
    redis_ok = check_redis_connection()
    return {
        "status": "ok" if (db_ok and redis_ok) else "degraded",
        "services": {
            "postgresql": "connected" if db_ok else "UNREACHABLE",
            "redis": "connected" if redis_ok else "UNREACHABLE",
        },
    }


@app.get("/")
def root():
    return {"message": "InternHub API", "docs": "/docs"}
