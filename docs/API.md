# API Contract — WSS Map Processing Platform

Base URL: `${NEXT_PUBLIC_API_BASE_URL}` (default `http://localhost:8000`).
All endpoints are prefixed with `/api` **except** the ones listed as root below —
to keep it simple, every route in this document is mounted under `/api`.
Interactive docs are available at `/docs`.

Authentication: `Authorization: Bearer <access_token>` on every route except
`POST /api/auth/login`.

Errors use FastAPI's default shape:

```json
{ "detail": "Human readable message" }
```

---

## Common objects

```jsonc
// User
{ "id": "uuid", "name": "Budi", "username": "budi",
  "role": "OPERATOR", "is_active": true, "created_at": "ISO8601" }

// MapDocumentSummary
{ "id": "uuid", "idsubsls": "3173030005003200", "processing_status": "COMPLETED",
  "quality_score": 0.87, "ocr_confidence": 0.95, "paper_confidence": 0.91,
  "orientation": 0, "upscaled": false, "upscale_factor": null,
  "created_at": "ISO8601", "processed_at": "ISO8601",
  "uploaded_by": "uuid", "uploaded_by_name": "Budi",
  "preview_url": "https://garage/...signed...", "review_reason": null }

// MapDocumentDetail (adds)
{ "ocr_raw": "3173030005003200", "ocr_candidates": [...], "corners": {...},
  "source_width": 3024, "source_height": 4032, "final_width": 2480, "final_height": 3508,
  "processing_attempts": 1, "error_message": null,
  "original_filename": "IMG_1023.jpg", "content_type": "image/jpeg", "file_size": 4212333,
  "original_url": "...", "final_url": "...", "review_url": "..." }
```

Pagination envelope:

```json
{ "items": [], "total": 0, "page": 1, "page_size": 20, "pages": 1 }
```

---

## Auth

### POST `/api/auth/login`
Request: `{ "username": "admin", "password": "admin123" }`
Response: `{ "access_token": "...", "token_type": "bearer", "user": User }`

### GET `/api/auth/me`
Response: `User`

---

## Uploads (direct-to-Garage)

### POST `/api/uploads/presign`
Creates a `map_document` in `UPLOADING` and returns a presigned PUT URL.

Request:
```json
{ "filename": "IMG_1023.jpg", "content_type": "image/jpeg", "size": 4212333,
  "target_id": "uuid|null" }
```
Response:
```json
{ "map_document_id": "uuid", "object_key": "original/<uuid>.jpg",
  "upload_url": "http://garage:3900/wss/original/...?X-Amz-Signature=...",
  "method": "PUT", "headers": { "Content-Type": "image/jpeg" }, "expires_in": 900 }
```
Validation: `content_type` must be in `UPLOAD_ALLOWED_TYPES`; `size` ≤
`UPLOAD_MAX_BYTES`. Returns `400` otherwise.

### POST `/api/uploads/complete`
Confirms the object reached Garage, creates the job and enqueues it.

Request: `{ "map_document_id": "uuid", "width": 3024, "height": 4032, "file_size": 4212333 }`
(`width`, `height` and `file_size` are optional — the CV worker measures the real
dimensions from the image.)
Response: `{ "map_document": MapDocumentDetail, "job": Job }`
The document transitions `UPLOADING → UPLOADED → QUEUED`.

---

## Jobs

### POST `/api/jobs`
Request: `{ "map_document_id": "uuid" }` → Response: `Job`
Re-enqueues an existing/uploaded document.

### GET `/api/jobs/{id}` → `Job`
```json
{ "id": "uuid", "map_document_id": "uuid", "job_type": "CV_PROCESS",
  "status": "RUNNING", "attempt": 1, "error_message": null,
  "started_at": "...", "completed_at": null, "created_at": "..." }
```

### POST `/api/jobs/{id}/retry` → `Job`

---

## Maps

### GET `/api/maps`
Query params: `status`, `q` (matches idsubsls), `page` (default 1),
`page_size` (default 20, max 100), `mine` (`true` → only current user's docs).
Response: pagination envelope of `MapDocumentSummary`.

### GET `/api/maps/{id}` → `MapDocumentDetail`
Includes fresh presigned URLs (`original_url`, `final_url`, `review_url`).

---

## Review queue

### GET `/api/review`
Documents in `NEEDS_REVIEW`. Response: pagination envelope of
`MapDocumentSummary` (with `review_reason`, `ocr_raw`, `ocr_candidates`,
`preview_url` populated).

### POST `/api/review/{id}/accept`
Body (optional): `{ "idsubsls": "3173030005003200" }`.
Promotes the review output to `maps/{idsubsls}.jpg`, sets `COMPLETED`,
updates the linked `wss_target`. Response: `MapDocumentDetail`.

### POST `/api/review/{id}/manual-id`
Body: `{ "idsubsls": "3173030005003200" }` (required, must match `ID_PATTERN`).
Operator supplies the correct ID; same promotion as accept. Response:
`MapDocumentDetail`.

---

## Dashboard

### GET `/api/dashboard`
```json
{
  "global": { "total": 5511, "completed": 1200, "processing": 4,
              "queued": 30, "review": 12, "failed": 3 },
  "progress_percent": 21.8,
  "queue": { "cv_pending": 30, "cv_processing": 1, "geo_pending": 0 },
  "operators": [
    { "id": "uuid", "name": "Budi", "username": "budi", "completed": 275,
      "assigned": 20, "review": 1, "failed": 0 }
  ]
}
```

---

## Operators (ADMIN only)

### GET `/api/operators` → `[User & { completed, assigned }]`
### POST `/api/operators`
Request: `{ "name": "Budi", "username": "budi", "password": "secret", "role": "OPERATOR" }`
→ `User`
### PATCH `/api/operators/{id}`
Request: any of `{ "name", "password", "is_active", "role" }` → `User`

---

## Targets (master IDSUBSLS list)

### GET `/api/targets`
Query: `status`, `q`, `page`, `page_size` → pagination envelope of
`{ id, idsubsls, status, map_document_id, assigned_to, assigned_at }`

### POST `/api/targets/import`
Request: `{ "idsubsls": ["3173030005003200", "3173030005003201"] }`
Response: `{ "created": 2, "skipped": 0, "invalid": 0 }`

### DELETE `/api/targets/{id}` → `{ "deleted": true }`

---

## Batch assignment

### POST `/api/batches/claim`
Request: `{ "size": 20 }`
Atomically locks the next `size` `PENDING` targets for the current operator
(`SELECT ... FOR UPDATE SKIP LOCKED`) and sets their status to `ASSIGNED`.
Response: `{ "targets": [WssTarget], "remaining": 5311 }`

---

## GeoJSON datasets (stage 2)

### POST `/api/geojson/datasets`
Multipart: `file` (`.geojson`/`.json`), `name`, `version`.
Parses features, stores the object, populates `geojson_features`.
Response: `{ id, name, version, source, object_key, status, feature_count, created_at }`

### GET `/api/geojson/datasets` → list
### GET `/api/geojson/features?idsubsls=...` → `[GeoJsonFeature]`

---

## Georeference (stage 2, stubbed)

### POST `/api/georeference`
Request: `{ "map_document_id": "uuid", "dataset_id": "uuid" }` → `Job` (`GEO_PROCESS`)
### GET `/api/georeference/{id}` → `Job` + output object key
### POST `/api/georeference/{id}/accept`
### POST `/api/georeference/{id}/retry`

---

## Health

### GET `/api/health` → `{ "status": "ok", "db": true, "redis": true, "storage": true }`
