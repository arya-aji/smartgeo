# Deploying the WSS Map Processing Platform on Coolify

This guide deploys the whole stack (Next.js, FastAPI, CV worker, geo worker,
PostgreSQL, Redis, Garage object storage, Caddy CORS proxy) as **one Coolify
Docker Compose resource**, with automatic HTTPS through Coolify's Traefik.

Use the dedicated production compose file: **`docker-compose.coolify.yml`**.
(It differs from the local `docker-compose.yml`: no host port publishing for
databases, explicit `environment:` blocks, and Traefik labels.)

---

## 0. What you need before starting

- A working Coolify instance (server with Docker + Traefik).
- A Git repository containing this project (GitHub / GitLab / Gitea / Bitbucket).
- **Three DNS records** pointing at your Coolify server, e.g.:

  | Purpose | Example hostname |
  |---|---|
  | Frontend (Next.js) | `maps.example.com` |
  | API (FastAPI) | `api.maps.example.com` |
  | Garage S3 endpoint (browser uploads) | `garage.maps.example.com` |

  All three are required. The Garage one is **not optional**: browsers upload
  photos directly to it, so it must be publicly reachable over HTTPS.
- **Server memory**: If your server has ≤ 4 GB RAM, ensure swap is enabled
  (e.g., `fallocate -l 4G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`).
  Without swap, Docker builds can trigger the Linux kernel OOM killer (exit code 255).

> Do **not** commit `.env` or `infra/garage/credentials/` — both are git-ignored.

---

## 1. Create the Coolify resource

1. Push the repository to your Git provider.
2. In Coolify: **+ New Resource → Docker Compose** (from your repository).
3. Select the repository and branch.
4. Set **Docker Compose Location** to:

   ```
   /docker-compose.coolify.yml
   ```

5. Do **not** let Coolify build a single service — the compose file defines all
   build contexts (they use the repository root so the shared
   `packages/wss_common` package is copied into each image).

---

## 2. Set the domains (Coolify creates the Traefik routes)

Coolify discovers every service in the compose file. Open each of these and
assign its domain under **Component Settings → Domains**:

| Service | Domain to enter | Container port |
|---|---|---|
| `web` | `https://maps.example.com` | `3000` |
| `api` | `https://api.maps.example.com` | `8000` |
| `garage-cors` | `https://garage.maps.example.com` | `3900` |

In the normal (managed) deployment mode **Coolify injects the Traefik labels
itself** and generates `SERVICE_FQDN_<SERVICE>` / `SERVICE_URL_<SERVICE>`
variables (hyphens become underscores, so `garage-cors` →
`SERVICE_FQDN_GARAGE_CORS`). The compose file therefore deliberately contains
**no** manual Traefik labels — adding your own would create a second router on
the same Host and can conflict.

Only if you deploy in **Raw Compose Deployment** mode do you need to add labels
yourself, for example on the `web` service:

```yaml
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.wss-web.rule=Host(`${SERVICE_FQDN_WEB}`)"
      - "traefik.http.routers.wss-web.entryPoints=https"
      - "traefik.http.routers.wss-web.tls.certresolver=letsencrypt"
      - "traefik.http.services.wss-web.loadbalancer.server.port=3000"
```
Repeat for `api` (port `8000`) and `garage-cors` (port `3900`).

---

## 3. Set environment variables

Add these in Coolify's environment editor for the resource. Values marked
**required** have no safe default.

### Core

| Variable | Value |
|---|---|
| `POSTGRES_USER` | `wss` |
| `POSTGRES_PASSWORD` | **required** — strong random |
| `POSTGRES_DB` | `wss` |
| `JWT_SECRET` | **required** — `openssl rand -hex 32` |
| `BOOTSTRAP_ADMIN_USERNAME` | `admin` |
| `BOOTSTRAP_ADMIN_PASSWORD` | **required** — strong |
| `BOOTSTRAP_ADMIN_NAME` | `Administrator` |
| `APP_ENV` | `production` |
| `LOG_LEVEL` | `INFO` |
| `COMPOSE_PARALLEL_LIMIT` | `1` (prevents build OOM by building images sequentially) |

> **Mark both `NEXT_PUBLIC_API_BASE_URL` and `COMPOSE_PARALLEL_LIMIT` as "Build Variables" in Coolify.**
> Coolify gives every variable independent *Build* and *Runtime* toggles. Setting
> `COMPOSE_PARALLEL_LIMIT=1` ensures Docker builds one service at a time, keeping
> memory usage low.

### URLs (must match the domains from step 2)

| Variable | Value |
|---|---|
| `CORS_ORIGINS` | `https://maps.example.com` |
| `NEXT_PUBLIC_API_BASE_URL` | `https://api.maps.example.com` |
| `S3_PUBLIC_ENDPOINT` | `https://garage.maps.example.com` |

