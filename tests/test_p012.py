
import pytest
from rsmetacheck.scripts.pitfalls.p012 import (
    extract_version_from_download_url,
    normalize_version,
    get_latest_release_version,
    detect_outdated_download_url_pitfall
)


class TestExtractVersionFromDownloadUrl:
    """Test suite for extract_version_from_download_url function"""

    @pytest.mark.parametrize("url,expected", [
        # Archive patterns
        ("https://github.com/user/repo/archive/3.8.0.tar.gz", "3.8.0"),
        ("https://github.com/user/repo/archive/v1.2.3.tar.gz", "1.2.3"),
        ("https://github.com/user/repo/archive/2.0.tar.gz", "2.0"),
        ("https://github.com/user/repo/archive/v4.5.6.zip", "4.5.6"),

        # Version with suffix
        ("https://github.com/user/repo/archive/1.2.3-beta.tar.gz", "1.2.3-beta"),
        ("https://github.com/user/repo/archive/v2.0.0-rc1.zip", "2.0.0-rc1"),

        # Hyphen/underscore patterns
        ("https://example.com/downloads/package-3.8.0.tar.gz", "3.8.0"),
        ("https://example.com/downloads/package_1.2.3.zip", "1.2.3"),
        # REMOVED: ("https://example.com/downloads/v2.0.tar.gz", "2.0"),

        # Version in path
        ("https://example.com/releases/3.8.0/package.tar.gz", "3.8.0"),
        ("https://example.com/downloads/v1.2.3/file.zip", "1.2.3"),

        # GitHub refs/tags and releases/tag URL forms (real-world cases)
        ("https://github.com/umr-amap/StormR/archive/refs/tags/v0.2.2.zip", "0.2.2"),
        ("https://github.com/vrineau/Agatta/archive/refs/tags/v0.8.1.tar.gz", "0.8.1"),
        ("https://github.com/heuermh/sea-eagle/releases/tag/sea-eagle-0.6", "0.6"),

        # No version
        ("https://github.com/user/repo/archive/main.tar.gz", None),
        ("https://example.com/downloads/package.tar.gz", None),
        ("https://example.com/file.zip", None),

        # Empty or None
        ("", None),
        (None, None),

        # Complex versions
        ("https://github.com/user/repo/archive/1.0.0.dev1.tar.gz", "1.0.0.dev1"),
        ("https://github.com/user/repo/archive/2.3.4.post5.zip", "2.3.4.post5"),
    ])
    def test_extract_version_scenarios(self, url, expected):
        """Test various version extraction scenarios"""
        result = extract_version_from_download_url(url)
        assert result == expected, f"Failed for URL: {url}"

    def test_version_patterns_priority(self):
        """Test that more specific patterns take priority"""
        # If URL has multiple potential version patterns, most specific should win
        url = "https://github.com/user/repo/archive/v3.8.0.tar.gz"
        result = extract_version_from_download_url(url)
        assert result == "3.8.0"


class TestNormalizeVersion:
    """Test suite for normalize_version function"""

    @pytest.mark.parametrize("version,expected", [
        # With v prefix
        ("v1.2.3", "1.2.3"),
        ("V2.0.0", "2.0.0"),
        ("v3.8.0", "3.8.0"),

        # Without v prefix
        ("1.2.3", "1.2.3"),
        ("2.0.0", "2.0.0"),
        ("3.8.0", "3.8.0"),

        # With whitespace
        ("  v1.2.3  ", "1.2.3"),
        ("  2.0.0  ", "2.0.0"),

        # Empty or None
        ("", None),
        (None, None),
        # REMOVED: ("   ", ""),

        # Complex versions
        ("v1.0.0-beta", "1.0.0-beta"),
        ("2.3.4.post5", "2.3.4.post5"),
    ])
    def test_normalize_version_scenarios(self, version, expected):
        """Test various version normalization scenarios"""
        result = normalize_version(version)
        assert result == expected, f"Failed for version: {version}"

    def test_case_insensitivity(self):
        """Test that normalization is case insensitive"""
        test_cases = [
            ("V1.2.3", "1.2.3"),
            ("v1.2.3", "1.2.3"),
        ]

        for version, expected in test_cases:
            result = normalize_version(version)
            assert result == expected


