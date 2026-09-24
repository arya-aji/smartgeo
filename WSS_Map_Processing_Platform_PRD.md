# PRD --- WSS Map Processing Platform

## 1. Ringkasan

WSS Map Processing Platform adalah aplikasi untuk mengelola proses
digitalisasi dan normalisasi foto peta WSS secara terstruktur.

Sistem menerima foto peta dari operator, mendeteksi lembar peta,
memperbaiki perspektif dan orientasi, meningkatkan kualitas visual,
mengidentifikasi kode `idsubsls`, melakukan validasi terhadap master ID,
kemudian menyimpan hasil peta yang sudah dibersihkan ke object storage
Garage.

Tahap berikutnya akan mengembangkan hasil peta bersih tersebut menjadi
raster ter-georeference menggunakan dataset GeoJSON yang tersedia.

Platform dirancang untuk: - 20 operator - target awal 5.511 peta -
pemrosesan paralel berbasis queue - deployment seluruh komponen melalui
Coolify - Garage sebagai S3-compatible object storage - pemisahan API,
image-processing worker, dan geospatial worker - penyimpanan
intermediate seminimal mungkin untuk menghemat storage

------------------------------------------------------------------------

## 2. Tujuan Produk

### Tujuan utama

1.  Mempercepat proses normalisasi foto peta WSS.
2.  Mengurangi pekerjaan manual operator dalam mencari dan mengganti
    nama berdasarkan `idsubsls`.
3.  Mempertahankan keterbacaan garis, tulisan, titik, simbol, dan detail
    peta.
4.  Menjamin setiap hasil dapat ditelusuri kembali ke file asli.
5.  Menyiapkan fondasi untuk proses georeferencing menggunakan GeoJSON.
6.  Mendukung pemrosesan paralel tanpa membebani API utama.

### Bukan tujuan tahap pertama

-   Menentukan standar DPI tertentu.
-   Menghasilkan kualitas cetak profesional.
-   Georeferencing otomatis penuh pada fase awal.
-   Menggunakan AI/LLM untuk seluruh proses image processing.

Fokus tahap pertama adalah **visual fidelity dan correctness of ID**,
bukan DPI.

------------------------------------------------------------------------

# 3. Target Pengguna

## Operator

Bertugas: - mengunggah foto peta - melihat status processing - melakukan
review terhadap hasil yang tidak meyakinkan - melakukan koreksi ID
secara manual jika diperlukan

## Administrator

Bertugas: - mengelola operator - melihat progress 5.511 peta - melihat
failed/review jobs - mengelola master `idsubsls` - mengelola dataset
GeoJSON pada tahap berikutnya - memonitor processing

------------------------------------------------------------------------

# 4. Target Awal

  -----------------------------------------------------------------------
  Parameter                                                        Target
  ------------------------------ ----------------------------------------
  Operator                                                       20 orang

  Target peta                                                       5.511

  Processing model                                           Asynchronous

  Storage                                                          Garage

  Deployment                                                      Coolify

  API                                                             FastAPI

  Frontend                                                        Next.js

  Database                                                     PostgreSQL

  Queue                                                             Redis

  Image processing                                        Python + OpenCV

  OCR                                     OCR engine yang dipilih setelah
                                                                benchmark

  Geospatial processing             Python/GDAL/Rasterio/GeoPandas sesuai
                                                                kebutuhan
  -----------------------------------------------------------------------

------------------------------------------------------------------------

# 5. Arsitektur Sistem

``` text
                         ┌─────────────────┐
                         │     Next.js     │
                         │    Frontend     │
                         └────────┬────────┘
                                  │
                                  ▼
                         ┌─────────────────┐
                         │     FastAPI     │
                         │       API       │
                         └───────┬─────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
        PostgreSQL             Redis              Garage
        Metadata               Queue            Object Storage
              │                  │
              │                  ▼
              │           ┌───────────────┐
              │           │  CV Worker    │
              │           │               │
              │           │ Paper detect  │
              │           │ Perspective    │
              │           │ Orientation    │
              │           │ Enhancement    │
              │           │ OCR            │
              │           │ Validation     │
              │           └───────┬───────┘
              │                   │
              │                   ▼
              │              Garage
              │
              │           Tahap berikutnya
              │                   │
              │                   ▼
              │           ┌───────────────┐
              └──────────►│ Geo Worker    │
                          │               │
                          │ GeoJSON match │
                          │ Georeference  │
                          │ Validation    │
                          └───────┬───────┘
                                  │
                                  ▼
                               Garage
```

