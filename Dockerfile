# zvibe — all-in-one Docker image (app + PostgreSQL/pgvector)
FROM python:3.11-slim

# ── Install PostgreSQL 16 + pgvector ──
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl gnupg lsb-release ca-certificates \
    && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
    postgresql-16 \
    postgresql-16-pgvector \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Configure PostgreSQL ──
ENV PGDATA=/var/lib/postgresql/data
ENV PGUSER=zvibe PGPASSWORD=zvibe PGDATABASE=zvibe
RUN mkdir -p "$PGDATA" /run/postgresql && chown -R postgres:postgres "$PGDATA" /run/postgresql

# ── Install Python deps ──
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Copy source ──
COPY backend/ ./backend/
COPY frontend/ ./frontend/
COPY scripts/seed_demo.py ./scripts/
COPY docker-entrypoint.sh .

# ── Create .env ──
RUN echo 'DATABASE_URL=postgresql+asyncpg://zvibe:zvibe@localhost:5432/zvibe' > backend/.env \
    && echo 'JWT_SECRET=zvibe-demo-secret-change-in-production' >> backend/.env \
    && echo 'JWT_ACCESS_EXPIRE_MINUTES=30' >> backend/.env \
    && echo 'JWT_REFRESH_EXPIRE_DAYS=7' >> backend/.env \
    && echo 'LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1' >> backend/.env \
    && echo 'LLM_API_KEY=' >> backend/.env \
    && echo 'LLM_MODEL=google/gemma-4-31b-it' >> backend/.env \
    && echo 'MEDIA_UPLOAD_DIR=./uploads' >> backend/.env \
    && echo 'CORS_ORIGINS=*' >> backend/.env \
    && echo 'APP_ENV=production' >> backend/.env

RUN chmod +x docker-entrypoint.sh \
    && mkdir -p backend/uploads

EXPOSE 8080
ENTRYPOINT ["./docker-entrypoint.sh"]
