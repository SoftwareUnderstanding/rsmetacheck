import pytest
from unittest.mock import patch
from rsmetacheck.scripts.pitfalls.p011 import (
    is_valid_issue_tracker_format,
    detect_issue_tracker_format_pitfall
)


class TestIsValidIssueTrackerFormat:
    """Test suite for is_valid_issue_tracker_format function"""

    def test_empty_or_none_url(self):
        assert is_valid_issue_tracker_format("") is False
        assert is_valid_issue_tracker_format(None) is False

    def test_valid_github_issues_url(self):
        assert is_valid_issue_tracker_format("https://github.com/user/repo/issues") is True

    def test_valid_gitlab_issues_url(self):
        assert is_valid_issue_tracker_format("https://gitlab.com/user/repo/-/issues") is True

    def test_valid_bitbucket_issues_url(self):
        assert is_valid_issue_tracker_format("https://bitbucket.org/user/repo/issues") is True

    def test_valid_self_hosted_issues_url(self):
        url = "https://gvipers.imt-nord-europe.fr/m3tal/csdvp-evolutionary-algorithm-optimization/issues"
        assert is_valid_issue_tracker_format(url) is True

    def test_valid_jira_issues_url(self):
        assert is_valid_issue_tracker_format("https://example.com/jira/projects/PROJ/issues") is True

    def test_valid_tickets_url(self):
        assert is_valid_issue_tracker_format("https://trac.example.com/project/tickets") is True

    def test_valid_issues_with_subpath(self):
        assert is_valid_issue_tracker_format("https://example.com/repo/issues/123") is True

    def test_invalid_no_scheme(self):
        assert is_valid_issue_tracker_format("github.com/user/repo/issues") is False

    def test_invalid_ftp_scheme(self):
        assert is_valid_issue_tracker_format("ftp://example.com/repo/issues") is False

    def test_invalid_no_netloc(self):
        assert is_valid_issue_tracker_format("https:///path/issues") is False

    def test_invalid_no_path(self):
        assert is_valid_issue_tracker_format("https://example.com") is False

    def test_invalid_root_path_only(self):
        assert is_valid_issue_tracker_format("https://example.com/") is False

    def test_invalid_path_without_issues(self):
        assert is_valid_issue_tracker_format("https://example.com/user/repo") is False

    def test_invalid_homepage_url(self):
        assert is_valid_issue_tracker_format("https://example.com/user/repo/wiki") is False

    def test_whitespace_handling(self):
        assert is_valid_issue_tracker_format("  https://example.com/repo/issues  ") is True

    def test_case_insensitive_path(self):
        assert is_valid_issue_tracker_format("https://example.com/repo/ISSUES") is True
        assert is_valid_issue_tracker_format("https://example.com/repo/Issues") is True


