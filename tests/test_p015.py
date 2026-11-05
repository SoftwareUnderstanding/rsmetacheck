import pytest
from unittest.mock import patch, Mock
from rsmetacheck.scripts.pitfalls.p015 import (
    detect_ci_404_pitfall,
    check_ci_url_status,
    is_valid_url_format
)


class TestIsValidUrlFormat:
    """Test suite for is_valid_url_format function"""

    @pytest.mark.parametrize("url,expected", [
        ("https://github.com/user/repo", True),
        ("http://example.com", True),
        ("https://travis-ci.org/user/repo", True),
        ("ftp://files.example.com", True),
        ("not-a-url", False),
        ("", False),
        ("github.com", False),
        ("://invalid", False),
        ("https://", False),
    ])
    def test_url_format_validation(self, url, expected):
        """Test URL format validation"""
        assert is_valid_url_format(url) == expected


class TestCheckCiUrlStatus:
    """Test suite for check_ci_url_status function"""

    def test_valid_url_success(self):
        """Test checking a valid accessible URL"""
        mock_response = Mock()
        mock_response.status_code = 200

        with patch('rsmetacheck.scripts.pitfalls.p015.requests.get', return_value=mock_response):
            result = check_ci_url_status("https://github.com/user/repo")

            assert result["is_accessible"] is True
            assert result["status_code"] == 200
            assert result["error"] is None

    def test_valid_url_404(self):
        """Test checking a URL that returns 404"""
        mock_response = Mock()
        mock_response.status_code = 404

        with patch('rsmetacheck.scripts.pitfalls.p015.requests.get', return_value=mock_response):
            result = check_ci_url_status("https://travis-ci.org/user/repo")

            assert result["is_accessible"] is False
            assert result["status_code"] == 404
            assert result["error"] is None

    @pytest.mark.parametrize("status_code,expected_accessible", [
        (200, True),
        (201, True),
        (204, True),
        (299, True),
        (300, False),
        (301, True),  # allow_redirects=True, so final code matters
        (302, True),
        (400, False),
        (401, False),
        (403, False),
        (404, False),
        (500, False),
        (503, False),
    ])
    def test_various_status_codes(self, status_code, expected_accessible):
        """Test various HTTP status codes"""
        mock_response = Mock()
        mock_response.status_code = status_code

        with patch('rsmetacheck.scripts.pitfalls.p015.requests.get', return_value=mock_response):
            result = check_ci_url_status("https://example.com")
            assert result["is_accessible"] == expected_accessible
            assert result["status_code"] == status_code

    def test_invalid_url_format(self):
        """Test handling of invalid URL format"""
        result = check_ci_url_status("not-a-valid-url")

        assert result["is_accessible"] is False
        assert result["status_code"] is None
        assert result["error"] == "Invalid URL format"

    def test_request_timeout(self):
        """Test handling of request timeout"""
        with patch('rsmetacheck.scripts.pitfalls.p015.requests.get',
                   side_effect=Exception("Timeout")):
            result = check_ci_url_status("https://example.com")

            assert result["is_accessible"] is False
            assert result["status_code"] is None
            assert "Timeout" in result["error"]

    def test_network_error(self):
        """Test handling of network errors"""
        with patch('rsmetacheck.scripts.pitfalls.p015.requests.get',
                   side_effect=Exception("Connection refused")):
            result = check_ci_url_status("https://example.com")

            assert result["is_accessible"] is False
            assert result["error"] is not None


