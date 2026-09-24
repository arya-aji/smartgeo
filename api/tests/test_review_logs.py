"""Review queue preview URL and Logs (map list) ordering."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from wss_common.enums import ProcessingStatus
from wss_common.models import MapDocument


def test_review_list_exposes_review_object_url(client, admin_token, db_session):
    doc = MapDocument(
        processing_status=ProcessingStatus.NEEDS_REVIEW,
        review_object_key="review/abc.jpg",
        review_reason="low confidence",
        original_object_key="original/abc.jpg",
        idsubsls="1234000000000001",
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    resp = client.get("/api/review", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    match = [i for i in resp.json()["items"] if i["id"] == str(doc.id)]
    assert len(match) == 1
    # conftest patches storage.presign_get to a fixed URL.
    assert match[0]["preview_url"] == "http://fake/get"


def test_maps_list_is_newest_first(client, admin_token, db_session):
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    older = MapDocument(
        processing_status=ProcessingStatus.COMPLETED,
        original_object_key="original/old.jpg",
        idsubsls="1111000000000001",
        created_at=base,
    )
    newer = MapDocument(
        processing_status=ProcessingStatus.COMPLETED,
        original_object_key="original/new.jpg",
        idsubsls="1111000000000002",
        created_at=base + timedelta(days=1),
    )
    db_session.add_all([older, newer])
    db_session.commit()
    db_session.refresh(older)
    db_session.refresh(newer)

    resp = client.get(
        "/api/maps?q=111100000000000",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    ids = [item["id"] for item in resp.json()["items"]]
    assert ids.index(str(newer.id)) < ids.index(str(older.id))


def test_accept_review_returns_object_urls(client, admin_token, db_session):
    idsubsls = "1234000000000002"
    doc = MapDocument(
        processing_status=ProcessingStatus.NEEDS_REVIEW,
        review_object_key="review/accept.jpg",
        original_object_key="original/accept.jpg",
        idsubsls=idsubsls,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    resp = client.post(
        f"/api/review/{doc.id}/accept",
        json={"idsubsls": idsubsls},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processing_status"] == "COMPLETED"
    # conftest patches storage.presign_get to a fixed URL.
    assert data["final_url"] == "http://fake/get"
    assert data["review_url"] == "http://fake/get"
    assert data["original_url"] == "http://fake/get"