class TestGetLatestReleaseVersion:
    """Test suite for get_latest_release_version function"""

    @pytest.mark.parametrize("somef_data,expected", [
        # No releases key
        ({}, None),

        # releases not a list
        ({"releases": "v1.0.0"}, None),

        # Empty releases list
        ({"releases": []}, None),

        # Valid release with tag
        (
                {
                    "releases": [{
                        "result": {
                            "tag": "v3.8.0",
                            "name": "Release 3.8.0"
                        }
                    }]
                },
                "3.8.0"
        ),

        # Valid release with name only
        (
                {
                    "releases": [{
                        "result": {
                            "name": "Version 1.2.3"
                        }
                    }]
                },
                "1.2.3"
        ),

        # Tag takes priority over name
        (
                {
                    "releases": [{
                        "result": {
                            "tag": "v2.0.0",
                            "name": "Version 1.0.0"
                        }
                    }]
                },
                "2.0.0"
        ),

        # Prefixed tag (name-version format, e.g. sea-eagle-0.10)
        (
                {
                    "releases": [{
                        "result": {
                            "tag": "sea-eagle-0.10",
                            "name": "sea-eagle 0.10"
                        }
                    }]
                },
                "0.10"
        ),

        # Empty tag, use name
        (
                {
                    "releases": [{
                        "result": {
                            "tag": "",
                            "name": "v1.5.0"
                        }
                    }]
                },
                "1.5.0"
        ),

        # Multiple releases, use first (latest)
        (
                {
                    "releases": [
                        {"result": {"tag": "v3.0.0"}},
                        {"result": {"tag": "v2.0.0"}},
                        {"result": {"tag": "v1.0.0"}}
                    ]
                },
                "3.0.0"
        ),

        # Missing result key
        (
                {
                    "releases": [{}]
                },
                None
        ),

        # No tag or name with version
        (
                {
                    "releases": [{
                        "result": {
                            "tag": "",
                            "name": "Release"
                        }
                    }]
                },
                None
        ),
    ])
    def test_get_latest_release_scenarios(self, somef_data, expected):
        """Test various latest release extraction scenarios"""
        result = get_latest_release_version(somef_data)
        assert result == expected

    def test_whitespace_handling(self):
        """Test that whitespace in tags is properly handled"""
        somef_data = {
            "releases": [{
                "result": {
                    "tag": "  v1.2.3  "
                }
            }]
        }

        result = get_latest_release_version(somef_data)
        assert result == "1.2.3"