------------------------------------------------------------------------

# 6. Prinsip Arsitektur

## 6.1 API tidak menerima file image secara langsung

Frontend meminta presigned URL kepada API.

``` text
Frontend
   ↓
POST /uploads/presign
   ↓
FastAPI
   ↓
Presigned URL
   ↓
Frontend
   ↓
Direct upload → Garage
```

Tujuannya agar API tetap ringan meskipun 20 operator mengunggah file
secara bersamaan.

## 6.2 Processing asynchronous

Setelah upload selesai:

``` text
Garage
   ↓
FastAPI
   ↓
Redis Queue
   ↓
Worker
```

Operator tidak perlu menunggu OCR selesai dalam request HTTP.

## 6.3 Worker terpisah dari API

Image processing dapat menggunakan CPU dan memory cukup besar. Worker
tidak boleh menghambat API.

## 6.4 Processing dapat di-scale

Awal:

``` text
CV Worker × 1
```

Kemudian dapat ditingkatkan:

``` text
CV Worker × 2
CV Worker × 3
CV Worker × 4
```

tanpa perubahan pada frontend.

------------------------------------------------------------------------

# 7. Workflow Tahap 1 --- Image Processing

``` text
RAW PHOTO
   ↓
Upload to Garage
   ↓
Create Processing Job
   ↓
Redis Queue
   ↓
Detect Paper
   ↓
Perspective Correction
   ↓
Orientation Detection
   ↓
Image Enhancement
   ↓
Adaptive Upscaling
   ↓
Text Detection
   ↓
IDSUBSLS OCR
   ↓
Master ID Validation
   ↓
Quality Evaluation
   ↓
 ┌───────────────┬────────────────┐
 │               │                │
 ACCEPT       NEEDS REVIEW      FAILED
 │               │                │
 ▼               ▼                ▼
Final Map      Review Queue    Error State
```

------------------------------------------------------------------------

# 8. Paper Detection

Foto tidak selalu: - simetris - tegak - berbentuk kotak sempurna -
memiliki pencahayaan seragam

Karena itu sistem harus mendeteksi bentuk lembar peta.

### Primary method

OpenCV: - grayscale - blur - edge detection - contour detection -
mencari kandidat quadrilateral - memilih kandidat berdasarkan ukuran dan
bentuk

### Fallback

Jika contour detection gagal, sistem dapat menggunakan lightweight
computer vision model yang dilatih untuk mendeteksi lembar peta/corners.

### Output

``` json
{
  "top_left": [x, y],
  "top_right": [x, y],
  "bottom_right": [x, y],
  "bottom_left": [x, y]
}
```

Confidence detection juga disimpan.

------------------------------------------------------------------------

# 9. Perspective Correction

Setelah empat sudut ditemukan, sistem melakukan homography/perspective
transform.

Tujuan:

``` text
Foto miring
    ↓
Peta normalized
```

Output harus memiliki orientasi bidang yang konsisten untuk proses
berikutnya.

Matrix transform dapat disimpan sebagai metadata apabila diperlukan
untuk audit/reprocessing.

------------------------------------------------------------------------

# 10. Orientation Detection

Peta dapat berbentuk: - portrait - landscape - rotasi 90° - rotasi
180° - rotasi 270°

Sistem tidak boleh mengasumsikan satu orientasi.

Pendekatan awal: 1. generate kandidat orientasi 2. jalankan text/ID
detection 3. hitung confidence 4. pilih orientasi dengan hasil paling
konsisten

------------------------------------------------------------------------

# 11. Image Enhancement

Enhancement bertujuan mempertahankan keterbacaan visual.

Pipeline dapat mencakup: - exposure/illumination correction - grayscale
bila diperlukan - denoise - contrast enhancement - sharpening -
thresholding untuk jalur OCR tertentu

Enhancement tidak boleh menghilangkan: - garis tipis - titik - simbol -
teks kecil - batas wilayah

------------------------------------------------------------------------

# 12. Adaptive Upscaling

Tidak semua gambar harus di-upscale.

### Foto bagus

