FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install CPU-only torch first — the transitive pull from
# sentence-transformers would otherwise fetch the ~2 GB CUDA wheel.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 \
  && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser \
  && mkdir -p /app/storage \
  && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