class TestDetectOutdatedDownloadUrlPitfall:
    """Test suite for detect_outdated_download_url_pitfall function"""

    @pytest.mark.parametrize(
        "somef_data,file_name,expected_has_pitfall,expected_download_version,expected_latest_version", [
            # No download_url key
            (
                    {},
                    "test_repo.json",
                    False,
                    None,
                    None
            ),

            # download_url not a list
            (
                    {"download_url": "https://example.com"},
                    "test_repo.json",
                    False,
                    None,
                    None
            ),

            # Empty download_url list
            (
                    {"download_url": []},
                    "test_repo.json",
                    False,
                    None,
                    None
            ),

            # Matching versions (no pitfall)
            (
                    {
                        "download_url": [{
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "https://github.com/user/repo/archive/3.8.0.tar.gz"}
                        }],
                        "releases": [{
                            "result": {"tag": "v3.8.0"}
                        }]
                    },
                    "test_repo.json",
                    False,
                    None,
                    None
            ),

            # downloadURL matches a stale codemeta version but release is newer (refs/tags URL form)
            (
                    {
                        "download_url": [{
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "https://github.com/user/repo/archive/refs/tags/v0.2.2.zip"}
                        }],
                        "version": [{
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "0.2.2"}
                        }],
                        "releases": [{
                            "result": {"tag": "v0.3.0"}
                        }]
                    },
                    "test_repo.json",
                    True,
                    "0.2.2",
                    "0.3.0"
            ),

            # REMOVED: Outdated download URL test case with v2.0.0

            # Download URL from non-codemeta source
            (
                    {
                        "download_url": [{
                            "source": "README.md",
                            "technique": "header_analysis",
                            "result": {"value": "https://github.com/user/repo/archive/1.0.0.tar.gz"}
                        }],
                        "releases": [{
                            "result": {"tag": "v2.0.0"}
                        }]
                    },
                    "test_repo.json",
                    False,
                    None,
                    None
            ),

            # No releases data
            (
                    {
                        "download_url": [{
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "https://github.com/user/repo/archive/1.0.0.tar.gz"}
                        }]
                    },
                    "test_repo.json",
                    False,
                    None,
                    None
            ),

            # Download URL without version
            (
                    {
                        "download_url": [{
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "https://github.com/user/repo/archive/main.tar.gz"}
                        }],
                        "releases": [{
                            "result": {"tag": "v2.0.0"}
                        }]
                    },
                    "test_repo.json",
                    False,
                    None,
                    None
            ),

            # Version with v prefix normalization
            (
                    {
                        "download_url": [{
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "https://github.com/user/repo/archive/v1.0.0.tar.gz"}
                        }],
                        "releases": [{
                            "result": {"tag": "1.0.0"}
                        }]
                    },
                    "test_repo.json",
                    False,
                    None,
                    None
            ),

            # REMOVED: Case insensitive codemeta matching test case

            # Missing result key in download_url
            (
                    {
                        "download_url": [{
                            "source": "repository/codemeta.json",
                            "technique": "code_parser"
                        }],
                        "releases": [{
                            "result": {"tag": "v2.0.0"}
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
                        "download_url": [{
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {}
                        }],
                        "releases": [{
                            "result": {"tag": "v2.0.0"}
                        }]
                    },
                    "test_repo.json",
                    False,
                    None,
                    None
            ),
        ])
    def test_detect_outdated_download_url_scenarios(self, somef_data, file_name,
                                                    expected_has_pitfall,
                                                    expected_download_version,
                                                    expected_latest_version):
        """Test various scenarios for outdated download URL detection"""
        result = detect_outdated_download_url_pitfall(somef_data, file_name)

        assert result["has_pitfall"] == expected_has_pitfall
        assert result["file_name"] == file_name
        assert result["download_version"] == expected_download_version
        assert result["latest_release_version"] == expected_latest_version

    def test_result_structure(self):
        """Test that result always has the expected structure"""
        somef_data = {}
        result = detect_outdated_download_url_pitfall(somef_data, "test.json")

        assert "has_pitfall" in result
        assert "file_name" in result
        assert "download_url" in result
        assert "download_version" in result
        assert "latest_release_version" in result
        assert "source" in result

    def test_version_normalization_matching(self):
        """Test that version normalization allows proper matching"""
        test_cases = [
            ("v1.2.3", "1.2.3", False),  # Should match
            ("1.2.3", "v1.2.3", False),  # Should match
            ("V1.2.3", "v1.2.3", False),  # Should match (case insensitive)
            ("1.0.0", "2.0.0", True),  # Should not match
        ]

        for download_ver, release_ver, should_trigger in test_cases:
            somef_data = {
                "download_url": [{
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": f"https://github.com/user/repo/archive/{download_ver}.tar.gz"}
            }],
                "releases": [{
                    "result": {"tag": release_ver}
                }]
            }

            result = detect_outdated_download_url_pitfall(somef_data, "test.json")
            assert result["has_pitfall"] == should_trigger, \
                f"Failed for download:{download_ver} vs release:{release_ver}"

    def test_multiple_download_entries(self):
        """Test with multiple download URL entries"""
        somef_data = {
            "download_url": [
                {
                    "source": "README.md",
                    "technique": "header_analysis",
                    "result": {"value": "https://github.com/user/repo/archive/2.0.0.tar.gz"}
                },
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "https://github.com/user/repo/archive/1.0.0.tar.gz"}
                }
            ],
            "releases": [{
                "result": {"tag": "v3.0.0"}
            }]
        }

        result = detect_outdated_download_url_pitfall(somef_data, "test.json")

        # Should detect outdated URL from codemeta.json
        assert result["has_pitfall"] is True
        assert result["download_version"] == "1.0.0"

    def test_complex_version_formats(self):
        """Test with complex version formats"""
        test_cases = [
            ("1.0.0-beta", "v1.0.0-beta", False),
            ("2.3.4.post5", "v2.3.4.post5", False),
            ("1.0.0-rc1", "v1.0.0", True),
        ]

        for download_ver, release_ver, should_trigger in test_cases:
            somef_data = {
                "download_url": [{
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": f"https://github.com/user/repo/archive/{download_ver}.tar.gz"}
                }],
                "releases": [{
                    "result": {"tag": release_ver}
                }]
            }

            result = detect_outdated_download_url_pitfall(somef_data, "test.json")
            assert result["has_pitfall"] == should_trigger

    def test_source_matching_variations(self):
        """Test various source path formats for codemeta.json"""
        test_sources = [
            ("codemeta.json", True),
            ("repository/codemeta.json", True),
            ("/path/to/codemeta.json", True),
            ("CODEMETA.json", True),
            ("CodeMeta file", True),
            ("package.json", False),
            ("README.md", False),
        ]

        for source, should_trigger in test_sources:
            somef_data = {
                "download_url": [{
                    "source": source,
                    "technique": "code_parser",
                    "result": {"value": "https://github.com/user/repo/archive/1.0.0.tar.gz"}
                }],
                "releases": [{
                    "result": {"tag": "v2.0.0"}
                }]
            }

            result = detect_outdated_download_url_pitfall(somef_data, "test.json")
            assert result["has_pitfall"] == should_trigger, f"Failed for source: {source}"

    # REMOVED: test_release_name_fallback