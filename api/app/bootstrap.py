"""Startup bootstrap: create tables, ensure bucket, seed admin."""

from __future__ import annotations

import logging

from wss_common import storage
from wss_common.config import settings
from wss_common.db import Base, SessionLocal, engine
from wss_common.enums import UserRole
from wss_common.models import User

from app.core.security import get_password_hash

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
    finally:
        db.close()