``` text
Source
 ↓
Perspective correction
 ↓
Enhancement
 ↓
Final
```

### Foto beresolusi rendah

``` text
Source
 ↓
Perspective correction
 ↓
Enhancement
 ↓
2× upscale
 ↓
OCR / Final
```

AI super-resolution hanya menjadi fallback untuk kasus yang benar-benar
membutuhkan dan harus divalidasi terhadap dataset nyata.

------------------------------------------------------------------------

# 13. IDSUBSLS Detection

Posisi kode `idsubsls` tidak dianggap fixed.

Sistem harus mencari teks pada area peta setelah normalisasi.

Contoh:

``` text
Text Detection
    ↓
┌───────────────────────┐
│ 3173030005003200      │
└───────────────────────┘
```

Candidate ID kemudian difilter berdasarkan pola yang diketahui.

Contoh pola awal:

``` regex
^\d{16}$
```

Pola final harus dikonfirmasi berdasarkan master data aktual.

------------------------------------------------------------------------

# 14. OCR Strategy

Sistem menggunakan text detection + text recognition.

Untuk gambar sulit, sistem dapat menjalankan beberapa variant:

``` text
Original enhanced
       │
 ┌─────┼─────┐
 ▼     ▼     ▼
A      B      C
 │     │      │
OCR   OCR    OCR
 └─────┼──────┘
       ▼
Result comparison
       ▼
Master ID matching
```

Tidak semua gambar perlu multi-pass. Multi-pass hanya digunakan jika
confidence awal rendah.

------------------------------------------------------------------------

# 15. Master ID Validation

Sistem memiliki tabel `wss_targets` yang berisi daftar ID yang
diharapkan.

Contoh:

``` text
3173030005003200
3173030005003201
3173030005003202
...
```

Hasil OCR dicocokkan dengan master.

### Validasi

-   format valid
-   panjang valid
-   ID terdapat pada master
-   ID belum digunakan jika aturan tersebut berlaku
-   similarity/fuzzy matching untuk OCR typo

Contoh:

``` text
OCR:
31730300050032OO

Candidate:
3173030005003200
```

Jika confidence tinggi, sistem dapat melakukan auto-accept.

Jika confidence sedang, masuk review.

------------------------------------------------------------------------

# 16. Quality Decision

Status hasil:

### COMPLETED

ID valid dan kualitas memenuhi threshold.

### NEEDS_REVIEW

Contoh: - OCR confidence rendah - ID tidak ditemukan pada master - paper
detection meragukan - orientasi ambigu - hasil enhancement tidak
meyakinkan

### FAILED

Contoh: - file rusak - paper tidak dapat ditemukan - processing
exception - storage error setelah retry

Threshold final ditentukan setelah benchmark terhadap sampel foto nyata.

------------------------------------------------------------------------

# 17. Storage Design

Garage digunakan sebagai S3-compatible object storage.

Struktur:

``` text
wss/
├── original/
├── maps/
├── review/
└── georeferenced/
```

### Original

``` text
original/{uuid}.jpg
```

### Final cleaned map

``` text
maps/{idsubsls}.jpg
```

### Review

``` text
review/{uuid}.jpg
```

### Georeferenced

Tahap berikutnya:

``` text
georeferenced/{idsubsls}.tif
```

------------------------------------------------------------------------

# 18. Storage Optimization

Requirement utama bukan DPI tertentu.

Target kualitas:

> Garis, tulisan, titik, simbol, dan detail peta harus tetap jelas
> dengan ukuran file seefisien mungkin.

Prinsip: - jangan menyimpan intermediate processing secara permanen -
gunakan local temporary storage pada worker - simpan hanya original,
final, dan review bila diperlukan - gunakan JPEG/WebP untuk visual map
setelah benchmark - gunakan GeoTIFF/COG untuk hasil geospatial - buat
preview beresolusi lebih kecil untuk dashboard

Contoh:

``` text
Master:
maps/3173030005003200.jpg

Preview:
preview/3173030005003200.webp
```

Preview digunakan untuk UI agar bandwidth Garage rendah.

------------------------------------------------------------------------

# 19. Original Retention

Original dapat dipertahankan sebagai arsip atau diberi retention policy.

Contoh:

``` text
Original
   ↓
Processing
   ↓
Final
   ↓
Original retained for defined period
```