> **`NEXT_PUBLIC_API_BASE_URL` must be marked as a "Build Variable" in Coolify.**
> Coolify gives every variable independent *Build* and *Runtime* toggles, and
> build args are only injected during the image build when the Build toggle is
> enabled. Set it correctly *before* the first deploy; changing it later requires
> a rebuild (Redeploy **with rebuild**, not just restart).

### Storage

| Variable | Value |
|---|---|
| `S3_REGION` | `garage` |
| `S3_BUCKET` | `wss` |
| `S3_ACCESS_KEY` | **required** — `GK` + `openssl rand -hex 16` |
| `S3_SECRET_KEY` | **required** — `openssl rand -hex 32` |

### Processing thresholds (defaults are fine; tune after benchmark)

```
ID_PATTERN=^\d{16}$
OCR_ENGINE=tesseract
OCR_AUTO_ACCEPT_CONFIDENCE=0.90
OCR_REVIEW_CONFIDENCE=0.55
FUZZY_AUTO_ACCEPT_RATIO=0.93
FUZZY_REVIEW_RATIO=0.72
PAPER_MIN_CONFIDENCE=0.60
QUALITY_MIN_SCORE=0.50
UPSCALE_MIN_SHORT_SIDE=1600
UPSCALE_MAX_FACTOR=2.0
JOB_MAX_ATTEMPTS=3
WORKER_CONCURRENCY=1
CV_WORKER_REPLICAS=2
```

---

## 4. Deploy

Trigger **Deploy**. Coolify builds four images (api, cv-worker, geo-worker, web)
and starts all services. The first build takes several minutes (OpenCV,
tesseract, rasterio, Next.js).

Check:

- `web` → `https://maps.example.com` should return the login page.
- `api` → `https://api.maps.example.com/api/health` should return
  `{"status":"ok","db":true,"redis":true,"storage":...}`.
  `storage` should be `true`; it stays `false` only when `S3_ACCESS_KEY` /
  `S3_SECRET_KEY` were not set (see step 5).

---

## 5. Garage credentials (automatic — no shell access needed)

Garage bootstraps itself from the environment, so there is **no manual `garage`
CLI step and no server shell access required**. `docker-compose.coolify.yml`
starts Garage with `server --single-node --default-access-key --default-bucket`,
which on first start:

1. configures the single-node cluster layout,
2. creates the S3 access key from `S3_ACCESS_KEY` / `S3_SECRET_KEY`,
3. creates the bucket `S3_BUCKET` (default `wss`) and grants that key full access.

All you have to do is set the credentials in Coolify (**Environment Variables**)
and redeploy. The key Garage creates always matches what the API signs with,
because both read the same variables:

| Variable | Value |
|---|---|
| `S3_ACCESS_KEY` | **required** — access key id, e.g. `GK` + 16 random hex chars |
| `S3_SECRET_KEY` | **required** — 32 random bytes, hex encoded |
| `S3_BUCKET` | `wss` |
| `S3_PUBLIC_ENDPOINT` | `https://garage.maps.example.com` |

Generate the values locally:

```sh
echo "GK$(openssl rand -hex 16)"   # S3_ACCESS_KEY
openssl rand -hex 32               # S3_SECRET_KEY
```

The compose fails fast (with `set S3_ACCESS_KEY`) if they are missing. After the
deploy, re-check:

```sh
curl https://api.maps.example.com/api/health
```
`"storage": true` means the whole stack is wired up.

> Requires Garage **>= v2.3.0** (the compose pins `dxflrs/garage:v2.3.0`). The
> flags are safe to leave in place on restarts — Garage only refuses
> `--single-node` if the cluster already contains *other* nodes. If you
> previously bootstrapped Garage by hand, set `S3_ACCESS_KEY` / `S3_SECRET_KEY`
> to the credentials printed back then, or delete the `garage_meta` /
> `garage_data` volumes to start fresh.
>
> With server shell access the equivalent can still be run by hand:
> `scripts/bootstrap-garage.sh` (also used by the local `docker-compose.yml`).

---

## 6. Verify end to end

1. Open `https://maps.example.com` and log in with the bootstrap admin.
2. The master region list (5,511 `idsubsls`) is seeded automatically into
   `wss_targets` on the first API start from `api/app/data/idsubsls.txt`
   (disable with `SEED_MASTER_TARGETS=false`). Confirm it on the **Map** page.
3. Go to **Upload**, drag in a map photo.
4. Watch it move `QUEUED → DETECTING_PAPER → … → COMPLETED / NEEDS_REVIEW`.
5. On **Map**, locate the region: once processing completes, that `idsubsls` row
   shows its state with **Preview** and **Download** buttons (the worker links
   the map to the region by `idsubsls`).
6. Check **Dashboard** for totals and progress.

