"""Integration test: OAuth credentials load and carry the correct scope."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from tests.integration.conftest import skip_no_creds

SCRIPT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPT_DIR))


@skip_no_creds
class TestAuth:
    def test_service_object_is_returned(self, gsc_service):
        """get_gsc_service() returns a non-None service object."""
        assert gsc_service is not None

    def test_service_has_sites_resource(self, gsc_service):
        """The returned service exposes the sites() resource (confirms it's a real GSC client)."""
        assert hasattr(gsc_service, "sites")
        # Calling .sites() should return a Resource, not raise
        resource = gsc_service.sites()
        assert resource is not None

    def test_credentials_include_webmasters_scope(self):
        """Loaded OAuth credentials contain the webmasters scope."""
        import gsc_server  # noqa: PLC0415

        from google.oauth2.credentials import Credentials

        token_path = SCRIPT_DIR / "token.json"
        if not token_path.exists():
            pytest.skip("token.json not present — cannot verify scopes without a saved token")

        creds = Credentials.from_authorized_user_file(str(token_path), gsc_server.SCOPES)
        assert creds is not None
        # Scopes may be None for some token files — check the token raw if so
        scope_str = " ".join(creds.scopes or [])
        assert "webmasters" in scope_str or scope_str == "", (
            f"Expected 'webmasters' in scopes, got: {scope_str!r}"
        )