Retention tidak boleh diterapkan sebelum kebutuhan audit/arsip
dikonfirmasi.

------------------------------------------------------------------------

# 20. Database

## `users`

``` text
id
name
username
role
created_at
```

## `wss_targets`

Master 5.511 target.

``` text
id
idsubsls
status
map_document_id
created_at
updated_at
```

## `map_documents`

``` text
id
idsubsls

original_object_key
final_object_key
review_object_key

source_width
source_height
final_width
final_height

orientation
paper_confidence
ocr_confidence

ocr_raw
quality_score

upscaled
upscale_factor

processing_status
processing_attempts

uploaded_by
created_at
processed_at
```

## `processing_jobs`

``` text
id
map_document_id
job_type
status
attempt
error_message
started_at
completed_at
created_at
```

## `geojson_datasets`

Untuk tahap berikutnya:

``` text
id
name
version
source
object_key
status
created_at
```

## `geojson_features`

``` text
id
dataset_id
idsubsls
geometry
properties
```

------------------------------------------------------------------------

# 21. Job States

``` text
UPLOADING
    ↓
UPLOADED
    ↓
QUEUED
    ↓
DETECTING_PAPER
    ↓
CORRECTING_PERSPECTIVE
    ↓
DETECTING_ORIENTATION
    ↓
ENHANCING
    ↓
DETECTING_TEXT
    ↓
RECOGNIZING_ID
    ↓
VALIDATING_ID
    ↓
FINALIZING
    ↓
COMPLETED
```

Alternative:

``` text
NEEDS_REVIEW
FAILED
```

------------------------------------------------------------------------

# 22. Operator Workflow

``` text
Login
 ↓
Dashboard
 ↓
Upload batch
 ↓
Upload direct to Garage
 ↓
Jobs enter queue
 ↓
Worker processes asynchronously
 ↓
Operator continues working
 ↓
Review exceptions
```

Operator tidak perlu menunggu setiap file selesai sebelum mengunggah
file berikutnya.

------------------------------------------------------------------------

# 23. Batch Assignment

Untuk 20 operator, sistem dapat menggunakan assignment agar pekerjaan
tidak duplikat.

Contoh:

``` text
Operator A
Batch 20 maps

Operator B
Batch 20 maps
```

Setelah batch selesai:

``` text
20/20 completed
      ↓
request next batch
```

Assignment dilakukan melalui database dengan mekanisme
locking/transaction untuk mencegah dua operator mendapatkan target yang
sama.

------------------------------------------------------------------------

# 24. Dashboard

### Global

``` text
TOTAL       5,511
COMPLETED   xxxx
PROCESSING  xx
QUEUED      xxxx
REVIEW      xx
FAILED      xx
```

### Progress

``` text
████████████████░░░░  82%
```

### Operator

``` text
Operator       Completed
A              275
B              270
C              275
...
```

### Review queue

Menampilkan: - image preview - OCR result - candidate ID - confidence -
reason for review - accept - retry - manual correction

------------------------------------------------------------------------

# 25. API Endpoint Awal

Contoh:

``` text
POST   /auth/login

POST   /uploads/presign
POST   /uploads/complete

POST   /jobs
GET    /jobs/{id}
POST   /jobs/{id}/retry

GET    /maps
GET    /maps/{id}

GET    /review
POST   /review/{id}/accept
POST   /review/{id}/manual-id

GET    /dashboard
```

Tahap geospatial:

``` text
POST   /geojson/datasets
GET    /geojson/datasets

POST   /georeference
GET    /georeference/{id}
POST   /georeference/{id}/accept
POST   /georeference/{id}/retry
```

------------------------------------------------------------------------

# 26. Frontend Pages

``` text
/login

/dashboard

/maps
/maps/{id}

/upload

/review

/operators

/targets

/geojson             # tahap 2
/georeference        # tahap 2
/gis/{idsubsls}      # tahap 2
```

------------------------------------------------------------------------

# 27. Georeferencing --- Tahap 2

Hasil tahap 1 menjadi input tahap 2.

``` text
Cleaned Map
     +
GeoJSON Dataset
     ↓
Match by IDSUBSLS
     ↓
Find corresponding feature
     ↓
Determine transformation
     ↓
Georeference
     ↓
Generate GeoTIFF/COG
     ↓
Quality validation
```

