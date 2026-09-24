"""Canonical enumerations shared by the API and the workers.

Values are stored as strings in PostgreSQL so they remain readable in the
database and stable across code changes.
"""

from __future__ import annotations

from enum import Enum


class UserRole(str, Enum):
    OPERATOR = "OPERATOR"
    ADMIN = "ADMIN"


class ProcessingStatus(str, Enum):
    """Lifecycle of a single map document (PRD section 21)."""

    UPLOADING = "UPLOADING"
    UPLOADED = "UPLOADED"
    QUEUED = "QUEUED"
    DETECTING_PAPER = "DETECTING_PAPER"
    CORRECTING_PERSPECTIVE = "CORRECTING_PERSPECTIVE"
    DETECTING_ORIENTATION = "DETECTING_ORIENTATION"
    ENHANCING = "ENHANCING"
    UPSCALING = "UPSCALING"
    DETECTING_TEXT = "DETECTING_TEXT"
    RECOGNIZING_ID = "RECOGNIZING_ID"
    VALIDATING_ID = "VALIDATING_ID"
    FINALIZING = "FINALIZING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"

    @classmethod
    def terminal(cls) -> set["ProcessingStatus"]:
        return {cls.COMPLETED, cls.NEEDS_REVIEW, cls.FAILED}

    @classmethod
    def in_flight(cls) -> set["ProcessingStatus"]:
        return {
            cls.DETECTING_PAPER,
            cls.CORRECTING_PERSPECTIVE,
            cls.DETECTING_ORIENTATION,
            cls.ENHANCING,
            cls.UPSCALING,
            cls.DETECTING_TEXT,
            cls.RECOGNIZING_ID,
            cls.VALIDATING_ID,
            cls.FINALIZING,
        }


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"


class JobType(str, Enum):
    CV_PROCESS = "CV_PROCESS"
    GEO_PROCESS = "GEO_PROCESS"


class TargetStatus(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class DatasetStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    FAILED = "FAILED"
