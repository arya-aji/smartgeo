"""Tests for rasterize module."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from geo_worker.rasterize import rasterize_cleaned_map, generate_preview

_rasterio_available = True
try:
    import rasterio
except ImportError:
    _rasterio_available = False


@pytest.mark.skipif(not _rasterio_available, reason="rasterio/GDAL not available")
class TestRasterizeCleanedMap:
    def test_writes_geotiff(self, tmp_path: Path) -> None:
        source = tmp_path / "source.jpg"
        output = tmp_path / "output.tif"

        # Create a tiny 10x10 RGB image
        img = Image.new("RGB", (10, 10), color=(255, 0, 0))
        img.save(source, format="JPEG")

        transform = (0.01, 0.0, 100.0, 0.0, -0.01, 10.0)
        rasterize_cleaned_map(source, output, transform, crs="EPSG:4326")

        assert output.exists()
        assert output.stat().st_size > 0

        with rasterio.open(output) as src:
            assert src.crs.to_string() == "EPSG:4326"
            assert src.width == 10
            assert src.height == 10
            assert src.count == 3

    def test_converts_grayscale_to_rgb(self, tmp_path: Path) -> None:
        source = tmp_path / "source.png"
        output = tmp_path / "output.tif"

        img = Image.new("L", (5, 5), color=128)
        img.save(source, format="PNG")

        transform = (1.0, 0.0, 0.0, 0.0, -1.0, 5.0)
        rasterize_cleaned_map(source, output, transform, crs="EPSG:4326")

        with rasterio.open(output) as src:
            assert src.count == 3  # converted to RGB


class TestGeneratePreview:
    def test_generates_webp(self, tmp_path: Path) -> None:
        source = tmp_path / "source.jpg"
        output = tmp_path / "preview.webp"

        img = Image.new("RGB", (2000, 2000), color=(0, 255, 0))
        img.save(source, format="JPEG")

        generate_preview(source, output, max_size=256)

        assert output.exists()
        assert output.stat().st_size > 0

        with Image.open(output) as preview:
            assert preview.format == "WEBP"
            assert max(preview.size) <= 256

    def test_handles_rgba(self, tmp_path: Path) -> None:
        source = tmp_path / "source.png"
        output = tmp_path / "preview.webp"

        img = Image.new("RGBA", (100, 100), color=(0, 0, 255, 128))
        img.save(source, format="PNG")

        generate_preview(source, output, max_size=64)

        with Image.open(output) as preview:
            assert preview.mode == "RGB"