`idsubsls` menjadi identifier yang menghubungkan:

``` text
Raw Photo
   ↓
Cleaned Map
   ↓
GeoJSON Feature
   ↓
Georeferenced Raster
```

------------------------------------------------------------------------

# 28. GeoJSON Versioning

Dataset GeoJSON harus memiliki versi.

Contoh:

``` text
WSS Boundary
2026.1
2026.2
2027.1
```

Hasil georeferencing menyimpan:

``` text
geojson_dataset_id
geojson_version
```

Dengan demikian hasil lama tetap dapat dilacak terhadap dataset yang
digunakan.

------------------------------------------------------------------------

# 29. Geospatial Output

Untuk display:

``` text
JPEG/WebP
```

Untuk GIS:

``` text
GeoTIFF
```

Jika kebutuhan performa web/GIS meningkat, gunakan:

``` text
Cloud Optimized GeoTIFF (COG)
```

dengan: - tiling - compression - overviews

------------------------------------------------------------------------

# 30. Deployment dengan Coolify

Semua service dapat dikelola melalui Coolify.

``` text
Coolify
│
├── wss-frontend
│   └── Next.js
│
├── wss-api
│   └── FastAPI
│
├── wss-cv-worker
│   └── Python + OpenCV + OCR
│
├── wss-geo-worker
│   └── Python + GDAL/Rasterio/etc.
│
├── wss-redis
│
├── wss-postgres
│
└── wss-garage
    └── S3-compatible storage
```

Worker dapat di-scale secara independen.

Awal:

``` text
CV Worker × 1
Geo Worker × 1
```

Kemudian dapat ditambah sesuai benchmark.

------------------------------------------------------------------------

# 31. Resource Strategy

Untuk MVP, seluruh service dapat berada dalam satu server jika resource
mencukupi.

Namun workload berbeda:

``` text
Frontend → ringan
API      → ringan
Redis    → ringan
Postgres → sedang
Garage   → disk/network
CV       → CPU/RAM intensive
Geo      → CPU/disk intensive
```

Karena itu desain harus memungkinkan worker dipindahkan ke server
terpisah tanpa mengubah aplikasi.

------------------------------------------------------------------------

# 32. Observability

Minimal harus tersedia:

-   processing time per image
-   OCR confidence
-   paper detection confidence
-   failure reason
-   retry count
-   queue length
-   worker CPU/RAM
-   Garage storage usage
-   total completed
-   total review
-   total failed

Tujuan utama adalah mengetahui bottleneck setelah 100--300 foto pertama.

------------------------------------------------------------------------

# 33. Benchmark Sebelum Production

Sebelum memproses 5.511 peta, kumpulkan sekitar 100--300 foto yang
mewakili kondisi nyata.

Kelompokkan:

``` text
GOOD
MEDIUM
BAD

PORTRAIT
LANDSCAPE
ROTATED
PERSPECTIVE
BLUR
DARK
GLARE
PARTIALLY OBSCURED
```

Ukur:

``` text
Paper detection accuracy
Orientation accuracy
ID detection accuracy
Final ID accuracy
Review rate
Average processing time
Average output file size
CPU usage
RAM usage
```

Metrik utama:

> **Final correct ID accuracy + visual readability**

bukan sekadar OCR accuracy.

------------------------------------------------------------------------

# 34. Non-Functional Requirements

### Performance

-   Upload tidak menunggu processing.
-   API tetap responsif ketika worker sibuk.
-   Processing dapat berjalan paralel.
-   Queue dapat menangani seluruh target 5.511 peta.

### Reliability

-   Job dapat retry.
-   Original tidak tertimpa.
-   Failed job dapat diproses ulang.
-   Setiap hasil memiliki audit trail.

### Storage

-   Intermediate tidak dipersistenkan secara permanen.
-   Final image dikompresi.
-   Preview berukuran lebih kecil.
-   Garage digunakan sebagai source of truth untuk file.

### Security

-   Operator hanya dapat mengakses job yang menjadi kewenangannya.
-   API menggunakan authentication.
-   Presigned URL memiliki expiry.
-   Object storage tidak perlu dibuka publik.
-   Credentials Garage hanya tersedia melalui environment/secret
    management.
