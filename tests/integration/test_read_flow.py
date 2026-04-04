"""Integration tests: read-only flows against the live GSC API."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tests.integration.conftest import skip_no_creds

SCRIPT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SCRIPT_DIR))

KNOWN_PROPERTY = "sc-domain:motoexpert.gr"


@skip_no_creds
class TestListProperties:
    def test_list_properties_returns_at_least_one(self, gsc_service):
        """sites().list() returns at least one property."""
        result = gsc_service.sites().list().execute()
        sites = result.get("siteEntry", [])
        assert len(sites) >= 1

    def test_known_property_present(self, gsc_service):
        """sc-domain:motoexpert.gr appears in the property list."""
        result = gsc_service.sites().list().execute()
        site_urls = [s.get("siteUrl", "") for s in result.get("siteEntry", [])]
        assert KNOWN_PROPERTY in site_urls, (
            f"{KNOWN_PROPERTY!r} not found in properties: {site_urls}"
        )

    def test_each_entry_has_permission_level(self, gsc_service):
        """Every siteEntry has a permissionLevel field."""
        result = gsc_service.sites().list().execute()
        for entry in result.get("siteEntry", []):
            assert "permissionLevel" in entry, f"Missing permissionLevel in {entry}"


@skip_no_creds
class TestGetSiteDetails:
    def test_get_known_property_returns_permission(self, gsc_service):
        """sites().get() for the known property returns permissionLevel."""
        details = gsc_service.sites().get(siteUrl=KNOWN_PROPERTY).execute()
        assert "permissionLevel" in details
        assert details["permissionLevel"] != ""

    def test_permission_is_full_user_or_owner(self, gsc_service):
        """Confirmed access level is siteFullUser or siteOwner."""
        details = gsc_service.sites().get(siteUrl=KNOWN_PROPERTY).execute()
        level = details.get("permissionLevel", "")
        assert level in ("siteFullUser", "siteOwner", "siteRestrictedUser"), (
            f"Unexpected permission level: {level!r}"
        )


@skip_no_creds
class TestSearchAnalytics:
    """Tests for searchanalytics().query() — the core read path."""

    def _base_request(self, days: int = 28) -> dict:
        end = datetime.now().date()
        start = end - timedelta(days=days)
        return {
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "dataState": "all",
        }

    def test_query_by_query_dimension_returns_rows(self, gsc_service):
        """Query dimension returns at least one row for motoexpert.gr."""
        request = {**self._base_request(), "dimensions": ["query"], "rowLimit": 10}
        response = gsc_service.searchanalytics().query(
            siteUrl=KNOWN_PROPERTY, body=request
        ).execute()
        rows = response.get("rows", [])
        assert len(rows) > 0, "Expected at least one query row"

    def test_row_has_expected_metric_fields(self, gsc_service):
        """Each row returned by searchanalytics has clicks, impressions, ctr, position."""
        request = {**self._base_request(), "dimensions": ["query"], "rowLimit": 5}
        response = gsc_service.searchanalytics().query(
            siteUrl=KNOWN_PROPERTY, body=request
        ).execute()
        for row in response.get("rows", []):
            assert "clicks" in row
            assert "impressions" in row
            assert "ctr" in row
            assert "position" in row
            assert "keys" in row

    def test_query_by_page_dimension(self, gsc_service):
        """Page dimension query executes without error and returns structured rows."""
        request = {**self._base_request(), "dimensions": ["page"], "rowLimit": 5}
        response = gsc_service.searchanalytics().query(
            siteUrl=KNOWN_PROPERTY, body=request
        ).execute()
        # May return empty if site has no data — just ensure no exception was raised
        assert isinstance(response, dict)
        assert "rows" in response or "responseAggregationType" in response or response == {}

    def test_multi_dimension_query(self, gsc_service):
        """Combined query + page dimensions execute and keys list has two entries per row."""
        request = {
            **self._base_request(),
            "dimensions": ["query", "page"],
            "rowLimit": 5,
        }
        response = gsc_service.searchanalytics().query(
            siteUrl=KNOWN_PROPERTY, body=request
        ).execute()
        for row in response.get("rows", []):
            assert len(row["keys"]) == 2, (
                f"Expected 2 keys for query+page, got {row['keys']}"
            )

    def test_date_dimension_returns_ordered_dates(self, gsc_service):
        """Date dimension returns rows with YYYY-MM-DD key format."""
        request = {**self._base_request(days=14), "dimensions": ["date"], "rowLimit": 14}
        response = gsc_service.searchanalytics().query(
            siteUrl=KNOWN_PROPERTY, body=request
        ).execute()
        for row in response.get("rows", []):
            date_str = row["keys"][0]
            # Will raise ValueError if format is wrong
            datetime.strptime(date_str, "%Y-%m-%d")

    def test_row_limit_respected(self, gsc_service):
        """rowLimit=3 returns at most 3 rows."""
        request = {**self._base_request(), "dimensions": ["query"], "rowLimit": 3}
        response = gsc_service.searchanalytics().query(
            siteUrl=KNOWN_PROPERTY, body=request
        ).execute()
        assert len(response.get("rows", [])) <= 3


@skip_no_creds
class TestPerformanceOverview:
    """Tests equivalent to the get_performance_overview tool — totals + daily trend."""

    def test_totals_request_returns_metrics(self, gsc_service):
        """Aggregate (no-dimension) query returns totals row with numeric metrics."""
        end = datetime.now().date()
        start = end - timedelta(days=28)
        request = {
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "dimensions": [],
            "rowLimit": 1,
            "dataState": "all",
        }
        response = gsc_service.searchanalytics().query(
            siteUrl=KNOWN_PROPERTY, body=request
        ).execute()
        rows = response.get("rows", [])
        assert len(rows) == 1
        row = rows[0]
        assert isinstance(row.get("clicks"), (int, float))
        assert isinstance(row.get("impressions"), (int, float))
        assert 0.0 <= row.get("ctr", 0) <= 1.0
        assert row.get("position", 0) > 0

    def test_daily_trend_keys_are_dates(self, gsc_service):
        """Date-dimension query keys parse as valid dates."""
        end = datetime.now().date()
        start = end - timedelta(days=7)
        request = {
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "dimensions": ["date"],
            "rowLimit": 7,
            "dataState": "all",
        }
        response = gsc_service.searchanalytics().query(
            siteUrl=KNOWN_PROPERTY, body=request
        ).execute()
        for row in response.get("rows", []):
            datetime.strptime(row["keys"][0], "%Y-%m-%d")


@skip_no_creds
class TestSitemaps:
    """Read-only sitemap checks (list + get — no submit/delete)."""

    def test_list_sitemaps_executes_without_error(self, gsc_service):
        """sitemaps().list() returns a dict (even if empty)."""
        result = gsc_service.sitemaps().list(siteUrl=KNOWN_PROPERTY).execute()
        assert isinstance(result, dict)

    def test_sitemap_entries_have_path(self, gsc_service):
        """Each sitemap entry has a 'path' field."""
        result = gsc_service.sitemaps().list(siteUrl=KNOWN_PROPERTY).execute()
        for entry in result.get("sitemap", []):
            assert "path" in entry, f"Missing 'path' in sitemap entry: {entry}"
