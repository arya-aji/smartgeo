"""Pytest configuration and shared fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Patch wss_common.db BEFORE any app import
import wss_common.db as db_mod

test_engine = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
test_session_maker = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

db_mod.engine = test_engine
db_mod.SessionLocal = test_session_maker

# Patch queue and storage
import wss_common.queue as queue_mod
import wss_common.storage as storage_mod

queue_mod.enqueue = lambda *args, **kwargs: None
queue_mod.queue_length = lambda job_type: 0
queue_mod.processing_length = lambda job_type: 0

storage_mod.presign_put = lambda *a, **k: "http://fake/put"
storage_mod.presign_get = lambda *a, **k: "http://fake/get"
storage_mod.object_exists = lambda *a, **k: True
storage_mod.upload_bytes = lambda *a, **k: "fake-key"
storage_mod.ensure_bucket = lambda: None


class FakeS3Client:
    def get_object(self, **kwargs):
        from io import BytesIO

        from PIL import Image

        img = Image.new("RGB", (100, 100), color="red")
        buf = BytesIO()
        img.save(buf, format="JPEG")
        buf.seek(0)
        return {"Body": buf}

    def copy_object(self, **kwargs):
        pass

    def put_object(self, **kwargs):
        pass

    def head_bucket(self, **kwargs):
        pass


storage_mod.get_s3_client = lambda: FakeS3Client()

# Now safe to import app-level code
from wss_common.config import settings
from wss_common.db import Base
from app.bootstrap import bootstrap

# Tests manage the target set explicitly; do not seed the packaged master list.
settings.seed_master_targets = False

Base.metadata.create_all(bind=test_engine)
bootstrap()

from app.main import app


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session():
    db = test_session_maker()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def admin_token(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    return resp.json()["access_token"]
