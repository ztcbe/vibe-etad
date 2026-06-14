# zvibe — all-in-one Docker image (app + PostgreSQL/pgvector)
# FROM python:3.11-slim
FROM ubuntu:24.04
RUN rm /bin/sh && ln -s /bin/bash /bin/sh


# # ── Install PostgreSQL 16 + pgvector ──
RUN apt-get update 
RUN apt-get install -y python3 python3-venv
RUN apt-get install -y --no-install-recommends curl gnupg lsb-release ca-certificates 
RUN curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /usr/share/keyrings/postgresql-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/postgresql-archive-keyring.gpg] http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list
RUN apt-get update 
RUN export DEBIAN_FRONTEND=noninteractive && apt-get install -y --no-install-recommends \
    postgresql-16 \
    postgresql-16-pgvector
RUN apt-get clean && rm -rf /var/lib/apt/lists/*

# ── Configure PostgreSQL ──
ENV PGDATA=/var/lib/postgresql/data
ENV PGUSER=zvibe PGPASSWORD=zvibe PGDATABASE=zvibe
RUN mkdir -p "$PGDATA" /run/postgresql && chown -R postgres:postgres "$PGDATA" /run/postgresql 

# ── Install Python deps ──
WORKDIR /app

# ── Copy source ──
COPY backend/ ./backend/
COPY frontend/ ./frontend/
RUN mkdir -p scripts
COPY seed_demo.py ./scripts/
COPY docker-entrypoint.sh .

RUN cd backend && rm -rf .venv && \
    python3 -m venv .venv && \
    source .venv/bin/activate && \
    pip install "."


RUN chmod +x docker-entrypoint.sh \
    && mkdir -p backend/uploads

EXPOSE 8080
ENTRYPOINT ["./docker-entrypoint.sh"]
