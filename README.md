# WSS Map Processing Platform

Platform for digitising and normalising WSS map photos: operators upload map
photographs, the system detects the map sheet, corrects perspective and
orientation, enhances readability, recognises the 16-digit `idsubsls` code,
validates it against the master list, and stores the cleaned map in Garage
(S3-compatible object storage).

Implements the requirements in [`WSS_Map_Processing_Platform_PRD.md`](./WSS_Map_Processing_Platform_PRD.md).

## Architecture at a glance

```
Next.js (web) ──presigned PUT──► Garage (S3)          ← API never proxies image bytes
     │                              ▲
     └──► FastAPI (api) ──enqueue──►│
              │        Redis        │
              │          │          │
              │          ▼          │
              │     cv-worker ──────┘   paper → perspective → orientation →
              │                         enhance → upscale → OCR → validate
              ▼
         PostgreSQL (state)          geo-worker (stage 2) → GeoTIFF/COG
```

| Service      | Tech                     | Role |
|--------------|--------------------------|------|
| `web`        | Next.js 14 App Router    | Operator/admin UI, direct-to-Garage uploads |
| `api`        | FastAPI + SQLAlchemy 2   | Auth, presigned URLs, job orchestration, review, dashboard |
| `cv-worker`  | Python + OpenCV + OCR    | Image-processing pipeline |
| `geo-worker` | Python + rasterio        | GeoJSON match → georeference → GeoTIFF (stage 2) |
| `postgres`   | PostgreSQL 16            | Metadata, source of truth for state |
| `redis`      | Redis 7                  | Work queue |
| `garage`     | Garage (S3-compatible)   | Object storage, source of truth for files |
| `garage-cors`| Caddy                    | CORS proxy for browser-facing S3 endpoint |

`packages/wss_common` is a shared Python package (models, enums, storage keys,
queue format, config) installed into every Python service so contracts cannot
drift. See [`docs/ARCHITECTURE.md`](./docs/ARCHITECTURE.md) and
[`docs/API.md`](./docs/API.md).

## Quick start (Docker)

```bash
cp .env.example .env
docker compose up -d --build postgres redis garage garage-cors
pwsh scripts/bootstrap-garage.ps1      # Windows
# sh scripts/bootstrap-garage.sh       # Linux / macOS
```

The bootstrap script applies the single-node Garage cluster layout, creates the
`wss` bucket and an S3 access key, writes the credentials to
`infra/garage/credentials/` (mounted into the app containers), and then starts
`api`, `cv-worker`, `geo-worker` and `web`.

Then open **http://localhost:3000** and log in with `admin` / `admin123`
(change this immediately in production — see `.env.example`).

API docs: **http://localhost:8000/docs**

### Why the two-step bootstrap?

The official Garage image is distroless (no shell), so the Garage CLI must run
inside the running container via `docker compose exec`. That is why cluster
init is a script rather than a compose service.

## Local development (without Docker)

Each Python service is a normal package; install the shared package first:

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e packages/wss_common

# API
cd api && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# CV worker
cd cv-worker && pip install -r requirements.txt
python -m cv_worker.main
```

The frontend:

```bash
cd web
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
npm run dev
```

You still need Postgres, Redis and Garage running (`docker compose up -d postgres redis garage garage-cors`).

## Tests

```bash
cd api        && python -m pytest -q     # offline (SQLite, services mocked)
cd cv-worker  && python -m pytest -q     # offline (synthetic map image)
cd geo-worker && python -m pytest -q     # offline
cd web        && npm run build           # type-checks the whole app
```

## Upload & processing flow

1. `POST /api/uploads/presign` → the API validates type/size, creates a
   `map_document` in `UPLOADING`, and returns a presigned PUT URL.
2. The browser `PUT`s the file **directly to Garage**.
3. `POST /api/uploads/complete` → the API verifies the object, creates a
   `processing_job` and pushes it onto Redis (`QUEUED`).
4. `cv-worker` picks it up and walks the pipeline, writing status transitions
   so the dashboard updates live.
5. Terminal states: `COMPLETED` (`maps/{idsubsls}.jpg`), `NEEDS_REVIEW`
   (`review/{id}.jpg`), `FAILED`.
6. Operators resolve the review queue; admins monitor progress on `/dashboard`.

## Object storage layout

```
wss/
├── original/{uuid}.{ext}        # immutable source archive
├── maps/{idsubsls}.jpg          # accepted cleaned map
├── review/{document_id}.jpg     # awaiting review
├── preview/{idsubsls}.webp      # small dashboard preview
└── georeferenced/{idsubsls}.tif # stage 2
```

Intermediate images are never persisted — they live in the worker's temp dir
and are deleted after each job.

## Configuration

All services read the same environment (see [`.env.example`](./.env.example)).
Key knobs:

| Variable | Purpose |
|---|---|
| `DATABASE_URL`, `REDIS_URL` | Infrastructure connections |
| `S3_ENDPOINT` / `S3_PUBLIC_ENDPOINT` | Internal vs browser-facing S3 endpoint |
| `S3_ACCESS_KEY_FILE` / `S3_SECRET_KEY_FILE` | File-based credentials (Docker secrets pattern) |
| `OCR_ENGINE` | `tesseract` (default), `paddleocr`, or `stub` |
| `OCR_AUTO_ACCEPT_CONFIDENCE`, `OCR_REVIEW_CONFIDENCE` | Auto-accept vs review band |
| `FUZZY_AUTO_ACCEPT_RATIO`, `FUZZY_REVIEW_RATIO` | Fuzzy-match thresholds |
| `PAPER_MIN_CONFIDENCE`, `QUALITY_MIN_SCORE` | Quality gates |
| `UPSCALE_MIN_SHORT_SIDE`, `UPSCALE_MAX_FACTOR` | Adaptive upscaling |
| `JOB_MAX_ATTEMPTS` | Retry budget |

Thresholds are intentionally conservative defaults and should be tuned after the
100–300 photo benchmark described in PRD section 33.

## Scaling workers

```bash
docker compose up -d --scale cv-worker=4
```

Workers can be moved to a dedicated host by pointing them at the same
`DATABASE_URL`, `REDIS_URL` and `S3_ENDPOINT` — no application changes needed.

## Deployment (Coolify)

Production deploys use the dedicated **`docker-compose.coolify.yml`** (no host
ports for databases, explicit `environment:` blocks, Traefik labels for TLS).

Full step-by-step guide: [`docs/DEPLOY_COOLIFY.md`](./docs/DEPLOY_COOLIFY.md).

Summary: create a Coolify **Docker Compose** resource pointing at
`/docker-compose.coolify.yml`, set domains for `web`, `api` and `garage-cors`,
fill in the environment variables, deploy, then run the one-time Garage
bootstrap (guide step 5) and set `S3_ACCESS_KEY` / `S3_SECRET_KEY`.

## Troubleshooting

- **Uploads fail with a CORS error** — make sure `garage-cors` is running and
  that `S3_PUBLIC_ENDPOINT` matches the URL the browser uses (default
  `http://localhost:3900`).
- **Uploads fail with `Invalid signature`** — do not add `header_up Host` to
  `infra/caddy/Caddyfile`; rewriting the Host breaks SigV4.
- **API can't reach storage** — confirm the bootstrap script ran and
  `infra/garage/credentials/` is populated.
- **Worker idle** — check `docker compose logs cv-worker`; jobs are consumed
  from `wss:cv:jobs` in Redis.
