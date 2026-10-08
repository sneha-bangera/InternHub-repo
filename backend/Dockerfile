FROM python:3.12-slim

WORKDIR /app
ENV PYTHONPATH=/app

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY backend /app/backend
COPY nlp /app/nlp
COPY scraper /app/scraper
COPY templates /app/templates
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
RUN mkdir -p /var/lib/internhub/compile /var/lib/internhub/artifacts \
    && chmod 0777 /var/lib/internhub/compile /var/lib/internhub/artifacts

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
