"""Tests for the GEO_PROCESS job processor."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy.orm import Session

from geo_worker.processor import process_job, GeoProcessingError
from wss_common.models import GeoJsonDataset, GeoJsonFeature, MapDocument, ProcessingJob
from wss_common.enums import DatasetStatus, JobStatus, ProcessingStatus


def _make_session_scope(session: Session):
    """Return a context-manager factory that yields the given session."""
    @contextmanager
    def _scope():
        yield session
    return _scope


class TestProcessJob:
    @pytest.fixture(autouse=True)
    def _patch_storage(self):
        """Patch storage operations so tests run offline."""
        with (
            patch("geo_worker.processor.download_file") as mock_download,
            patch("geo_worker.processor.upload_file") as mock_upload,
        ):
            self.mock_download = mock_download
            self.mock_upload = mock_upload
            yield

    def test_missing_map_document(self, db_session: Session) -> None:
        with patch("geo_worker.processor.session_scope", _make_session_scope(db_session)):
            with pytest.raises(GeoProcessingError, match="not found"):
                process_job({
                    "job_id": str(uuid.uuid4()),
                    "map_document_id": str(uuid.uuid4()),
                    "attempt": 1,
                })

    def test_missing_idsubsls(self, db_session: Session, sample_processing_job: ProcessingJob) -> None:
        doc = db_session.get(MapDocument, sample_processing_job.map_document_id)
        doc.idsubsls = None
        db_session.commit()

        with patch("geo_worker.processor.session_scope", _make_session_scope(db_session)):
            with pytest.raises(GeoProcessingError, match="no idsubsls"):
                process_job({
                    "job_id": str(sample_processing_job.id),
                    "map_document_id": str(sample_processing_job.map_document_id),
                    "attempt": 1,
                })

    def test_no_ready_dataset(self, db_session: Session, sample_processing_job: ProcessingJob) -> None:
        with patch("geo_worker.processor.session_scope", _make_session_scope(db_session)):
            with pytest.raises(GeoProcessingError, match="No READY GeoJSON dataset"):
                process_job({
                    "job_id": str(sample_processing_job.id),
                    "map_document_id": str(sample_processing_job.map_document_id),
                    "attempt": 1,
                })

    def test_feature_not_found(
        self,
        db_session: Session,
        sample_processing_job: ProcessingJob,
        sample_geojson_dataset: GeoJsonDataset,
    ) -> None:
        other = GeoJsonFeature(
            id=uuid.uuid4(),
            dataset_id=sample_geojson_dataset.id,
            idsubsls="9999999999999999",
            geometry={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]},
            properties={},
        )
        db_session.add(other)
        db_session.commit()

        with patch("geo_worker.processor.session_scope", _make_session_scope(db_session)):
            process_job({
                "job_id": str(sample_processing_job.id),
                "map_document_id": str(sample_processing_job.map_document_id),
                "attempt": 1,
            })

        db_session.refresh(sample_processing_job)
        assert sample_processing_job.status == JobStatus.FAILED
        assert "No GeoJSON feature found" in (sample_processing_job.error_message or "")

    def test_successful_flow(
        self,
        db_session: Session,
        sample_processing_job: ProcessingJob,
        sample_geojson_feature: GeoJsonFeature,
        tmp_path: Path,
    ) -> None:
        from PIL import Image

        def fake_download(key: str, local_path: Path) -> Path:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            img = Image.new("RGB", (100, 100), color=(128, 128, 128))
            img.save(local_path, format="JPEG")
            return local_path

        self.mock_download.side_effect = fake_download

        with patch("geo_worker.processor.session_scope", _make_session_scope(db_session)):
            with patch("geo_worker.processor.rasterize_cleaned_map") as mock_rasterize:
                with patch("geo_worker.processor.validate_geotiff") as mock_validate:
                    from geo_worker.validate import ValidationResult
                    mock_validate.return_value = ValidationResult(ok=True)

                    process_job({
                        "job_id": str(sample_processing_job.id),
                        "map_document_id": str(sample_processing_job.map_document_id),
                        "attempt": 1,
                    })

                    mock_rasterize.assert_called_once()
                    mock_validate.assert_called_once()

        db_session.refresh(sample_processing_job)
        assert sample_processing_job.status == JobStatus.SUCCEEDED

        doc = db_session.get(MapDocument, sample_processing_job.map_document_id)
        assert doc.processing_status == ProcessingStatus.COMPLETED
        assert doc.transform_matrix is not None
        assert doc.transform_matrix.get("geojson_dataset_id") == str(sample_geojson_feature.dataset_id)

    def test_uses_dataset_id_from_payload(
        self,
        db_session: Session,
        sample_processing_job: ProcessingJob,
        sample_geojson_dataset: GeoJsonDataset,
        tmp_path: Path,
    ) -> None:
        from PIL import Image

        feature = GeoJsonFeature(
            id=uuid.uuid4(),
            dataset_id=sample_geojson_dataset.id,
            idsubsls="3173030005003200",
            geometry={
                "type": "Polygon",
                "coordinates": [
                    [
                        [100.0, -6.0],
                        [100.1, -6.0],
                        [100.1, -6.1],
                        [100.0, -6.1],
                        [100.0, -6.0],
                    ]
                ],
            },
            properties={},
        )
        db_session.add(feature)
        db_session.commit()

        def fake_download(key: str, local_path: Path) -> Path:
            local_path.parent.mkdir(parents=True, exist_ok=True)
            img = Image.new("RGB", (100, 100), color=(128, 128, 128))
            img.save(local_path, format="JPEG")
            return local_path

        self.mock_download.side_effect = fake_download

        with patch("geo_worker.processor.session_scope", _make_session_scope(db_session)):
            with patch("geo_worker.processor.rasterize_cleaned_map"):
                with patch("geo_worker.processor.validate_geotiff") as mock_validate:
                    from geo_worker.validate import ValidationResult
                    mock_validate.return_value = ValidationResult(ok=True)

                    process_job({
                        "job_id": str(sample_processing_job.id),
                        "map_document_id": str(sample_processing_job.map_document_id),
                        "attempt": 1,
                        "geojson_dataset_id": str(sample_geojson_dataset.id),
                    })

        db_session.refresh(sample_processing_job)
        assert sample_processing_job.status == JobStatus.SUCCEEDED
