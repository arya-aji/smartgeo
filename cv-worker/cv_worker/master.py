"""Master ID list loader: fetch all idsubsls values from wss_targets."""

from __future__ import annotations

import logging

from sqlalchemy import select

from wss_common.db import session_scope
from wss_common.models import WssTarget

logger = logging.getLogger(__name__)


def load_master_ids() -> set[str]:
    """Load the set of valid idsubsls strings from the database.

    Deliberately NOT cached: an administrator can import master IDs at any time
    and the workers must honour the new list on the very next job. Caching this
    per process previously meant freshly imported IDs were ignored until the
    worker was restarted, which silently sent valid maps to review.

    The table is small (the full target set is ~5.5k rows) and the query is
    indexed, so the cost is negligible next to the image pipeline itself.
    """
    try:
        with session_scope() as session:
            result = session.execute(select(WssTarget.idsubsls))
            ids = {row[0] for row in result if row[0]}
        logger.info("Loaded %d master IDs", len(ids))
        return ids
    except Exception as exc:
        logger.warning("Failed to load master IDs: %s", exc)
        return set()


def clear_master_cache() -> None:
    """Kept for backwards compatibility; master IDs are no longer cached."""
    return None
