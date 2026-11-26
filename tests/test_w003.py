import pytest
from rsmetacheck.scripts.warnings.w003 import detect_dual_license_missing_codemeta_pitfall


class TestDetectDualLicenseMissingCodemetaPitfall:
    """Test suite for detect_dual_license_missing_codemeta_pitfall function"""

    @pytest.mark.parametrize(
        "somef_data,file_name,expected_has_warning,expected_dual_indicator,expected_codemeta_count",
        [
            # No license key
            (
                {},
                "test_repo.json",
                False,
                False,
                0
            ),

            # license not a list
            (
                {"license": "MIT"},
                "test_repo.json",
                False,
                False,
                0
            ),

            # Empty license list
            (
                {"license": []},
                "test_repo.json",
                False,
                False,
                0
            ),

            # Single license in codemeta, no dual license indicator (no pitfall)
            (
                {
                    "license": [{
                        "source": "repository/codemeta.json",
                        "technique": "code_parser",
                        "result": {"value": "MIT"}
                    }]
                },
                "test_repo.json",
                False,
                False,
                1
            ),

            # Dual license indicator in README, only one license in codemeta (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "dual-licensed under MIT and Apache-2.0"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # Dual license indicator, no codemeta license (pitfall)
            (
                {
                    "license": [{
                        "source": "README.md",
                        "result": {"value": "This project is dual licensed"}
                    }]
                },
                "test_repo.json",
                True,
                True,
                0
            ),

            # Dual license indicator, two licenses in codemeta (no pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "Apache-2.0"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "dual-licensed"}
                        }
                    ]
                },
                "test_repo.json",
                False,
                True,
                2
            ),

            # Multiple licenses pattern (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "LICENSE.md",
                            "result": {"value": "multiple licenses available"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # "Licensed under X and Y" pattern (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "Licensed under MIT and Apache"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # "Choose license" pattern (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "You may choose your license to use"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # "Either license" pattern (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "either MIT or Apache license"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # "License options" pattern (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "license options: MIT or GPL"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # "Available under licenses" pattern (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "available under multiple licenses"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # Case insensitive pattern matching (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "DUAL-LICENSED UNDER MIT AND APACHE"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # Different spelling: "licence" (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "dual licence"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # Pattern with hyphen variation (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "dual licensed"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),

            # No dual license indicator, single codemeta license (no pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "MIT License"}
                        }
                    ]
                },
                "test_repo.json",
                False,
                False,
                1
            ),

            # Non-string license value (no crash)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": 12345}  # Non-string value
                        }
                    ]
                },
                "test_repo.json",
                False,
                False,
                1
            ),

            # Numbered list pattern (pitfall)
            (
                {
                    "license": [
                        {
                            "source": "repository/codemeta.json",
                            "technique": "code_parser",
                            "result": {"value": "MIT"}
                        },
                        {
                            "source": "README.md",
                            "result": {"value": "1. MIT License\n2. Apache License"}
                        }
                    ]
                },
                "test_repo.json",
                True,
                True,
                1
            ),
        ])
    def test_detect_pitfall_scenarios(self, somef_data, file_name, expected_has_warning,
                                      expected_dual_indicator, expected_codemeta_count):
        """Test various dual license missing codemeta scenarios"""
        result = detect_dual_license_missing_codemeta_pitfall(somef_data, file_name)

        assert result["has_warning"] == expected_has_warning
        assert result["file_name"] == file_name
        assert result["has_dual_license_indicator"] == expected_dual_indicator
        assert result["codemeta_license_count"] == expected_codemeta_count

        if expected_dual_indicator:
            assert result["dual_license_source"] is not None

    def test_result_structure(self):
        """Test that result always has the expected structure"""
        somef_data = {}
        result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")

        assert "has_warning" in result
        assert "file_name" in result
        assert "has_dual_license_indicator" in result
        assert "codemeta_license_count" in result
        assert "dual_license_source" in result

    def test_dual_license_source_captured(self):
        """Test that dual license source is properly captured"""
        somef_data = {
            "license": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "MIT"}
                },
                {
                    "source": "README.md",
                    "result": {"value": "dual licensed"}
                }
            ]
        }

        result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")
        assert result["dual_license_source"] == "README.md"

    def test_multiple_codemeta_licenses_no_pitfall(self):
        """Test that multiple codemeta licenses prevent pitfall"""
        somef_data = {
            "license": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "MIT"}
                },
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "Apache-2.0"}
                },
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "GPL-3.0"}
                },
                {
                    "source": "README.md",
                    "result": {"value": "dual licensed"}
                }
            ]
        }

        result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")
        assert result["has_warning"] == False
        assert result["codemeta_license_count"] == 3

    def test_all_dual_license_patterns(self):
        """Test that all dual license patterns are detected"""
        patterns_to_test = [
            "dual-licensed",
            "dual licensed",
            "dually licensed",
            "multiple licenses",
            "multiple licence",
            "licensed under MIT and Apache",
            "licensed under GPL or MIT",
            "choose your license",
            "either MIT or Apache license",
            "available under multiple licenses"
        ]

        for pattern in patterns_to_test:
            somef_data = {
                "license": [
                    {
                        "source": "repository/codemeta.json",
                        "technique": "code_parser",
                        "result": {"value": "MIT"}
                    },
                    {
                        "source": "README.md",
                        "result": {"value": pattern}
                    }
                ]
            }

            result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")
            assert result["has_dual_license_indicator"] == True, f"Pattern '{pattern}' not detected"
            assert result["has_warning"] == True

    def test_non_codemeta_technique_not_counted(self):
        """Test that non-code_parser technique doesn't count as codemeta license"""
        somef_data = {
            "license": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "header_analysis",  # Not code_parser
                    "result": {"value": "MIT"}
                },
                {
                    "source": "README.md",
                    "result": {"value": "dual licensed"}
                }
            ]
        }

        result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")
        assert result["codemeta_license_count"] == 0
        assert result["has_warning"] == True

    def test_first_dual_license_pattern_wins(self):
        """Test that first matching pattern sets the source"""
        somef_data = {
            "license": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "MIT"}
                },
                {
                    "source": "README.md",
                    "result": {"value": "dual licensed"}
                },
                {
                    "source": "LICENSE.txt",
                    "result": {"value": "multiple licenses"}
                }
            ]
        }

        result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")
        assert result["dual_license_source"] == "README.md"

    def test_missing_result_or_value_handled(self):
        """Test that entries without result or value don't cause errors"""
        somef_data = {
            "license": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "MIT"}
                },
                {
                    "source": "README.md",
                    # Missing result
                },
                {
                    "source": "LICENSE.md",
                    "result": {}  # Missing value
                }
            ]
        }

        result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")
        assert result["has_warning"] == False
        assert result["codemeta_license_count"] == 1

    def test_edge_case_exactly_one_codemeta_license(self):
        """Test boundary condition with exactly 1 codemeta license"""
        somef_data = {
            "license": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "MIT"}
                },
                {
                    "source": "README.md",
                    "result": {"value": "dual licensed"}
                }
            ]
        }

        result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")
        assert result["codemeta_license_count"] == 1
        assert result["has_warning"] == True

    def test_edge_case_exactly_two_codemeta_licenses(self):
        """Test boundary condition with exactly 2 codemeta licenses"""
        somef_data = {
            "license": [
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "MIT"}
                },
                {
                    "source": "repository/codemeta.json",
                    "technique": "code_parser",
                    "result": {"value": "Apache-2.0"}
                },
                {
                    "source": "README.md",
                    "result": {"value": "dual licensed"}
                }
            ]
        }

        result = detect_dual_license_missing_codemeta_pitfall(somef_data, "test.json")
        assert result["codemeta_license_count"] == 2
        assert result["has_warning"] == False