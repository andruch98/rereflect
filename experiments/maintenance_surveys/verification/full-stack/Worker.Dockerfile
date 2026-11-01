# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm
WORKDIR /app
COPY services/worker-service/requirements.txt requirements.txt
RUN python -c "from pathlib import Path; p=Path('requirements.txt'); p.write_text(''.join(l for l in p.read_text().splitlines(True) if not l.startswith(('torch==','transformers==','sentence-transformers=='))))"
RUN pip install --no-cache-dir -r requirements.txt
COPY services/worker-service/src ./src
COPY services/analysis-engine/src/analyzer ./analyzer
ENV PYTHONPATH=/app
CMD ["celery", "-A", "src.celery_app", "worker", "--pool=solo", "--concurrency=1", "--loglevel=info"]
