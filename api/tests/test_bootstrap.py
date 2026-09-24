"""Bootstrap admin seeding / recovery behaviour."""

from __future__ import annotations

from app.bootstrap import bootstrap, seed_master_targets
from app.core.security import get_password_hash, verify_password
from wss_common.config import settings
from wss_common.models import User, WssTarget


def _get_admin(db_session) -> User:
    admin = (
        db_session.query(User)
        .filter(User.username == settings.bootstrap_admin_username)
        .first()
    )
    assert admin is not None
    return admin


def test_bootstrap_force_reset_recovers_admin_password(db_session):
    admin = _get_admin(db_session)

    # Simulate a lost/rotated password: stored hash no longer matches the env.
    admin.password_hash = get_password_hash("stale-password")
    db_session.commit()

    original_password = settings.bootstrap_admin_password
    settings.bootstrap_admin_password = "recovered-secret"
    settings.bootstrap_admin_force_reset = True
    try:
        bootstrap()
    finally:
        settings.bootstrap_admin_force_reset = False
        settings.bootstrap_admin_password = original_password

    db_session.expire_all()
    admin = _get_admin(db_session)
    assert verify_password("recovered-secret", admin.password_hash)
    assert not verify_password("stale-password", admin.password_hash)

    # Leave the shared admin usable for any later tests.
    admin.password_hash = get_password_hash(original_password)
    db_session.commit()


def test_bootstrap_without_force_reset_keeps_password(db_session):
    admin = _get_admin(db_session)

    admin.password_hash = get_password_hash("stale-password")
    db_session.commit()

    # Flag is off (the default) -> bootstrap must not touch the password.
    assert settings.bootstrap_admin_force_reset is False
    bootstrap()

    db_session.expire_all()
    admin = _get_admin(db_session)
    assert verify_password("stale-password", admin.password_hash)

    # Restore the shared admin for any later tests.
    admin.password_hash = get_password_hash(settings.bootstrap_admin_password)
    db_session.commit()


def test_seed_master_targets_adds_missing_and_is_idempotent(db_session):
    before = db_session.query(WssTarget).count()

    added = seed_master_targets(db_session)
    assert added > 0
    assert db_session.query(WssTarget).count() == before + added

    # A known code from the packaged master list must now exist.
    assert (
        db_session.query(WssTarget)
        .filter(WssTarget.idsubsls == "3173010001000101")
        .first()
        is not None
    )

    # Running again is a no-op.
    assert seed_master_targets(db_session) == 0
