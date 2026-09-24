"""Tests for GeoTIFF validation."""

from __future__ import annotations

from pathlib import Path

import pytest

from geo_worker.validate import validate_geotiff, ValidationResult

_rasterio_available = True
try:
    import rasterio
except ImportError:
    _rasterio_available = False


class TestValidateGeotiff:
    def test_missing_file(self, tmp_path: Path) -> None:
        missing = tmp_path / "missing.tif"
        result = validate_geotiff(missing)
        assert result.ok is False
        assert result.reason == "GeoTIFF does not exist"

    def test_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty.tif"
        empty.write_text("")
        result = validate_geotiff(empty)
        assert result.ok is False
        assert "empty" in (result.reason or "").lower()

    @pytest.mark.skipif(not _rasterio_available, reason="rasterio/GDAL not available")
    def test_valid_geotiff(self, tmp_path: Path) -> None:
        # Create a minimal valid GeoTIFF via rasterio directly
        import numpy as np
        from rasterio.transform import Affine

        path = tmp_path / "valid.tif"
        data = np.ones((10, 10), dtype=np.uint8) * 128
        transform = Affine.identity() * Affine.translation(100.0, -6.0) * Affine.scale(0.01, -0.01)

        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=10,
            width=10,
            count=1,
            dtype=rasterio.uint8,
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(data, 1)

        result = validate_geotiff(path, expected_bounds={"min_x": 100.0, "min_y": -6.1, "max_x": 100.1, "max_y": -6.0})
        assert result.ok is True

    @pytest.mark.skipif(not _rasterio_available, reason="rasterio/GDAL not available")
    def test_bounds_do_not_intersect(self, tmp_path: Path) -> None:
        import numpy as np
        from rasterio.transform import Affine

        path = tmp_path / "far.tif"
        data = np.ones((10, 10), dtype=np.uint8)
        transform = Affine.translation(200.0, 0.0) * Affine.scale(1.0, -1.0)

        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=10,
            width=10,
            count=1,
            dtype=rasterio.uint8,
            crs="EPSG:4326",
            transform=transform,
        ) as dst:
            dst.write(data, 1)

        result = validate_geotiff(
            path,
            expected_bounds={"min_x": 0.0, "min_y": 0.0, "max_x": 1.0, "max_y": 1.0},
        )
        assert result.ok is False
        assert "do not intersect" in (result.reason or "")
