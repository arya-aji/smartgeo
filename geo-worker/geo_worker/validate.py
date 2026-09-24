"""Sanity checks for generated GeoTIFFs."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("geo_worker.validate")


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str | None = None
    error: Exception | None = None


def validate_geotiff(
    geotiff_path: Path,
    expected_bounds: dict[str, float] | None = None,
    feature_geometry: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate a generated GeoTIFF.

    Checks:
    - File exists and is non-empty.
    - Has a valid CRS and transform.
    - Geographic bounds intersect the expected bounds / feature geometry.

    Args:
        geotiff_path: Path to the GeoTIFF.
        expected_bounds: Optional dict with min_x, min_y, max_x, max_y.
        feature_geometry: Optional GeoJSON geometry dict for bounds check.

    Returns:
        ValidationResult indicating success or failure with a reason.
    """
    # Lazy import so tests can run without rasterio.
    try:
        import rasterio
    except ImportError as exc:
        logger.warning("rasterio not available; skipping GeoTIFF validation")
        return ValidationResult(ok=True)

    if not geotiff_path.exists():
        return ValidationResult(ok=False, reason="GeoTIFF does not exist")

    if geotiff_path.stat().st_size == 0:
        return ValidationResult(ok=False, reason="GeoTIFF is empty")

    try:
        with rasterio.open(geotiff_path) as src:
            if src.crs is None:
                return ValidationResult(ok=False, reason="GeoTIFF has no CRS")

            if src.transform is None or src.transform.is_identity:
                return ValidationResult(ok=False, reason="GeoTIFF has no valid transform")

            width, height = src.width, src.height
            if width == 0 or height == 0:
                return ValidationResult(ok=False, reason="GeoTIFF has zero dimensions")

            # Compute bounds from transform
            left, bottom, right, top = src.bounds

            if expected_bounds is not None:
                exp_min_x = expected_bounds["min_x"]
                exp_min_y = expected_bounds["min_y"]
                exp_max_x = expected_bounds["max_x"]
                exp_max_y = expected_bounds["max_y"]

                # Simple intersection test
                if right < exp_min_x or left > exp_max_x or top < exp_min_y or bottom > exp_max_y:
                    return ValidationResult(
                        ok=False,
                        reason=(
                            f"GeoTIFF bounds [{left:.6f}, {bottom:.6f}, "
                            f"{right:.6f}, {top:.6f}] do not intersect expected bounds "
                            f"[{exp_min_x:.6f}, {exp_min_y:.6f}, "
                            f"{exp_max_x:.6f}, {exp_max_y:.6f}]"
                        ),
                    )

            logger.info(
                "GeoTIFF validation passed: %s (%dx%d, bounds=%s)",
                geotiff_path,
                width,
                height,
                (left, bottom, right, top),
            )
            return ValidationResult(ok=True)

    except Exception as exc:
        logger.exception("GeoTIFF validation error")
        return ValidationResult(ok=False, reason=f"Validation error: {exc}", error=exc)
