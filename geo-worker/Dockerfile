FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# No extra system runtime libs required (rasterio & Pillow bundle needed libs in manylinux wheels)

WORKDIR /app

COPY packages/wss_common /app/packages/wss_common
RUN pip install /app/packages/wss_common

COPY geo-worker/requirements.txt /app/geo-worker/requirements.txt
RUN pip install -r /app/geo-worker/requirements.txt

COPY geo-worker /app/geo-worker

WORKDIR /app/geo-worker

CMD ["python", "-m", "geo_worker.main"]
