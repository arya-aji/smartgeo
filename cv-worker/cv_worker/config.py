"""CV-worker-specific configuration.

Most settings are imported from wss_common so the worker stays in sync with the
API and geo-worker.
"""

from __future__ import annotations

from wss_common import settings

__all__ = ["settings"]
