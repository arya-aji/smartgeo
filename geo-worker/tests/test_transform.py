"""Tests for affine transform computation and GeoJSON bbox extraction."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from geo_worker.transform import _extract_bbox, compute_transform, TransformResult


class TestExtractBbox:
    def test_polygon(self) -> None:
        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [10.0, 20.0],
                    [30.0, 20.0],
                    [30.0, 40.0],
                    [10.0, 40.0],
                    [10.0, 20.0],
                ]
            ],
        }
        assert _extract_bbox(geometry) == (10.0, 20.0, 30.0, 40.0)

    def test_multipolygon(self) -> None:
        geometry = {
            "type": "MultiPolygon",
            "coordinates": [
                [
                    [
                        [0.0, 0.0],
                        [10.0, 0.0],
                        [10.0, 10.0],
                        [0.0, 10.0],
                        [0.0, 0.0],
                    ]
                ],
                [
                    [
                        [20.0, 20.0],
                        [30.0, 20.0],
                        [30.0, 30.0],
                        [20.0, 30.0],
                        [20.0, 20.0],
                    ]
                ],
            ],
        }
        assert _extract_bbox(geometry) == (0.0, 0.0, 30.0, 30.0)

    def test_feature(self) -> None:
        geometry = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [5.0, 5.0],
                        [15.0, 5.0],
                        [15.0, 15.0],
                        [5.0, 15.0],
                        [5.0, 5.0],
                    ]
                ],
            },
            "properties": {},
        }
        assert _extract_bbox(geometry) == (5.0, 5.0, 15.0, 15.0)

    def test_feature_collection(self) -> None:
        geometry = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [0.0, 0.0],
                                [10.0, 0.0],
                                [10.0, 10.0],
                                [0.0, 10.0],
                                [0.0, 0.0],
                            ]
                        ],
                    },
                    "properties": {},
                },
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [20.0, 20.0],
                                [30.0, 20.0],
                                [30.0, 30.0],
                                [20.0, 30.0],
                                [20.0, 20.0],
                            ]
                        ],
                    },
                    "properties": {},
                },
            ],
        }
        assert _extract_bbox(geometry) == (0.0, 0.0, 30.0, 30.0)

    def test_none_geometry_raises(self) -> None:
        with pytest.raises(ValueError, match="Geometry is None"):
            _extract_bbox(None)

    def test_unsupported_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported geometry type"):
            _extract_bbox({"type": "Point", "coordinates": [0, 0]})


class TestComputeTransform:
    def test_hand_computed_example(self, tmp_path: Path) -> None:
        """Verify transform coefficients against a hand-computed example.

        Image: 1000 x 500 pixels
        Bounds: min_x=106.0, min_y=-6.1, max_x=106.1, max_y=-6.0

        Expected:
          a = (106.1 - 106.0) / 1000 = 0.0001
          e = -(-6.0 - (-6.1)) / 500 = -0.0002
          c = 106.0
          f = -6.0
        """
        img_path = tmp_path / "test.jpg"
        img = Image.new("RGB", (1000, 500), color=(128, 128, 128))
        img.save(img_path, format="JPEG")

        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [106.0, -6.1],
                    [106.1, -6.1],
                    [106.1, -6.0],
                    [106.0, -6.0],
                    [106.0, -6.1],
                ]
            ],
        }

        result = compute_transform(geometry, img_path)

        assert result.a == pytest.approx(0.0001)
        assert result.e == pytest.approx(-0.0002)
        assert result.c == pytest.approx(106.0)
        assert result.f == pytest.approx(-6.0)
        assert result.b == 0.0
        assert result.d == 0.0
        assert result.source_bounds == {
            "min_x": 106.0,
            "min_y": -6.1,
            "max_x": 106.1,
            "max_y": -6.0,
        }

    def test_to_affine_tuple(self, tmp_path: Path) -> None:
        img_path = tmp_path / "test.jpg"
        Image.new("RGB", (100, 100), color=(0, 0, 0)).save(img_path, format="JPEG")

        geometry = {
            "type": "Polygon",
            "coordinates": [
                [
                    [0.0, 0.0],
                    [1.0, 0.0],
                    [1.0, 1.0],
                    [0.0, 1.0],
                    [0.0, 0.0],
                ]
            ],
        }

        result = compute_transform(geometry, img_path)
        affine = result.to_affine()
        assert affine == (result.a, result.b, result.c, result.d, result.e, result.f)
