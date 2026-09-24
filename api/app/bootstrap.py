"""Startup bootstrap: create tables, ensure bucket, seed admin."""

from __future__ import annotations

import logging

from wss_common import storage
from wss_common.config import settings
from wss_common.db import Base, SessionLocal, engine
from wss_common.enums import UserRole
from wss_common.models import User

from app.core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)


def bootstrap() -> None:
    logger.info("Creating database tables...")
    Base.metadata.create_all(bind=engine)

    try:
        storage.ensure_bucket()
        logger.info("Storage bucket ensured.")
    except Exception as exc:
        logger.warning("Could not ensure storage bucket: %s", exc)

    db = SessionLocal()
    try:
        if db.query(User).first() is None:
            admin = User(
                name=settings.bootstrap_admin_name,
                username=settings.bootstrap_admin_username,
                password_hash=get_password_hash(settings.bootstrap_admin_password),
                role=UserRole.ADMIN,
                is_active=True,
            )
            db.add(admin)
            db.commit()
            logger.info("Bootstrap admin user created.")
        elif settings.bootstrap_admin_force_reset:
            admin = (
                db.query(User)
                .filter(User.username == settings.bootstrap_admin_username)
                .first()
            )
            if admin is None:
                logger.warning(
                    "BOOTSTRAP_ADMIN_FORCE_RESET is set but user %r does not exist.",
                    settings.bootstrap_admin_username,
                )
            elif verify_password(settings.bootstrap_admin_password, admin.password_hash):
                logger.info("Bootstrap admin password already matches; nothing to reset.")
            else:
                admin.password_hash = get_password_hash(settings.bootstrap_admin_password)
                db.commit()
                logger.info(
                    "Bootstrap admin %r password reset from BOOTSTRAP_ADMIN_PASSWORD.",
                    settings.bootstrap_admin_username,
                )
    finally:
        db.close()
