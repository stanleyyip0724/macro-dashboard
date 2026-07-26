# US Macro Health Dashboard — API

FastAPI backend that aggregates ~48 FRED series into a business-cycle phase
classification, a composite systemic-risk index, and a threshold alert engine.

Interactive docs: `/docs`. Endpoints under `/api`.

## Deploy (Google Cloud Run)

    gcloud run deploy macro-dashboard-api --source . --region us-central1 \
      --allow-unauthenticated --cpu-boost --memory 1Gi --timeout 300

Required environment:

- `FRED_API_KEY` — FRED API key (store as a Secret Manager secret, not a plain env var)
- `CORS_ORIGINS` — comma-separated frontend origins, e.g. the Vercel URL
- `CACHE_DB_PATH` — `/tmp/fred_cache.db` (the container filesystem is read-only apart from /tmp)