> The UI is **Map** (all regions + result), **Logs** (every document, newest
> first), **Review** (exceptions), **Tasks** (claim a batch of regions) and
> **Upload**. Dashboard, Operators and Targets are admin-only.
>
> After upgrading an existing deployment, **log out and back in once**: the
> navigation and the admin-only gate now read a `role` cookie that sessions
> created before this change do not have (an admin without it lands on Map).

If the browser upload fails, see *Troubleshooting*.

---

## 7. Scaling workers

The CV worker is the CPU-heavy part and is stateless (it pulls jobs from Redis),
so scale it freely:

- Set `CV_WORKER_REPLICAS` (compose `deploy.replicas`) and redeploy, **or**
- On the server: `docker compose -f docker-compose.coolify.yml up -d --scale cv-worker=4`.

Workers can also run on a separate server: point a second compose stack at the
same `DATABASE_URL`, `REDIS_URL` and `S3_ENDPOINT` and run only the worker
services. No application changes are needed.

---

## 8. Persistent data & backups

These Docker volumes hold all state and survive redeploys:

- `postgres_data` — all metadata
- `redis_data` — queue
- `garage_meta`, `garage_data` — the map files

> Coolify prefixes named volumes (e.g. `postgres_data` becomes something like
> `<resource-id>_postgres_data`) to avoid collisions between resources. They are
> still persistent across redeploys — just look them up under the resource's
> *Deployable Compose* / Docker volumes view when backing up.

Back up:

- **PostgreSQL**: scheduled `pg_dump`.
- **Garage**: back up the `garage_meta` and `garage_data` volumes (or enable
  Garage replication if you later run a multi-node cluster).

Originals under `original/` are immutable, so a bucket-level copy is a valid
archive. Do **not** apply a retention policy to `original/` until audit/archival
requirements are confirmed.

---

## 9. Troubleshooting (issues actually hit while building this stack)

**Browser upload fails with a CORS error**
`garage-cors` must be running and reachable, and `S3_PUBLIC_ENDPOINT` must be
exactly the URL the browser uses (`https://garage.maps.example.com`). Garage's
own CORS only decorates `OPTIONS` with a `403`, which fails the browser
preflight — that is why Caddy sits in front.

**Uploads fail with `Invalid signature`**
Do not add `header_up Host` to `infra/caddy/Caddyfile`. Rewriting the Host header
breaks the SigV4 signature. Caddy preserves the Host by default — leave it alone.

**API health shows `"storage": false`**
The Garage bucket/credentials are missing. Re-run step 5 and set
`S3_ACCESS_KEY` / `S3_SECRET_KEY`.

**Garage container restarts / layout errors**
Use capacity `100G` (not `1`). Also change `rpc_secret` and `admin_token` in
`infra/garage/garage.toml` from the dev defaults before going to production.

**Frontend calls the wrong API URL**
`NEXT_PUBLIC_API_BASE_URL` is baked in at build time. Fix the env var and
redeploy **with rebuild**.

**Locked out of the admin account (401 on login)**
The bootstrap admin is created only while the `users` table is empty
(`api/app/bootstrap.py`), so changing `BOOTSTRAP_ADMIN_PASSWORD` after the first
start does **not** update an existing admin. Recover without database access:
set `BOOTSTRAP_ADMIN_PASSWORD` to the password you want and
`BOOTSTRAP_ADMIN_FORCE_RESET=true` in Coolify, redeploy the `api` service, log
in, then set `BOOTSTRAP_ADMIN_FORCE_RESET=false` again.

**Workers idle, jobs stuck in `QUEUED`**
Check the `cv-worker` logs. The worker consumes from the Redis list
`wss:cv:jobs`; if it crashed on startup it restarts, and a `nack`ed job returns
to the queue.

**Traefik 404 on a domain**
The service must expose the port named in
`traefik.http.services.<name>.loadbalancer.server.port` (3000 / 8000 / 3900) and
be on Coolify's proxy network. Verify the `SERVICE_FQDN_*` values were actually
set for those services.

---

## 10. Production hardening checklist

- [ ] Change `rpc_secret` and `admin_token` in `infra/garage/garage.toml`.
- [ ] Strong `POSTGRES_PASSWORD`, `JWT_SECRET`, `BOOTSTRAP_ADMIN_PASSWORD`.
- [ ] Change the bootstrap admin password after first login (or create a real
      admin and disable the bootstrap one).
- [ ] PostgreSQL, Redis and the Garage admin API stay **unpublished** — the
      Coolify compose already uses `expose`, not `ports`.
- [ ] Scheduled backups for PostgreSQL and the Garage volumes.
- [ ] Run the 100–300 photo benchmark (PRD §33) and tune
      `OCR_AUTO_ACCEPT_CONFIDENCE` / `OCR_REVIEW_CONFIDENCE` / `FUZZY_*` before
      processing the full 5,511-map target.
