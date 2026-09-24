"""Targets list endpoint — the region view backing the Map page."""

from __future__ import annotations

from datetime import datetime, timezone

from wss_common.enums import ProcessingStatus, TargetStatus
from wss_common.models import MapDocument, WssTarget


def test_list_targets_returns_pagination_and_url_fields(client, admin_token):
    resp = client.get(
        "/api/targets?page=1&page_size=5",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert {"items", "total", "page", "page_size", "pages"}.issubset(data.keys())
    for item in data["items"]:
        assert "preview_url" in item
        assert "final_url" in item
        assert "download_url" in item


def test_list_targets_attaches_map_urls(client, admin_token, db_session):
    idsubsls = "9000000000000001"
    doc = MapDocument(
        processing_status=ProcessingStatus.COMPLETED,
        original_object_key=f"original/{idsubsls}.jpg",
        final_object_key=f"maps/{idsubsls}.jpg",
        preview_object_key=f"preview/{idsubsls}.webp",
        idsubsls=idsubsls,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    target = WssTarget(
        idsubsls=idsubsls,
        status=TargetStatus.COMPLETED,
        map_document_id=doc.id,
    )
    db_session.add(target)
    db_session.commit()

    resp = client.get(
        f"/api/targets?q={idsubsls}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 1
    item = items[0]
    # conftest patches storage.presign_get to a fixed URL.
    assert item["preview_url"] == "http://fake/get"
    assert item["final_url"] == "http://fake/get"
    assert item["download_url"] == "http://fake/get"


def test_list_targets_without_map_has_null_urls(client, admin_token, db_session):
    idsubsls = "9000000000000002"
    db_session.add(WssTarget(idsubsls=idsubsls, status=TargetStatus.PENDING))
    db_session.commit()

    resp = client.get(
        f"/api/targets?q={idsubsls}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    item = resp.json()["items"][0]
    assert item["preview_url"] is None
    assert item["final_url"] is None
    assert item["download_url"] is None


def test_list_targets_mine_filters_by_assignee(client, admin_token, db_session):
    idsubsls = "9000000000000011"
    # Backdate it so the claim (oldest-first, limited) is guaranteed to pick it.
    db_session.add(
        WssTarget(
            idsubsls=idsubsls,
            status=TargetStatus.PENDING,
            created_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
        )
    )
    db_session.commit()

    client.post(
        "/api/operators",
        json={"name": "Mine Op", "username": "mine_op", "password": "pw", "role": "OPERATOR"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    token = client.post(
        "/api/auth/login", json={"username": "mine_op", "password": "pw"}
    ).json()["access_token"]

    # Nothing assigned yet.
    before = client.get("/api/targets?mine=true", headers={"Authorization": f"Bearer {token}"})
    assert before.status_code == 200
    assert before.json()["total"] == 0

    client.post(
        "/api/batches/claim",
        json={"size": 100},
        headers={"Authorization": f"Bearer {token}"},
    )

    after = client.get(
        f"/api/targets?mine=true&q={idsubsls}", headers={"Authorization": f"Bearer {token}"}
    )
    assert after.status_code == 200
    assert after.json()["total"] == 1