-   File type dan ukuran upload divalidasi.

------------------------------------------------------------------------

# 35. Acceptance Criteria Tahap 1

Sistem dianggap siap untuk pilot apabila:

-   [ ] 20 operator dapat login.
-   [ ] Operator dapat mengupload gambar secara paralel.
-   [ ] File masuk langsung ke Garage.
-   [ ] API tidak menjadi jalur transfer file utama.
-   [ ] Job otomatis masuk Redis.
-   [ ] Worker mengambil job dari queue.
-   [ ] Sistem dapat mendeteksi lembar peta pada variasi foto.
-   [ ] Sistem dapat melakukan perspective correction.
-   [ ] Sistem dapat menentukan orientasi.
-   [ ] Sistem melakukan enhancement adaptif.
-   [ ] Sistem dapat mendeteksi kandidat `idsubsls`.
-   [ ] ID dapat divalidasi terhadap master.
-   [ ] ID confidence rendah masuk review.
-   [ ] Hasil accepted disimpan dengan nama `idsubsls`.
-   [ ] Original tetap dapat ditelusuri.
-   [ ] Retry tersedia.
-   [ ] Dashboard menunjukkan progress 5.511 target.
-   [ ] Intermediate tidak memenuhi Garage secara permanen.
-   [ ] Output tetap mempertahankan garis, tulisan, titik, dan simbol
    secara jelas.

------------------------------------------------------------------------

# 36. Acceptance Criteria Tahap 2

-   [ ] GeoJSON dapat di-upload sebagai dataset.
-   [ ] Dataset memiliki version.
-   [ ] Feature dapat dicari berdasarkan `idsubsls`.
-   [ ] Cleaned map dapat dipasangkan dengan GeoJSON feature.
-   [ ] Georeferencing job menggunakan queue.
-   [ ] Hasil dapat divisualisasikan.
-   [ ] Hasil dapat diekspor sebagai GeoTIFF/COG.
-   [ ] Metadata transformation tersimpan.
-   [ ] Dataset GeoJSON yang digunakan tercatat.
-   [ ] Hasil dapat di-review sebelum final.

------------------------------------------------------------------------

# 37. MVP Scope

### Wajib

1.  Authentication
2.  Operator dashboard
3.  Upload batch
4.  Garage integration
5.  Redis queue
6.  PostgreSQL
7.  Paper detection
8.  Perspective correction
9.  Orientation detection
10. Image enhancement
11. OCR IDSUBSLS
12. Master ID validation
13. Review queue
14. Auto rename
15. Progress dashboard
16. Retry
17. Audit metadata

### Tidak wajib untuk MVP

-   AI super-resolution
-   automatic georeferencing
-   GIS web editor
-   advanced analytics
-   Kubernetes
-   distributed Garage cluster
-   complex role hierarchy

------------------------------------------------------------------------

# 38. Future Roadmap

## Phase 1 --- WSS Cleaning

``` text
Photo
→ Normalize
→ OCR
→ Validate
→ Rename
→ Store
```

## Phase 2 --- Georeferencing

``` text
Cleaned Map
+
GeoJSON
→ Match
→ Transform
→ GeoTIFF/COG
```

## Phase 3 --- GIS Validation

``` text
GeoTIFF
+
GeoJSON
→ Overlay
→ Visual QA
→ Correction
```

## Phase 4 --- Production GIS Platform

``` text
WSS
+
GeoJSON
+
Georeferenced Raster
+
GIS Viewer
+
QA
+
Export
```

------------------------------------------------------------------------

# 39. Prinsip Produk

Platform ini harus mengikuti prinsip:

> **Process once, preserve the source, store only what is useful, and
> keep every result traceable.**

Hasil tahap pertama bukan sekadar file yang sudah di-rename. Hasilnya
adalah **aset peta terstruktur** yang memiliki hubungan:

``` text
Original Photo
      │
      ▼
Map Document
      │
      ├── IDSUBSLS
      ├── Processing Metadata
      ├── Cleaned Image
      └── Quality Information
                │
                ▼
          GeoJSON Feature
                │
                ▼
        Georeferenced Raster
```

Dengan model ini, platform dapat berkembang dari alat pemrosesan foto
menjadi pipeline pengolahan data geospasial tanpa harus membangun ulang
fondasi sistem.