class TestDetectCi404Pitfall:
    """Test suite for detect_ci_404_pitfall function"""

    @pytest.mark.parametrize(
        "somef_data,file_name,expected_has_pitfall,expected_ci_url,expected_status_code", [
            # No continuous_integration key
            (
                {},
                "test_repo.json",
                False,
                None,
                None
            ),

            # continuous_integration not a list
            (
                {"continuous_integration": "https://travis-ci.org"},
                "test_repo.json",
                False,
                None,
                None
            ),

            # Empty continuous_integration list
            (
                {"continuous_integration": []},
                "test_repo.json",
                False,
                None,
                None
            ),

            # CI URL from codemeta.json returns 404
            (
                {
                    "continuous_integration": [{
                        "source": "repository/codemeta.json",
                        "technique": "code_parser",
                        "result": {"value": "https://travis-ci.org/user/repo"}
                    }]
                },
                "test_repo.json",
                True,
                "https://travis-ci.org/user/repo",
                404
            ),

            # CI URL from codemeta.json is accessible
            (
                {
                    "continuous_integration": [{
                        "source": "repository/codemeta.json",
                        "technique": "code_parser",
                        "result": {"value": "https://github.com/user/repo/actions"}
                    }]
                },
                "test_repo.json",
                False,
                None,
                None
            ),

            # CI URL from non-codemeta source (should not trigger)
            (
                {
                    "continuous_integration": [{
                        "source": "README.md",
                        "technique": "header_analysis",
                        "result": {"value": "https://travis-ci.org/user/repo"}
                    }]
                },
                "test_repo.json",
                False,
                None,
                None
            ),

            # Missing result key
            (
                {
                    "continuous_integration": [{
                        "source": "repository/codemeta.json",
                        "technique": "code_parser"
                    }]
                },
                "test_repo.json",
                False,
                None,
                None
            ),

            # Missing value in result
            (
                {
                    "continuous_integration": [{
                        "source": "repository/codemeta.json",
                        "technique": "code_parser",
                        "result": {}
                    }]
                },
                "test_repo.json",
                False,
                None,
                None
            ),

            # Invalid URL format
            (
                {
                    "continuous_integration": [{
                        "source": "repository/codemeta.json",
                        "technique": "code_parser",
                        "result": {"value": "not-a-valid-url"}
                    }]
                },
                "test_repo.json",
                True,
                "not-a-valid-url",
                None
            ),
        ])
    def test_detect_ci_404_scenarios(self, somef_data, file_name,
                                     expected_has_pitfall, expected_ci_url,
                                     expected_status_code):
        """Test various scenarios for CI 404 detection"""
        def mock_check_ci_url_status(url, timeout=10):
            if url == "https://github.com/user/repo/actions":
                return {
                    "is_accessible": True,
                    "status_code": 200,
                    "error": None
                }
            elif url == "https://travis-ci.org/user/repo":
                return {
                    "is_accessible": False,
                    "status_code": 404,
                    "error": None
                }
            elif url == "not-a-valid-url":
                return {
                    "is_accessible": False,
                    "status_code": None,
                    "error": "Invalid URL format"
                }
            else:
                return {
                    "is_accessible": False,
                    "status_code": 500,
                    "error": "Server error"
                }

        with patch('rsmetacheck.scripts.pitfalls.p015.check_ci_url_status',
                   side_effect=mock_check_ci_url_status):
            result = detect_ci_404_pitfall(somef_data, file_name)

            assert result["has_pitfall"] == expected_has_pitfall
            assert result["file_name"] == file_name
            assert result["ci_url"] == expected_ci_url
            assert result["status_code"] == expected_status_code

    def test_result_structure(self):
        """Test that result always has the expected structure"""
        somef_data = {}
        result = detect_ci_404_pitfall(somef_data, "test.json")

        assert "has_pitfall" in result
        assert "file_name" in result
        assert "ci_url" in result
        assert "source" in result
        assert "status_code" in result
        assert "error" in result

    def test_codemeta_lowercase_source(self):
        """Test detection with lowercase codemeta in source"""
        somef_data = {
            "continuous_integration": [{
                "source": "repository/codemeta.json",
                "technique": "code_parser",
                "result": {"value": "https://broken-ci.com/build"}
            }]
        }

        with patch('rsmetacheck.scripts.pitfalls.p015.check_ci_url_status',
                   return_value={"is_accessible": False, "status_code": 404, "error": None}):
            result = detect_ci_404_pitfall(somef_data, "test.json")
            assert result["has_pitfall"] is True

    def test_stops_at_first_inaccessible(self):
        """Test that function stops after finding first inaccessible CI URL"""
        somef_data = {
            "continuous_integration": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "https://first-ci.com"}
                },
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "https://second-ci.com"}
                }
            ]
        }

        def mock_check(url, timeout=10):
            return {
                "is_accessible": False,
                "status_code": 404,
                "error": None
            }

        with patch('rsmetacheck.scripts.pitfalls.p015.check_ci_url_status',
                   side_effect=mock_check) as mock:
            result = detect_ci_404_pitfall(somef_data, "test.json")

            assert result["has_pitfall"] is True
            assert result["ci_url"] == "https://first-ci.com"
            assert mock.call_count == 1  # Should stop after first

    def test_multiple_ci_sources_mixed(self):
        """Test with multiple CI sources, some from codemeta, some not"""
        somef_data = {
            "continuous_integration": [
                {
                    "source": "README.md",
                    "technique": "header_analysis",
                    "result": {"value": "https://ci-from-readme.com"}
                },
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "https://ci-from-codemeta.com"}
                }
            ]
        }

        with patch('rsmetacheck.scripts.pitfalls.p015.check_ci_url_status',
                   return_value={"is_accessible": False, "status_code": 404, "error": None}):
            result = detect_ci_404_pitfall(somef_data, "test.json")

            assert result["has_pitfall"] is True
            assert result["ci_url"] == "https://ci-from-codemeta.com"

    @pytest.mark.parametrize("status_code", [401, 403, 500, 502, 503])
    def test_various_error_status_codes(self, status_code):
        """Test that transient/server errors are NOT flagged (inconclusive)"""
        somef_data = {
            "continuous_integration": [{
                "source": "repository/codemeta.json",
                "technique": "code_parser",
                "result": {"value": "https://ci.example.com"}
            }]
        }

        with patch('rsmetacheck.scripts.pitfalls.p015.check_ci_url_status',
                   return_value={"is_accessible": False, "status_code": status_code, "error": None}):
            result = detect_ci_404_pitfall(somef_data, "test.json")

            assert result["has_pitfall"] is False
            assert result["status_code"] is None
            assert result["ci_url"] is None