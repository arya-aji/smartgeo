"""Write a GeoTIFF from a cleaned map + computed affine transform."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("geo_worker.rasterize")


def rasterize_cleaned_map(
    source_image_path: Path,
    output_path: Path,
    transform: tuple[float, float, float, float, float, float],
    crs: str,
) -> None:
    """Create a GeoTIFF from a cleaned map image using the given affine + CRS.

    Args:
        source_image_path: Path to the input image (e.g. JPG).
        output_path: Destination path for the GeoTIFF.
        transform: 6-element affine tuple (a, b, c, d, e, f).
        crs: Coordinate reference system string, e.g. "EPSG:4326".
    """
    # Lazy import so the module loads even when rasterio is not installed.
    import numpy as np
    from PIL import Image
    import rasterio
    from rasterio.transform import Affine

    with Image.open(source_image_path) as img:
        # Convert to RGB if necessary
        if img.mode != "RGB":
            img = img.convert("RGB")
        arr = np.array(img)

    height, width = arr.shape[:2]
    bands = arr.shape[2] if arr.ndim == 3 else 1

    affine = Affine(*transform)

    dtype = arr.dtype
    if dtype == np.uint8:
        rio_dtype = rasterio.uint8
    else:
        rio_dtype = rasterio.uint8
        arr = arr.astype(np.uint8)

    with rasterio.open(
        output_path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=bands,
        dtype=rio_dtype,
        crs=crs,
        transform=affine,
        compress="deflate",
    ) as dst:
        if bands == 1:
            dst.write(arr, 1)
        else:
            for i in range(bands):
                dst.write(arr[:, :, i], i + 1)

    logger.info("Wrote GeoTIFF: %s (%dx%d, %s)", output_path, width, height, crs)


def generate_preview(source_image_path: Path, output_path: Path, max_size: int = 512) -> None:
    """Generate a small web-friendly preview image.

    Args:
        source_image_path: Path to the source image.
        output_path: Destination path (should end in .webp or .jpg).
        max_size: Maximum width or height in pixels.
    """
    from PIL import Image

    with Image.open(source_image_path) as img:
        img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(output_path, format="WEBP", quality=80)

    logger.info("Wrote preview: %s", output_path)
