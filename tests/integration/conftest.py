"""Integration test fixtures — skip if GSC credentials are not configured."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Allow importing gsc_server from the project root without installing the package
SCRIPT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPT_DIR))

TOKEN_PATH = SCRIPT_DIR / "token.json"
CLIENT_SECRETS_PATH = SCRIPT_DIR / "client_secrets.json"


def _credentials_available() -> bool:
    """Return True if OAuth token or client secrets are present."""
    return TOKEN_PATH.exists() or CLIENT_SECRETS_PATH.exists()


pytestmark = pytest.mark.integration

skip_no_creds = pytest.mark.skipif(
    not _credentials_available(),
    reason="GSC credentials not found — expected token.json or client_secrets.json next to gsc_server.py",
)


@pytest.fixture(scope="session")
def gsc_service():
    """Return a live, authenticated GSC service object (session-scoped to avoid re-auth)."""
    import gsc_server  # noqa: PLC0415 — late import keeps the module out of unit-test context

    return gsc_server.get_gsc_service()
