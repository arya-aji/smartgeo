# Architecture — WSS Map Processing Platform

This document describes the concrete implementation of the platform described in
`WSS_Map_Processing_Platform_PRD.md`. It is the shared contract between the API,
the workers and the frontend.

## 1. Repository layout

```
smartgeo/
├── api/                  # FastAPI service (control plane)
├── cv-worker/            # Image-processing worker (paper/perspective/OCR)
├── geo-worker/           # Geospatial worker (stage 2)
├── web/                  # Next.js frontend
├── packages/wss_common/  # Shared contracts: models, enums, storage, queue, config
├── infra/garage/         # Garage configuration
├── docs/                 # Architecture, API contract, deployment
└── docker-compose.yml    # Local / single-node stack
```

`packages/wss_common` is installed into every Python service so the database
schema, object-key layout, queue message format and enum values cannot drift.

## 2. Services

| Service      | Tech                     | Responsibility |
|--------------|--------------------------|----------------|
| `web`        | Next.js (App Router)     | Operator/admin UI, direct-to-Garage uploads |
| `api`        | FastAPI + SQLAlchemy 2   | Auth, presigned URLs, job orchestration, review, dashboard |
| `cv-worker`  | Python + OpenCV + OCR    | Paper detect → perspective → orientation → enhance → upscale → OCR → validate |
| `geo-worker` | Python + GDAL/Rasterio   | GeoJSON match → georeference → GeoTIFF/COG (stage 2) |
| `postgres`   | PostgreSQL 16            | Metadata (source of truth for state) |
| `redis`      | Redis 7                  | Work queue + coordination |
| `garage`     | Garage (S3-compatible)   | Object storage (source of truth for files) |

## 3. Core principles (PRD section 6)

1. **API never receives image bytes.** The browser asks `POST /uploads/presign`
   for a presigned PUT URL and uploads directly to Garage. The API stays light
   under 20 concurrent operators.
2. **Processing is asynchronous.** `POST /uploads/complete` creates the
   `map_document` + `processing_job` and pushes a message onto Redis.
3. **Workers are separate processes** and can be scaled horizontally
   (`docker compose up --scale cv-worker=4`) with no frontend changes.
4. **Storage discipline.** Only `original/`, `maps/`, `review/` and `preview/`
   are persisted. All intermediates live in the worker's local temp dir and are
   deleted after each job.

## 4. Upload + processing flow

```
Browser ──POST /uploads/presign──► API ──presigned PUT──► Browser
Browser ──PUT bytes────────────────────────────────────► Garage (original/{uuid}.jpg)
Browser ──POST /uploads/complete─► API ──enqueue────────► Redis (wss:cv:jobs)
                                                   │
                                          cv-worker BRPOPLPUSH
                                                   │
   DETECTING_PAPER → CORRECTING_PERSPECTIVE → DETECTING_ORIENTATION
   → ENHANCING → UPSCALING → DETECTING_TEXT → RECOGNIZING_ID
   → VALIDATING_ID → FINALIZING
                                                   │
                        ┌──────────────────────────┼───────────────────────┐
                     COMPLETED                 NEEDS_REVIEW              FAILED
                   maps/{id}.jpg            review/{doc}.jpg        error_message set
                   preview/{id}.webp
```

Every status transition is written to `map_documents.processing_status` so the
dashboard can render live progress.

## 5. Job state machine

`ProcessingStatus` (PRD section 21):

```
UPLOADING → UPLOADED → QUEUED → DETECTING_PAPER → CORRECTING_PERSPECTIVE
→ DETECTING_ORIENTATION → ENHANCING → UPSCALING → DETECTING_TEXT
→ RECOGNIZING_ID → VALIDATING_ID → FINALIZING → COMPLETED
                                                 ├─► NEEDS_REVIEW
                                                 └─► FAILED
```

`JobStatus` (per `processing_jobs` row): `PENDING → RUNNING → SUCCEEDED`
with `FAILED` / `RETRYING` on error. Retries are bounded by
`JOB_MAX_ATTEMPTS` (default 3).

## 6. Database schema

Defined in `packages/wss_common/wss_common/models.py`:

- `users` — id, name, username, password_hash, role (`OPERATOR`|`ADMIN`), is_active, created_at
- `wss_targets` — master 5,511 IDs: id, idsubsls, status, map_document_id, assigned_to, assigned_at
- `map_documents` — the processing record (keys, dimensions, orientation, confidences, ocr_raw, quality_score, upscale info, status, attempts)
- `processing_jobs` — job_type, status, attempt, error_message, timestamps
- `geojson_datasets` — name, version, source, object_key, status
- `geojson_features` — dataset_id, idsubsls, geometry (JSONB), properties (JSONB)

## 7. Object storage layout (PRD sections 17 & 18)

```
wss/
├── original/{uuid}.{ext}        # immutable source archive
├── maps/{idsubsls}.jpg          # accepted final cleaned map
├── review/{document_id}.jpg     # output awaiting operator review
├── preview/{idsubsls}.webp      # small dashboard preview
└── georeferenced/{idsubsls}.tif # stage 2
```

Helpers live in `wss_common.storage`; nothing constructs keys by hand.

## 8. Queue contract (Redis)

Lists, reliable via `BRPOPLPUSH`:

| Queue | Pending | Processing |
|-------|---------|------------|
| CV    | `wss:cv:jobs`  | `wss:cv:processing`  |
| Geo   | `wss:geo:jobs` | `wss:geo:processing` |

Message payload:

```json
{ "job_id": "<uuid>", "map_document_id": "<uuid>", "job_type": "CV_PROCESS", "attempt": 1 }
```

On worker startup, `requeue_stale()` returns anything stranded in the
processing list back to pending so crashed jobs are retried.

## 9. Decision logic (PRD sections 15 & 16)

For each document the worker computes `paper_confidence`, `ocr_confidence` and a
`quality_score`, then:

| Condition | Outcome |
|-----------|---------|
| ID matches master (exact) AND confidence ≥ `OCR_AUTO_ACCEPT_CONFIDENCE` | `COMPLETED` |
| Fuzzy match ratio ≥ `FUZZY_AUTO_ACCEPT_RATIO` AND confidence ≥ auto threshold | `COMPLETED` (auto-corrected ID) |
| Confidence in review band, fuzzy match in review band, or ID not in master | `NEEDS_REVIEW` (reason recorded) |
| Paper detection below `PAPER_MIN_CONFIDENCE`, corrupt file, or exception | `FAILED` (or `NEEDS_REVIEW` if recoverable) |

All thresholds are environment-driven and are expected to be tuned after the
100–300 photo benchmark (PRD section 33).

## 10. Security (PRD section 34)

- JWT bearer auth; operators see only their own jobs, admins see all.
- Presigned URLs expire (`S3_PRESIGN_EXPIRE`).
- Garage is never exposed publicly; credentials come from env/secrets.
- Upload content-type and size validated before presigning.
- Originals are never overwritten.

## 11. Deployment (PRD section 30)

Single `docker-compose.yml` for local and single-node Coolify deploys.
Workers can be scaled or moved to a dedicated host by pointing them at the same
`DATABASE_URL`, `REDIS_URL` and `S3_ENDPOINT` — no application changes required.
See `docs/DEPLOY_COOLIFY.md`.

## 12. Observability (PRD section 32)

`GET /dashboard` exposes totals, progress %, per-operator counts and queue
lengths. Per-document metrics (`paper_confidence`, `ocr_confidence`,
`quality_score`, `processing_attempts`, `error_message`) are persisted for
bottleneck analysis after the first 100–300 photos.
