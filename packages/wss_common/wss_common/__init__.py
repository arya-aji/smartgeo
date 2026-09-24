"""Shared contracts for the WSS Map Processing Platform.

This package is imported by both the FastAPI service and the Python workers so
that the database schema, job-state machine, object-storage layout and queue
message format stay in sync across services.
"""

from .config import settings
from .enums import (
    DatasetStatus,
    JobStatus,
    JobType,
    ProcessingStatus,
    TargetStatus,
    UserRole,
)

__all__ = [
    "settings",
    "UserRole",
    "ProcessingStatus",
    "JobStatus",
    "JobType",
    "TargetStatus",
    "DatasetStatus",
]

__version__ = "0.1.0"
