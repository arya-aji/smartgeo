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
| `S3_ACCESS_KEY` | leave empty for now (filled in step 5) |
| `S3_SECRET_KEY` | leave empty for now (filled in step 5) |

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
  `storage` may be `false` until step 5 — that is expected.

---

## 5. Bootstrap Garage (one time, required)

The official Garage image is **distroless (no shell)**, so the Garage CLI must be
run *inside* the running container. Note that Coolify's interactive **Terminal**
opens a shell, which this image does not have — so use one of these instead:

**Option A — server SSH (most reliable):**

```bash
CID=$(docker ps -qf "name=garage" | head -n1)
docker exec -it "$CID" /garage -c /etc/garage.toml node id
```
Copy the node id (the part before `@`), then run each of these (same `docker
exec` form, replacing `<NODE_ID>`):

```sh
/garage -c /etc/garage.toml layout assign -z dc1 -c 100G <NODE_ID>
/garage -c /etc/garage.toml layout apply --version 1
/garage -c /etc/garage.toml bucket create wss
/garage -c /etc/garage.toml key create wss-app
/garage -c /etc/garage.toml bucket allow --read --write --owner wss --key wss-app
/garage -c /etc/garage.toml key info --show-secret wss-app
```

**Option B — Coolify UI:** if your Coolify version offers an "Execute Command"
that runs a single command without a shell, use it with the commands above
(prefixed by `/garage`). If it only opens a shell, use Option A.

Notes:

- Capacity must be at least `1K` (use `100G` above). `-c 1` fails with
  *"Capacity should be at least 1K"*, after which everything else fails with
  *"Layout not ready"*.
- `layout apply --version 1` only works the first time. If it errors, the layout
  is already applied — continue.

The last command prints:

```
Key ID:         GK........
Secret key:     ................................
```

Set both in Coolify:

| Variable | Value |
|---|---|
| `S3_ACCESS_KEY` | the *Key ID* |
| `S3_SECRET_KEY` | the *Secret key* |

Then **Redeploy** (a plain restart is enough — no rebuild needed) so the API and
workers pick up the credentials. Re-check:

```sh
curl https://api.maps.example.com/api/health
```
`"storage": true` means the whole stack is wired up.

> Alternative if you have server shell access: `scripts/bootstrap-garage.sh`
> performs the same sequence via `docker compose exec` (also works with the local
> `docker-compose.yml` for staging).

---

## 6. Verify end to end

1. Open `https://maps.example.com` and log in with the bootstrap admin.
2. Go to **Upload**, drag in a map photo.
3. Watch it move `QUEUED → DETECTING_PAPER → … → COMPLETED / NEEDS_REVIEW`.
4. Import the master list on **Targets** (one `idsubsls` per line) so valid IDs
   can auto-accept instead of always going to review.
5. Check **Dashboard** for totals and progress.

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
