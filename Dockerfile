FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 sprain \
    && useradd --uid 10001 --gid sprain --create-home --shell /usr/sbin/nologin sprain \
    && chown sprain:sprain /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn[standard] asyncpg fastapi pydantic pydantic-settings jinja2 python-multipart
COPY --chown=sprain:sprain . .

WORKDIR /app/api

ENV HOME=/home/sprain
USER sprain

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
