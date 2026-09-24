"""Find the GeoJSON feature for a given idsubsls."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from wss_common.models import GeoJsonFeature


def find_feature_for_idsubsls(
    session: Session, dataset_id: uuid.UUID, idsubsls: str
) -> GeoJsonFeature | None:
    """Return the GeoJsonFeature whose ``idsubsls`` matches in the given dataset.

    Args:
        session: SQLAlchemy session.
        dataset_id: UUID of the geojson_dataset to search.
        idsubsls: The 16-digit IDSUBSLS string.

    Returns:
        The matching GeoJsonFeature or None.
    """
    stmt = (
        select(GeoJsonFeature)
        .where(GeoJsonFeature.dataset_id == dataset_id)
        .where(GeoJsonFeature.idsubsls == idsubsls)
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()
