"""Compute an affine transform from GeoJSON feature bounds to pixel space."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _extract_bbox(geometry: dict[str, Any] | None) -> tuple[float, float, float, float]:
    """Return (min_x, min_y, max_x, max_y) for a GeoJSON geometry object.

    Supports Polygon, MultiPolygon, Feature, and FeatureCollection shapes.
    """
    if geometry is None:
        raise ValueError("Geometry is None")

    geom_type = geometry.get("type")
    if geom_type is None:
        raise ValueError("Geometry has no 'type' field")

    if geom_type == "FeatureCollection":
        features = geometry.get("features", [])
        if not features:
            raise ValueError("FeatureCollection has no features")
        bboxes = [_extract_bbox(f.get("geometry")) for f in features if f.get("geometry")]
        if not bboxes:
            raise ValueError("FeatureCollection has no geometries")
        return (
            min(b[0] for b in bboxes),
            min(b[1] for b in bboxes),
            max(b[2] for b in bboxes),
            max(b[3] for b in bboxes),
        )

    if geom_type == "Feature":
        return _extract_bbox(geometry.get("geometry"))

    if geom_type == "Polygon":
        coords = geometry.get("coordinates", [])
        if not coords:
            raise ValueError("Polygon has no coordinates")
        # coords is a list of rings; exterior ring is first
        flat = [pt for ring in coords for pt in ring]
        if not flat:
            raise ValueError("Polygon has no points")
        xs = [pt[0] for pt in flat]
        ys = [pt[1] for pt in flat]
        return (min(xs), min(ys), max(xs), max(ys))

    if geom_type == "MultiPolygon":
        coords = geometry.get("coordinates", [])
        if not coords:
            raise ValueError("MultiPolygon has no coordinates")
        flat = [pt for poly in coords for ring in poly for pt in ring]
        if not flat:
            raise ValueError("MultiPolygon has no points")
        xs = [pt[0] for pt in flat]
        ys = [pt[1] for pt in flat]
        return (min(xs), min(ys), max(xs), max(ys))

    raise ValueError(f"Unsupported geometry type: {geom_type}")


@dataclass(frozen=True)
class TransformResult:
    """Affine transform coefficients and source bounds.

    Mapping from pixel space (col, row) to geographic space (x, y):
        x = a * col + b * row + c
        y = d * col + e * row + f

    For a north-up image, b and d are zero.
    """

    a: float
    b: float
    c: float
    d: float
    e: float
    f: float
    source_bounds: dict[str, float]

    def to_affine(self) -> tuple[float, float, float, float, float, float]:
        """Return the 6-element affine tuple (a, b, c, d, e, f)."""
        return (self.a, self.b, self.c, self.d, self.e, self.f)


def compute_transform(
    geometry: dict[str, Any] | None,
    cleaned_map_path: Path,
) -> TransformResult:
    """Compute an affine transform mapping the cleaned map to the feature bounds.

    The image origin (top-left) maps to (min_x, max_y) so that pixel
    coordinates increase east and south (standard north-up orientation).

    Args:
        geometry: GeoJSON geometry dict.
        cleaned_map_path: Path to the cleaned map image.

    Returns:
        TransformResult with coefficients and bounds.
    """
    from PIL import Image

    min_x, min_y, max_x, max_y = _extract_bbox(geometry)

    with Image.open(cleaned_map_path) as img:
        width, height = img.size

    if width == 0 or height == 0:
        raise ValueError("Cleaned map has zero dimensions")

    # Pixel size in geographic units
    a = (max_x - min_x) / width
    e = -(max_y - min_y) / height  # negative because image y grows downward
    c = min_x
    f = max_y

    return TransformResult(
        a=a,
        b=0.0,
        c=c,
        d=0.0,
        e=e,
        f=f,
        source_bounds={
            "min_x": min_x,
            "min_y": min_y,
            "max_x": max_x,
            "max_y": max_y,
        },
    )
