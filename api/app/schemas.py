"""Pydantic v2 request/response models."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
class UserBase(BaseModel):
    name: str
    username: str


class UserCreate(UserBase):
    password: str
    role: str = "OPERATOR"


class UserUpdate(BaseModel):
    name: str | None = None
    password: str | None = None
    is_active: bool | None = None
    role: str | None = None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    username: str
    role: str
    is_active: bool
    created_at: datetime


class UserWithStats(UserResponse):
    completed: int
    assigned: int


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
class PresignRequest(BaseModel):
    filename: str
    content_type: str
    size: int
    target_id: uuid.UUID | None = None


class PresignResponse(BaseModel):
    map_document_id: uuid.UUID
    object_key: str
    upload_url: str
    method: str
    headers: dict[str, str]
    expires_in: int


class CompleteRequest(BaseModel):
    map_document_id: uuid.UUID
    # Optional: the CV worker measures the real dimensions from the image.
    width: int | None = None
    height: int | None = None
    file_size: int | None = None


# --------------------------------------------------------------------------- #
# Jobs
# --------------------------------------------------------------------------- #
class JobCreateRequest(BaseModel):
    map_document_id: uuid.UUID


class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    map_document_id: uuid.UUID
    job_type: str
    status: str
    attempt: int
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


# --------------------------------------------------------------------------- #
# Maps
# --------------------------------------------------------------------------- #
class MapDocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    idsubsls: str | None
    processing_status: str
    quality_score: float | None
    ocr_confidence: float | None
    paper_confidence: float | None
    orientation: int | None
    upscaled: bool
    upscale_factor: float | None
    created_at: datetime
    processed_at: datetime | None
    uploaded_by: uuid.UUID | None
    uploaded_by_name: str | None = None
    preview_url: str | None = None
    review_reason: str | None


class MapDocumentDetail(MapDocumentSummary):
    ocr_raw: str | None
    ocr_candidates: list | None = None
    corners: Any = None
    source_width: int | None
    source_height: int | None
    final_width: int | None
    final_height: int | None
    processing_attempts: int
    error_message: str | None
    original_filename: str | None
    content_type: str | None
    file_size: int | None
    original_object_key: str | None = None
    final_object_key: str | None = None
    review_object_key: str | None = None
    preview_object_key: str | None = None
    original_url: str | None = None
    final_url: str | None = None
    review_url: str | None = None


class CompleteResponse(BaseModel):
    map_document: MapDocumentDetail
    job: JobResponse


# --------------------------------------------------------------------------- #
# Pagination
# --------------------------------------------------------------------------- #
class PaginationEnvelope(BaseModel):
    items: list[Any]
    total: int
    page: int
    page_size: int
    pages: int


# --------------------------------------------------------------------------- #
# Review
# --------------------------------------------------------------------------- #
class ReviewAcceptRequest(BaseModel):
    idsubsls: str | None = None


class ReviewManualIdRequest(BaseModel):
    idsubsls: str


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
class DashboardGlobal(BaseModel):
    total: int
    completed: int
    processing: int
    queued: int
    review: int
    failed: int


class DashboardQueue(BaseModel):
    cv_pending: int
    cv_processing: int
    geo_pending: int


class DashboardOperator(BaseModel):
    id: uuid.UUID
    name: str
    username: str
    completed: int
    assigned: int
    review: int
    failed: int


class DashboardResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    global_: DashboardGlobal = Field(alias="global")
    progress_percent: float
    queue: DashboardQueue
    operators: list[DashboardOperator]


# --------------------------------------------------------------------------- #
# Targets / Batches
# --------------------------------------------------------------------------- #
class WssTargetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    idsubsls: str
    status: str
    map_document_id: uuid.UUID | None
    assigned_to: uuid.UUID | None
    assigned_at: datetime | None


class PaginatedTargets(BaseModel):
    items: list[WssTargetResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BatchClaimRequest(BaseModel):
    size: int


class BatchClaimResponse(BaseModel):
    targets: list[WssTargetResponse]
    remaining: int


class TargetImportRequest(BaseModel):
    idsubsls: list[str]


class TargetImportResponse(BaseModel):
    created: int
    skipped: int
    invalid: int


# --------------------------------------------------------------------------- #
# GeoJSON
# --------------------------------------------------------------------------- #
class GeoJsonDatasetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    version: str
    source: str | None
    object_key: str
    status: str
    feature_count: int
    created_at: datetime


class GeoJsonFeatureResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    dataset_id: uuid.UUID
    idsubsls: str
    geometry: dict | None
    properties: dict | None


# --------------------------------------------------------------------------- #
# Georeference
# --------------------------------------------------------------------------- #
class GeoreferenceRequest(BaseModel):
    map_document_id: uuid.UUID
    dataset_id: uuid.UUID


class GeoreferenceResponse(BaseModel):
    job: JobResponse


class GeoreferenceDetailResponse(BaseModel):
    job: JobResponse
    output_object_key: str | None = None


# --------------------------------------------------------------------------- #
# Health
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    status: str
    db: bool
    redis: bool
    storage: bool
