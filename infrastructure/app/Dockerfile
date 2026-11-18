FROM python:3.13-slim AS base

WORKDIR /app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt /tmp/requirements.txt

RUN python -m pip install --no-cache-dir \
    -r /tmp/requirements.txt

COPY api /app/api
COPY incident_service /app/incident_service
COPY lineage /app/lineage
COPY metadata /app/metadata
COPY infrastructure/postgres/init /app/infrastructure/postgres/init
COPY dashboard /app/dashboard
COPY failure_injection /app/failure_injection
COPY spark /app/spark

FROM base AS api

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app \
       --home-dir /nonexistent \
       --shell /usr/sbin/nologin app \
    && chown -R app:app /app \
    && chmod -R a+rX /app

USER app

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]

FROM base AS worker

RUN apt-get update \
    && apt-get install -y --no-install-recommends docker-cli \
    && rm -rf /var/lib/apt/lists/*

CMD ["python", "-m", "incident_service.worker.main"]

FROM base AS cloud-worker

RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app \
       --home-dir /nonexistent \
       --shell /usr/sbin/nologin app \
    && chown -R app:app /app \
    && chmod -R a+rX /app

USER app

CMD ["python", "-m", "incident_service.worker.main"]
