


# InternHub

A full-stack internship aggregator that scrapes listings from **Internshala** and **LinkedIn**, ranks them against your skill profile using NLP, and sends deadline reminders, all in one unified dashboard.

---

## Demo
https://github.com/user-attachments/assets/7207181a-bf15-4df6-b61e-5c66dccba882



---

## Features

- **Aggregated listings** — scrapes Internshala (130+ listings) and LinkedIn (20+ listings) every 6 hours via Celery beat
- **NLP skill matching** — ranks listings by cosine similarity between your skill profile and listing content using `sentence-transformers` (all-MiniLM-L6-v2)
- **JWT authentication** — register/login with bcrypt passwords, access + refresh token rotation via Redis
- **Application tracker** — spreadsheet and Kanban view with 6 statuses (saved, applied, test, interview, rejected, accepted), inline note editing, and CSV/JSON export
- **WhatsApp reminders** — Twilio-powered daily reminders for deadlines within 3 days
- **Protected dashboard** — filterable, searchable, paginated listings with match score bars
- **Redis embedding cache** — listing embeddings are cached in Redis for 24 hours so NLP ranking drops from ~6s to <200ms after the first request; cache is auto-invalidated when scrapers update listing content

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, shadcn/ui |
| Backend | FastAPI (Python), Uvicorn |
| Database | PostgreSQL (SQLAlchemy ORM, Alembic migrations) |
| Cache / Queue | Redis (Docker), Celery |
| Scraping | Playwright (headless Chromium) |
| NLP | sentence-transformers (`all-MiniLM-L6-v2`), cosine similarity |
| Notifications | Twilio WhatsApp API |
| Auth | JWT (access + refresh tokens), bcrypt |

---

## Project Structure

```
internhub/
├── backend/
│   ├── api/routes/          # listings, applications, skills, scraper, reminders
│   ├── auth/                # JWT, bcrypt, Redis refresh token rotation
│   ├── core/                # config, redis client
│   ├── db/                  # SQLAlchemy models, database session
│   ├── tasks/               # Celery scraper + reminder tasks
│   └── main.py              # FastAPI app
├── templates/resume/        # Jinja2 LaTeX resume templates and manifests
├── alembic/                 # DB migrations
├── scraper/                 # Playwright scrapers (Internshala, LinkedIn, Wellfound)
├── nlp/                     # Sentence-transformer ranking
└── frontend/
    └── src/
        ├── app/             # Next.js pages (dashboard, tracker, profile, login, register)
        ├── components/      # Navbar, ListingCard
        ├── hooks/           # useAuth
        └── lib/             # axios client, auth helpers, types
```

---

Resume LaTeX templates are rendered by `backend.services.resume_render_service`.
The bundled Jake-style template is at `templates/resume/jake/`; its manifest
lists the supported independently toggleable sections. Rendered user values are
passed through the `latex_escape` filter.

Resume PDFs are compiled asynchronously by the `resume-compiler` Docker Compose
service. Configure `.env` from `.env.example`, run `docker compose up --build`,
then apply database migrations with
`docker compose exec api alembic upgrade head`. The compiler has no network
access, runs Tectonic in untrusted mode with shell escape disabled, and is
limited to one CPU, 512 MiB of memory, and 20 seconds per job. Poll
`GET /api/resume/jobs/{id}` and download generated files from the authenticated
`/api/resume/jobs/{id}/download/tex` and `/pdf` endpoints. For Overleaf import,
set `PUBLIC_API_URL` to the public HTTPS API origin; the app creates a
10-minute signed read-only URL so Overleaf can fetch the `.tex` source.

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL (running locally)
- Docker (for Redis only)

### 1. Clone and set up backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
playwright install chromium
```

### 2. Configure environment

```bash
cp .env.example backend/.env
# Fill in: DATABASE_URL, SECRET_KEY, TWILIO credentials
python -c "import secrets; print(secrets.token_hex(32))"  # generate SECRET_KEY
```

### 3. Start Redis

```bash
docker run -d -p 6379:6379 --name internhub-redis redis
```

### 4. Run migrations and seed data

```bash
# From internhub\ root, venv active
$env:PYTHONPATH = "."
alembic upgrade head
python backend/seed.py
```

### 5. Start all services

```bash
# Terminal 1 — FastAPI
$env:PYTHONPATH = "."
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — Celery worker
$env:PYTHONPATH = "."
celery -A backend.celery_app worker --pool=solo -l info

# Terminal 3 — Next.js
cd frontend
npm install
npm run dev
```

### 6. Open the app

- Frontend: http://localhost:3000
- API docs: http://localhost:8000/docs

---

## Scaling & Architecture Notes

### Celery horizontal scaling
The scraper and reminder tasks are fully decoupled from FastAPI via a Redis message broker. Adding workers is a single command — no code changes needed:

```bash
# Run on any machine that can reach the same Redis instance
$env:PYTHONPATH = "."
celery -A backend.celery_app worker --pool=solo -l info
```

Each worker picks up tasks from the shared queue automatically. In production on Linux, swap `--pool=solo` (Windows dev constraint) for `--concurrency=4` to run 4 parallel task executors per worker process.

Individual scrapers are registered as independent tasks (`run_single_scraper("internshala")`, `run_single_scraper("linkedin")`) so they can be distributed across workers — Internshala and LinkedIn could scrape in parallel on two workers instead of sequentially on one.

### Redis embedding cache
Listing embeddings (384-dim vectors from `all-MiniLM-L6-v2`) are cached in Redis under `listing_embed:{listing_id}` with a 24-hour TTL.

| Request | Latency |
|---|---|
| Cold (first request, 130+ listings) | ~6–8s |
| Warm (cache populated) | <200ms |

Cache is automatically invalidated in `crud.upsert_listing()` whenever a scraper updates a listing's content, so embeddings never go stale across scraper runs.


## API Overview

| Method | Endpoint | Description |
|---|---|---|
| POST | `/auth/register` | Create account |
| POST | `/auth/login` | Login, get tokens |
| POST | `/auth/refresh` | Rotate refresh token |
| GET | `/listings` | Paginated listings |
| GET | `/listings/ranked` | NLP-ranked listings |
| POST | `/applications` | Save/apply to listing |
| PATCH | `/applications/{id}` | Update status or notes |
| POST | `/user/skills` | Add skill to profile |
| POST | `/scraper/run` | Trigger all scrapers |
| POST | `/reminders/test` | Send test WhatsApp |

---
