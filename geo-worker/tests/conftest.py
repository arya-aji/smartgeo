"""Shared test fixtures for the geo-worker test suite."""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

# Force SQLite for tests before any wss_common imports (which create engines).
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

# Ensure repo root is on path so wss_common imports work
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

# Purge cached wss_common modules so the env var is respected on reload.
_mods = [k for k in sys.modules if k.startswith("wss_common")]
for _m in _mods:
    del sys.modules[_m]

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from wss_common.db import Base
from wss_common.models import GeoJsonDataset, GeoJsonFeature, MapDocument, ProcessingJob, User
from wss_common.enums import (
    DatasetStatus,
    JobStatus,
    JobType,
    ProcessingStatus,
    UserRole,
)


@pytest.fixture
def db_engine():
    """Create an in-memory SQLite engine for isolated tests."""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Session:
    """Yield a transactional session that rolls back after the test."""
    connection = db_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False, class_=Session)()
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_user(db_session: Session) -> User:
    user = User(
        id=uuid.uuid4(),
        name="Test User",
        username="testuser",
        password_hash="hashed",
        role=UserRole.OPERATOR,
    )
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def sample_map_document(db_session: Session, sample_user: User) -> MapDocument:
    doc = MapDocument(
        id=uuid.uuid4(),
        idsubsls="3173030005003200",
        original_object_key="original/test.jpg",
        processing_status=ProcessingStatus.COMPLETED,
        uploaded_by=sample_user.id,
    )
    db_session.add(doc)
    db_session.commit()
    return doc


@pytest.fixture
def sample_processing_job(db_session: Session, sample_map_document: MapDocument) -> ProcessingJob:
    job = ProcessingJob(
        id=uuid.uuid4(),
        map_document_id=sample_map_document.id,
        job_type=JobType.GEO_PROCESS,
        status=JobStatus.PENDING,
        attempt=1,
    )
    db_session.add(job)
    db_session.commit()
    return job


@pytest.fixture
def sample_geojson_dataset(db_session: Session) -> GeoJsonDataset:
    dataset = GeoJsonDataset(
        id=uuid.uuid4(),
        name="Test Dataset",
        version="1.0.0",
        source="test",
        object_key="geojson/test.json",
        status=DatasetStatus.READY,
    )
    db_session.add(dataset)
    db_session.commit()
    return dataset


@pytest.fixture
def sample_geojson_feature(db_session: Session, sample_geojson_dataset: GeoJsonDataset) -> GeoJsonFeature:
    feature = GeoJsonFeature(
        id=uuid.uuid4(),
        dataset_id=sample_geojson_dataset.id,
        idsubsls="3173030005003200",
        geometry={
            "type": "Polygon",
            "coordinates": [
                [
                    [106.0, -6.0],
                    [106.1, -6.0],
                    [106.1, -6.1],
                    [106.0, -6.1],
                    [106.0, -6.0],
                ]
            ],
        },
        properties={"name": "Test Feature"},
    )
    db_session.add(feature)
    db_session.commit()
    return feature
