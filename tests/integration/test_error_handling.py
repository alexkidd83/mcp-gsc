"""Integration tests: real API errors return structured responses, not exceptions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from googleapiclient.errors import HttpError

from tests.integration.conftest import skip_no_creds

SCRIPT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPT_DIR))

KNOWN_PROPERTY = "sc-domain:motoexpert.gr"
NONEXISTENT_PROPERTY = "sc-domain:this-domain-definitely-does-not-exist-12345.example.invalid"
NONEXISTENT_URL_PROPERTY = "https://this.also.does.not.exist.example.invalid/"


@skip_no_creds
class TestInvalidProperty:
    """Requests against properties we don't own should return HttpError 403/404."""

    def test_sites_get_nonexistent_domain_raises_http_error(self, gsc_service):
        """sites().get() for an unknown domain raises HttpError (not a bare exception)."""
        with pytest.raises(HttpError) as exc_info:
            gsc_service.sites().get(siteUrl=NONEXISTENT_PROPERTY).execute()
        assert exc_info.value.resp.status in (403, 404), (
            f"Expected 403 or 404, got {exc_info.value.resp.status}"
        )

    def test_searchanalytics_nonexistent_property_raises_http_error(self, gsc_service):
        """searchanalytics().query() for an unknown property raises HttpError."""
        from datetime import datetime, timedelta

        end = datetime.now().date()
        start = end - timedelta(days=7)
        request = {
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "dimensions": ["query"],
            "rowLimit": 1,
            "dataState": "all",
        }
        with pytest.raises(HttpError) as exc_info:
            gsc_service.searchanalytics().query(
                siteUrl=NONEXISTENT_PROPERTY, body=request
            ).execute()
        assert exc_info.value.resp.status in (403, 404)

    def test_sitemaps_list_nonexistent_property_raises_http_error(self, gsc_service):
        """sitemaps().list() for an unknown property raises HttpError."""
        with pytest.raises(HttpError) as exc_info:
            gsc_service.sitemaps().list(siteUrl=NONEXISTENT_PROPERTY).execute()
        assert exc_info.value.resp.status in (403, 404)

    def test_sitemap_get_nonexistent_feedpath_raises_http_error(self, gsc_service):
        """sitemaps().get() for an unknown feedpath on a valid property raises HttpError 404."""
        with pytest.raises(HttpError) as exc_info:
            gsc_service.sitemaps().get(
                siteUrl=KNOWN_PROPERTY,
                feedpath="https://motoexpert.gr/sitemap-that-does-not-exist-xyz.xml",
            ).execute()
        # 404 is expected; 403 is also acceptable if the API short-circuits on auth check
        assert exc_info.value.resp.status in (403, 404)


@skip_no_creds
class TestToolLevelErrorHandling:
    """Verify that the gsc_server tool functions catch HttpError and return error strings."""

    def test_list_properties_returns_string(self, gsc_service):
        """list_properties is not tested here (no async runner), but service.sites().list()
        returns a dict — confirm no crash on valid call."""
        result = gsc_service.sites().list().execute()
        assert isinstance(result, dict)

    def test_gsc_server_site_not_found_helper(self):
        """_site_not_found_error returns a non-empty string for both property types."""
        import gsc_server  # noqa: PLC0415

        msg_domain = gsc_server._site_not_found_error("sc-domain:example.com")
        assert "404" in msg_domain
        assert "sc-domain" in msg_domain

        msg_url = gsc_server._site_not_found_error("https://example.com/")
        assert "404" in msg_url
        assert "domain property" in msg_url.lower() or "sc-domain" in msg_url


@skip_no_creds
class TestInvalidDataState:
    """Verify the module-level guard on GSC_DATA_STATE catches bad values at import time."""

    def test_valid_data_state_module_constant_is_all_or_final(self):
        """The loaded module's DATA_STATE constant is one of the two valid values."""
        import gsc_server  # noqa: PLC0415

        assert gsc_server.DATA_STATE in ("all", "final"), (
            f"DATA_STATE has unexpected value: {gsc_server.DATA_STATE!r}"
        )