class TestDetectIssueTrackerFormatPitfall:
    """Test suite for detect_issue_tracker_format_pitfall function"""

    @pytest.mark.parametrize(
        "somef_data,file_name,expected_has_pitfall,expected_url", [
            # No issue_tracker key
            ({}, "test_repo.json", False, None),
            # issue_tracker not a list
            ({"issue_tracker": "https://example.com/issues"}, "test_repo.json", False, None),
            # Empty issue_tracker list
            ({"issue_tracker": []}, "test_repo.json", False, None),
            # Missing result key
            ({"issue_tracker": [{
                "source": "repository/codemeta.json",
                "technique": "code_parser"
            }]}, "test_repo.json", False, None),
            # Missing value in result
            ({"issue_tracker": [{
                "source": "repository/codemeta.json",
                "technique": "code_parser",
                "result": {}
            }]}, "test_repo.json", False, None),
            # Non-codemeta source (should not trigger)
            ({"issue_tracker": [{
                "source": "README.md",
                "technique": "header_analysis",
                "result": {"value": "https://example.com/issues"}
            }]}, "test_repo.json", False, None),
        ])
    def test_detect_issue_tracker_scenarios_without_url_check(
            self, somef_data, file_name, expected_has_pitfall, expected_url):
        """Test various scenarios without URL format check"""
        result = detect_issue_tracker_format_pitfall(somef_data, file_name)
        assert result["has_pitfall"] == expected_has_pitfall
        assert result["file_name"] == file_name
        assert result["issue_url"] == expected_url

    def test_valid_format_no_pitfall(self):
        """Test that valid issue tracker format doesn't trigger pitfall"""
        somef_data = {
            "issue_tracker": [{
                "source": "repository/codemeta.json",
                "technique": "code_parser",
                "result": {"value": "https://github.com/user/repo/issues"}
            }]
        }
        with patch('rsmetacheck.scripts.pitfalls.p011._is_unreachable',
                   return_value={"status_code": 200, "error": None, "verdict": "accessible"}):
            result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
        assert result["has_pitfall"] is False

    def test_invalid_format_has_pitfall(self):
        """Test that invalid URL format triggers pitfall"""
        somef_data = {
            "issue_tracker": [{
                "source": "repository/codemeta.json",
                "technique": "code_parser",
                "result": {"value": "https://broken.example.com/repo/wiki"}
            }]
        }
        result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
        assert result["has_pitfall"] is True
        assert result["issue_url"] == "https://broken.example.com/repo/wiki"
        assert result["format_violation"] == "URL does not match recognized issue tracker format"

    def test_result_structure(self):
        """Test that result always has the expected structure"""
        somef_data = {}
        result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
        assert "has_pitfall" in result
        assert "file_name" in result
        assert "issue_url" in result
        assert "source" in result
        assert "format_violation" in result

    def test_case_insensitive_codemeta_matching(self):
        """Test case insensitive matching for codemeta.json"""
        test_sources = [
            "codemeta.json",
            "repository/codemeta.json",
            "CODEMETA.JSON",
            "CodeMeta.json",
        ]
        for source in test_sources:
            somef_data = {
                "issue_tracker": [{
                    "source": source,
                    "technique": "code_parser",
                    "result": {"value": "https://broken.example.com/repo/wiki"}
                }]
            }
            result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
            assert result["has_pitfall"] is True, f"Failed for source: {source}"

    def test_code_parser_with_codemeta_in_source(self):
        """Test detection with code_parser technique and codemeta in source"""
        somef_data = {
            "issue_tracker": [{
                "source": "CodeMeta file",
                "technique": "code_parser",
                "result": {"value": "https://broken.example.com/repo/wiki"}
            }]
        }
        result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
        assert result["has_pitfall"] is True

    def test_stops_at_first_match(self):
        """Test that function stops after finding first invalid URL"""
        somef_data = {
            "issue_tracker": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "https://broken1.example.com/repo/wiki"}
                },
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "https://broken2.example.com/repo/wiki"}
                }
            ]
        }
        result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
        assert result["has_pitfall"] is True
        assert result["issue_url"] == "https://broken1.example.com/repo/wiki"

    def test_multiple_entries_first_non_codemeta(self):
        """Test with multiple entries where first is non-codemeta"""
        somef_data = {
            "issue_tracker": [
                {
                    "source": "README.md",
                    "technique": "header_analysis",
                    "result": {"value": "https://example.com/repo/wiki"}
                },
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "https://broken.example.com/repo/wiki"}
                }
            ]
        }
        result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
        assert result["has_pitfall"] is True
        assert result["issue_url"] == "https://broken.example.com/repo/wiki"

    def test_various_invalid_urls_detected(self):
        """Test that various invalid URL formats are detected"""
        test_urls = [
            "not-a-url",
            "ftp://example.com/repo/issues",
            "https://example.com",
            "https://github.com/user/repo",
        ]
        for url in test_urls:
            somef_data = {
                "issue_tracker": [{
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": url}
                }]
            }
            result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
            assert result["has_pitfall"] is True, f"Failed for URL: {url}"
            assert result["issue_url"] == url

    def test_various_valid_urls_not_detected(self):
        """Test that various valid issue tracker URLs are NOT flagged"""
        test_urls = [
            "https://github.com/user/repo/issues",
            "https://gitlab.com/user/repo/-/issues",
            "https://bitbucket.org/user/repo/issues",
            "https://example.com/jira/projects/PROJ/issues",
            "https://gvipers.imt-nord-europe.fr/m3tal/csdvp-evolutionary-algorithm-optimization/issues",
            "https://trac.example.com/project/tickets",
        ]
        for url in test_urls:
            somef_data = {
                "issue_tracker": [{
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": url}
                }]
            }
            with patch('rsmetacheck.scripts.pitfalls.p011._is_unreachable',
                       return_value={"status_code": 200, "error": None, "verdict": "accessible"}):
                result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
            assert result["has_pitfall"] is False, f"URL should be valid: {url}"

    def test_wrong_technique_still_matches_source(self):
        """Test that source matching still triggers regardless of technique"""
        somef_data = {
            "issue_tracker": [{
                "source": "repository/codemeta.json",
                "technique": "github_api",
                "result": {"value": "https://broken.example.com/repo/wiki"}
            }]
        }
        result = detect_issue_tracker_format_pitfall(somef_data, "test.json")
        assert result["has_pitfall"] is True
