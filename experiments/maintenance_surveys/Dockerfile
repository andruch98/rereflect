# Fictional local preview, using the existing FastAPI application and migrations.
# Optional multi-GB local ML dependencies are omitted just as in repository CI.
FROM python:3.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libpq-dev pkg-config libxml2-dev libxslt1-dev zlib1g-dev \
    libxmlsec1-dev libxmlsec1-openssl && rm -rf /var/lib/apt/lists/*
COPY services/backend-api/requirements.txt ./requirements.txt
RUN python -c "from pathlib import Path; p=Path('requirements.txt'); p.write_text(''.join(line for line in p.read_text().splitlines(True) if not line.startswith(('torch==','transformers==','sentence-transformers=='))))" \
    && pip install --no-cache-dir -r requirements.txt
COPY services/backend-api/ ./
COPY services/analysis-engine/src/analyzer ./analysis-engine/analyzer
COPY experiments/maintenance_surveys/fixtures ./survey-demo-fixtures
RUN useradd -m -u 1000 surveyuser && chown -R surveyuser:surveyuser /app
USER surveyuser
ENV PORT=8000
EXPOSE 8000
