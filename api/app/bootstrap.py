"""Startup bootstrap: create tables, ensure bucket, seed admin."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from wss_common import storage
from wss_common.config import settings
from wss_common.db import Base, SessionLocal, engine
from wss_common.enums import TargetStatus, UserRole
from wss_common.models import User, WssTarget

from app.core.security import get_password_hash, verify_password

logger = logging.getLogger(__name__)

_MASTER_IDS_FILE = Path(__file__).parent / "data" / "idsubsls.txt"


def seed_master_targets(db) -> int:
    """Insert any missing master idsubsls rows so every region is visible.

    The packaged file is the authoritative master list of 16-digit sub-SLS
    codes. Rows are only added, never removed, so it is safe to run on every
    startup. Returns the number of rows added.
    """
    if not _MASTER_IDS_FILE.exists():
        logger.warning("Master idsubsls file not found: %s", _MASTER_IDS_FILE)
        return 0

    pattern = re.compile(settings.id_pattern)
    wanted: list[str] = []
    seen: set[str] = set()
    for line in _MASTER_IDS_FILE.read_text(encoding="utf-8").splitlines():
        code = line.strip()
        if not code or code in seen or not pattern.match(code):
            continue
        seen.add(code)
        wanted.append(code)

    existing = {row[0] for row in db.query(WssTarget.idsubsls).all()}
    missing = [code for code in wanted if code not in existing]
    for code in missing:
        db.add(WssTarget(idsubsls=code, status=TargetStatus.PENDING))
    if missing:
        db.commit()
    logger.info(
        "Master targets: %d in list, %d already present, %d added.",
        len(wanted),
        len(existing & seen),
        len(missing),
    )
    return len(missing)


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

        if settings.seed_master_targets:
            try:
                seed_master_targets(db)
            except Exception as exc:
                logger.warning("Could not seed master targets: %s", exc)
    finally:
        db.close()
