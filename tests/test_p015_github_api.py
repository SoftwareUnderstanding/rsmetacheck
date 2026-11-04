"""Tests for the GitHub-API path of P015 (dead CI links).

GitHub answers 200 for any /actions/... page because it is a client-side route,
so the detector resolves workflow existence through the REST API instead.
"""
from unittest.mock import patch

import pytest

from rsmetacheck.scripts.pitfalls import p015


class FakeResponse:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        if self._payload is None:
            raise ValueError("no json")
        return self._payload


def router(routes, calls=None):
    """requests.get replacement: maps a URL substring to a FakeResponse."""
    def _get(url, **kwargs):
        if calls is not None:
            calls.append((url, kwargs))
        for fragment, response in routes.items():
            if fragment in url:
                return response
        return FakeResponse(404)
    return _get


def test_workflow_exists_is_accessible():
    calls = []
    get = router({"/repos/o/r/actions/workflows/ci.yml": FakeResponse(200, {"state": "active"})}, calls)
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status("https://github.com/o/r/actions/workflows/ci.yml")
    assert result["is_accessible"] is True
    assert result["check_method"] == "github_api"
    assert result["workflow_state"] == "active"
    assert any("api.github.com" in url for url, _ in calls)


def test_missing_workflow_in_readable_repo_is_hard_failure():
    calls = []
    get = router({
        "/repos/o/r/actions/workflows/nightly.yml": FakeResponse(404),
        "/repos/o/r": FakeResponse(200, {"full_name": "o/r"}),
    }, calls)
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status(
            "https://github.com/o/r/actions/workflows/nightly.yml")
    assert result["verdict"] == p015.HARD_FAILURE
    assert result["status_code"] == 404
    assert "does not exist" in result["error"]
    # repo probe must use the bare repo endpoint, not the actions one
    assert any(url.endswith("/repos/o/r") for url, _ in calls)


def test_missing_workflow_in_unreadable_repo_is_inconclusive():
    get = router({
        "/repos/o/r/actions/workflows/ci.yml": FakeResponse(404),
        "/repos/o/r": FakeResponse(404),
    })
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status("https://github.com/o/r/actions/workflows/ci.yml")
    assert result["verdict"] == "inconclusive"
    assert result["is_accessible"] is False


def test_badge_url_uses_api_not_image():
    get = router({"/actions/workflows/ci.yml": FakeResponse(200, {"state": "active"})})
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status(
            "https://github.com/o/r/workflows/ci.yml/badge.svg?branch=main")
    assert result["is_accessible"] is True
    assert result["check_method"] == "github_api"


def test_blob_url_missing_file_hard_failure():
    get = router({
        "/contents/.github/workflows/ci.yml": FakeResponse(404),
        "/repos/o/r": FakeResponse(200, {}),
    })
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status(
            "https://github.com/o/r/blob/main/.github/workflows/ci.yml")
    assert result["verdict"] == p015.HARD_FAILURE


def test_actions_list_with_no_workflows_is_hard_failure():
    get = router({"/actions/workflows": FakeResponse(200, {"total_count": 0, "workflows": []})})
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status("https://github.com/o/r/actions")
    assert result["verdict"] == p015.HARD_FAILURE
    assert "no workflows" in result["error"]


def test_rate_limit_is_inconclusive():
    get = router({"/actions/workflows/ci.yml": FakeResponse(403)})
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status("https://github.com/o/r/actions/workflows/ci.yml")
    assert result["verdict"] == "inconclusive"
    assert "rate limited" in result["error"].lower()


def test_non_actions_github_url_falls_back_to_html():
    get = router({"github.com/o/r/releases": FakeResponse(200)})
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status("https://github.com/o/r/releases")
    assert result["check_method"] == "http"


def test_non_github_url_uses_html():
    get = router({"travis-ci.org/o/r": FakeResponse(404)})
    with patch.object(p015.requests, "get", get):
        result = p015.check_ci_url_status("https://travis-ci.org/o/r")
    assert result["check_method"] == "http"
    assert result["verdict"] == p015.HARD_FAILURE


def test_network_error_is_inconclusive():
    def boom(url, **kwargs):
        raise p015.requests.exceptions.ConnectionError("boom")

    with patch.object(p015.requests, "get", boom):
        result = p015.check_ci_url_status("https://github.com/o/r/actions/workflows/ci.yml")
    assert result["verdict"] == "inconclusive"


def test_token_header_sent_when_configured(monkeypatch):
    calls = []
    get = router({"/actions/workflows": FakeResponse(200, {"total_count": 1})}, calls)
    monkeypatch.setenv("GITHUB_API_TOKEN", "dummy-token")
    with patch.object(p015.requests, "get", get):
        p015.check_ci_url_status("https://github.com/o/r/actions")
    assert calls[0][1]["headers"]["Authorization"] == "token dummy-token"


def test_no_token_header_when_unset(monkeypatch):
    calls = []
    get = router({"/actions/workflows": FakeResponse(200, {"total_count": 1})}, calls)
    for var in ("GITHUB_API_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    with patch.object(p015.requests, "get", get):
        p015.check_ci_url_status("https://github.com/o/r/actions")
    assert "Authorization" not in calls[0][1]["headers"]


@pytest.mark.parametrize("url,expected_kind", [
    ("https://github.com/o/r/actions/workflows/ci.yml", "workflow_file"),
    ("https://github.com/o/r/actions", "actions_list"),
    ("https://github.com/o/r/actions/workflows", "actions_list"),
    ("https://github.com/o/r/workflows/ci.yml/badge.svg", "workflow_file"),
    ("https://github.com/o/r/blob/main/.github/workflows/ci.yml", "workflow_blob"),
    ("https://github.com/o/r/tree/main/.github/workflows", "tree_workflows"),
    ("https://github.com/o/r/releases", None),
    ("https://gitlab.com/o/r/-/pipelines", None),
])
def test_url_parsing(url, expected_kind):
    target = p015.parse_github_actions_url(url)
    assert (target or {}).get("kind") == expected_kind


def test_detector_reports_api_method():
    somef_data = {"continuous_integration": [{
        "source": "repository/codemeta.json",
        "technique": "code_parser",
        "result": {"value": "https://github.com/o/r/actions/workflows/ci.yml"},
    }]}
    get = router({
        "/actions/workflows/ci.yml": FakeResponse(404),
        "/repos/o/r": FakeResponse(200, {}),
    })
    with patch.object(p015.requests, "get", get):
        result = p015.detect_ci_404_pitfall(somef_data, "test.json")
    assert result["has_pitfall"] is True
    assert result["check_method"] == "github_api"
    assert result["api_status"] == 404
