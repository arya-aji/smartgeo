FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# tesseract for OCR; libglib2.0-0 for OpenCV headless utils (libgl1 is NOT needed for headless)
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY packages/wss_common /app/packages/wss_common
RUN pip install /app/packages/wss_common

COPY cv-worker/requirements.txt /app/cv-worker/requirements.txt
RUN pip install -r /app/cv-worker/requirements.txt

COPY cv-worker /app/cv-worker

WORKDIR /app/cv-worker

CMD ["python", "-m", "cv_worker.main"]
