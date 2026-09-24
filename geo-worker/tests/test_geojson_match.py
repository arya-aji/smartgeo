"""Tests for GeoJSON feature matching logic."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.orm import Session

from geo_worker.geojson_match import find_feature_for_idsubsls
from wss_common.models import GeoJsonDataset, GeoJsonFeature
from wss_common.enums import DatasetStatus


class TestFindFeatureForIdsubsls:
    def test_found(
        self,
        db_session: Session,
        sample_geojson_dataset: GeoJsonDataset,
        sample_geojson_feature: GeoJsonFeature,
    ) -> None:
        feature = find_feature_for_idsubsls(
            db_session, sample_geojson_dataset.id, "3173030005003200"
        )
        assert feature is not None
        assert feature.idsubsls == "3173030005003200"

    def test_not_found(self, db_session: Session, sample_geojson_dataset: GeoJsonDataset) -> None:
        feature = find_feature_for_idsubsls(
            db_session, sample_geojson_dataset.id, "9999999999999999"
        )
        assert feature is None

    def test_wrong_dataset(self, db_session: Session) -> None:
        other_dataset = GeoJsonDataset(
            id=uuid.uuid4(),
            name="Other",
            version="1.0.0",
            source="other",
            object_key="geojson/other.json",
            status=DatasetStatus.READY,
        )
        db_session.add(other_dataset)
        db_session.commit()

        feature = find_feature_for_idsubsls(
            db_session, other_dataset.id, "3173030005003200"
        )
        assert feature is None
