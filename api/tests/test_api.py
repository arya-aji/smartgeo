"""API integration tests (offline, no external services)."""

from __future__ import annotations

from uuid import uuid4

from wss_common.enums import JobStatus, ProcessingStatus, TargetStatus, UserRole
from wss_common.models import MapDocument, ProcessingJob, User, WssTarget


# --------------------------------------------------------------------------- #
# Auth
# --------------------------------------------------------------------------- #
def test_login_success(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["username"] == "admin"


def test_login_failure(client):
    resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert resp.status_code == 401


def test_auth_me(client, admin_token):
    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["role"] == "ADMIN"


# --------------------------------------------------------------------------- #
# Uploads
# --------------------------------------------------------------------------- #
def test_presign_bad_content_type(client, admin_token):
    resp = client.post(
        "/api/uploads/presign",
        json={"filename": "test.jpg", "content_type": "application/pdf", "size": 1024},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 400


def test_upload_complete_creates_job(client, admin_token):
    # Presign
    presign_resp = client.post(
        "/api/uploads/presign",
        json={"filename": "test.jpg", "content_type": "image/jpeg", "size": 1024},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert presign_resp.status_code == 200
    doc_id = presign_resp.json()["map_document_id"]

    # Complete
    complete_resp = client.post(
        "/api/uploads/complete",
        json={"map_document_id": str(doc_id), "width": 100, "height": 100, "file_size": 1024},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert complete_resp.status_code == 200
    data = complete_resp.json()
    assert data["map_document"]["processing_status"] == "QUEUED"
    assert data["job"]["status"] == "PENDING"
    assert data["job"]["job_type"] == "CV_PROCESS"


# --------------------------------------------------------------------------- #
# Review
# --------------------------------------------------------------------------- #
def test_review_accept_promotes_to_completed(client, admin_token, db_session):
    # Create a doc in NEEDS_REVIEW state directly
    doc = MapDocument(
        processing_status=ProcessingStatus.NEEDS_REVIEW,
        review_object_key="review/test.jpg",
        original_object_key="original/test.jpg",
        idsubsls="1234567890123456",
        uploaded_by=None,
    )
    db_session.add(doc)
    db_session.commit()
    db_session.refresh(doc)

    resp = client.post(
        f"/api/review/{doc.id}/accept",
        json={},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["processing_status"] == "COMPLETED"
    assert data["final_object_key"] is not None
    assert data["preview_object_key"] is not None


# --------------------------------------------------------------------------- #
# Dashboard
# --------------------------------------------------------------------------- #
def test_dashboard_shape(client, admin_token):
    resp = client.get("/api/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert "global" in data
    assert "progress_percent" in data
    assert "queue" in data
    assert "operators" in data
    assert "total" in data["global"]


# --------------------------------------------------------------------------- #
# Batches
# --------------------------------------------------------------------------- #
def test_batches_claim_assigns_targets(client, admin_token, db_session):
    # Import targets as admin
    client.post(
        "/api/targets/import",
        json={"idsubsls": ["1111111111111111", "2222222222222222"]},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Create operator
    client.post(
        "/api/operators",
        json={"name": "Op", "username": "op1", "password": "op123", "role": "OPERATOR"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    # Login as operator
    login_resp = client.post("/api/auth/login", json={"username": "op1", "password": "op123"})
    assert login_resp.status_code == 200
    op_token = login_resp.json()["access_token"]

    # Claim batch
    claim_resp = client.post(
        "/api/batches/claim",
        json={"size": 10},
        headers={"Authorization": f"Bearer {op_token}"},
    )
    assert claim_resp.status_code == 200
    data = claim_resp.json()
    assert len(data["targets"]) == 2
    assert data["remaining"] == 0

    for t in data["targets"]:
        assert t["status"] == "ASSIGNED"
