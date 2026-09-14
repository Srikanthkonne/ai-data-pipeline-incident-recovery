FROM python:3.13-slim

WORKDIR /workspace

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt /tmp/requirements.txt

RUN pip install --no-cache-dir \
    -r /tmp/requirements.txt \
    python-dotenv \
    dbt-core==1.12.4 \
    dbt-duckdb==1.11.0

CMD ["sleep", "infinity"]
