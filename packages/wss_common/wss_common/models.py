"""SQLAlchemy models mirroring PRD section 20 (Database)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base
from .enums import (
    DatasetStatus,
    JobStatus,
    JobType,
    ProcessingStatus,
    TargetStatus,
    UserRole,
)

# JSONB on PostgreSQL, generic JSON elsewhere (e.g. sqlite in unit tests).
JSONType = JSON().with_variant(JSONB, "postgresql")


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role"), default=UserRole.OPERATOR, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MapDocument(Base):
    __tablename__ = "map_documents"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idsubsls: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("wss_targets.id", ondelete="SET NULL"), nullable=True
    )

    original_object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    final_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    review_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    preview_object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

    source_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    final_height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    orientation: Mapped[int | None] = mapped_column(Integer, nullable=True)  # degrees: 0/90/180/270
    paper_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    ocr_raw: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_candidates: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    quality_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    upscaled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    upscale_factor: Mapped[float | None] = mapped_column(Float, nullable=True)

    processing_status: Mapped[ProcessingStatus] = mapped_column(
        SAEnum(ProcessingStatus, name="processing_status"),
        default=ProcessingStatus.UPLOADING,
        nullable=False,
        index=True,
    )
    processing_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    corners: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    transform_matrix: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WssTarget(Base):
    __tablename__ = "wss_targets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    idsubsls: Mapped[str] = mapped_column(String(32), unique=True, index=True, nullable=False)
    status: Mapped[TargetStatus] = mapped_column(
        SAEnum(TargetStatus, name="target_status"),
        default=TargetStatus.PENDING,
        nullable=False,
        index=True,
    )
    # Circular FK with map_documents -> created via ALTER after both tables exist.
    map_document_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey(
            "map_documents.id",
            ondelete="SET NULL",
            use_alter=True,
            name="fk_wss_targets_map_document_id",
        ),
        nullable=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ProcessingJob(Base):
    __tablename__ = "processing_jobs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    map_document_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("map_documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[JobType] = mapped_column(
        SAEnum(JobType, name="job_type"), default=JobType.CV_PROCESS, nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status"),
        default=JobStatus.PENDING,
        nullable=False,
        index=True,
    )
    attempt: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GeoJsonDataset(Base):
    __tablename__ = "geojson_datasets"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)
    status: Mapped[DatasetStatus] = mapped_column(
        SAEnum(DatasetStatus, name="dataset_status"),
        default=DatasetStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class GeoJsonFeature(Base):
    __tablename__ = "geojson_features"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("geojson_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    idsubsls: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    geometry: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
