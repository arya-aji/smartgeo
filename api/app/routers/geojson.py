"""GeoJSON router."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from wss_common import storage
from wss_common.db import get_session
from wss_common.enums import DatasetStatus
from wss_common.models import GeoJsonDataset, GeoJsonFeature, User

from app.core.deps import get_current_user
from app.schemas import GeoJsonDatasetResponse, GeoJsonFeatureResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/datasets", response_model=GeoJsonDatasetResponse)
def create_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    version: str = Form(...),
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> dict:
    content = file.file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON",
        ) from exc

    if data.get("type") != "FeatureCollection":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Expected GeoJSON FeatureCollection",
        )

    object_key = f"geojson/{name}/{version}.geojson"
    storage.upload_bytes(content, object_key, content_type="application/geo+json")

    dataset = GeoJsonDataset(
        name=name,
        version=version,
        source=file.filename,
        object_key=object_key,
        status=DatasetStatus.READY,
    )
    db.add(dataset)
    db.flush()

    features = data.get("features", [])
    for feature in features:
        props = feature.get("properties", {})
        idsubsls = props.get("idsubsls") or props.get("IDSUBSLS") or ""
        geom = feature.get("geometry")
        gf = GeoJsonFeature(
            dataset_id=dataset.id,
            idsubsls=str(idsubsls),
            geometry=geom,
            properties=props,
        )
        db.add(gf)

    db.commit()
    db.refresh(dataset)

    return {
        "id": dataset.id,
        "name": dataset.name,
        "version": dataset.version,
        "source": dataset.source,
        "object_key": dataset.object_key,
        "status": dataset.status.value,
        "feature_count": len(features),
        "created_at": dataset.created_at,
    }


@router.get("/datasets", response_model=list[GeoJsonDatasetResponse])
def list_datasets(
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[dict]:
    datasets = db.query(GeoJsonDataset).all()
    result = []
    for ds in datasets:
        count = db.query(GeoJsonFeature).filter(GeoJsonFeature.dataset_id == ds.id).count()
        result.append(
            {
                "id": ds.id,
                "name": ds.name,
                "version": ds.version,
                "source": ds.source,
                "object_key": ds.object_key,
                "status": ds.status.value,
                "feature_count": count,
                "created_at": ds.created_at,
            }
        )
    return result


@router.get("/features", response_model=list[GeoJsonFeatureResponse])
def list_features(
    idsubsls: str,
    db: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
) -> list[GeoJsonFeature]:
    return (
        db.query(GeoJsonFeature)
        .filter(GeoJsonFeature.idsubsls == idsubsls)
        .all()
    )
