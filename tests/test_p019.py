import pytest
from rsmetacheck.scripts.pitfalls.p019 import (
    get_author_identifier,
    extract_authors_from_somef,
    find_author_count_inconsistencies,
    detect_inconsistent_author_count,
    _declared_organization,
    _codemeta_persons,
)


class TestGetAuthorIdentifier:
    """Test suite for get_author_identifier function"""

    @pytest.mark.parametrize("author,expected", [
        # String authors
        ("John Doe", "John Doe"),
        ("  Jane Smith  ", "Jane Smith"),
        ("", ""),
        
        # Dict authors with name field
        ({"name": "Alice Johnson"}, "Alice Johnson"),
        ({"name": "  Bob Wilson  "}, "Bob Wilson"),
        ({"name": ""}, ""),
        ({"name": None}, "None"),
        
        # Dict authors with value field
        ({"value": "Charlie Brown"}, "Charlie Brown"),
        ({"value": "  Diana Prince  "}, "Diana Prince"),
        ({"value": ""}, ""),
        
        # Dict authors with email field
        ({"email": "test@example.com"}, "test@example.com"),
        ({"email": "  user@domain.org  "}, "user@domain.org"),
        
        # Dict with multiple fields (name takes precedence)
        ({"name": "Name Field", "value": "Value Field", "email": "email@test.com"}, "Name Field"),
        ({"value": "Value Field", "email": "email@test.com"}, "Value Field"),
        
        # Dict with no standard fields
        ({"other": "data"}, "{'other': 'data'}"),
        ({}, "{}"),
        
        # Non-string, non-dict types
        (123, "123"),
        (None, "None"),
        ([1, 2, 3], "[1, 2, 3]"),
        (True, "True"),
    ])
    def test_get_author_identifier_scenarios(self, author, expected):
        """Test various author identifier extraction scenarios"""
        assert get_author_identifier(author) == expected


class TestExtractAuthorsFromSomef:
    """Test suite for extract_authors_from_somef function"""

    def test_no_author_key(self):
        """Test with no author key in SoMEF data"""
        assert extract_authors_from_somef({}) == []

    def test_author_not_list(self):
        """Test when author is not a list"""
        assert extract_authors_from_somef({"author": "John Doe"}) == []
        assert extract_authors_from_somef({"author": {}}) == []

    def test_empty_author_list(self):
        """Test with empty author list"""
        assert extract_authors_from_somef({"author": []}) == []

    def test_single_author_as_string(self):
        """Test single author as string in result"""
        somef_data = {
            "author": [{
                "source": "repository/codemeta.json",
                "result": "John Doe"
            }]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 1
        assert result[0]["author_count"] == 1
        assert result[0]["authors"] == ["John Doe"]
        assert result[0]["source_file"] == "codemeta.json"

    def test_single_author_as_dict(self):
        """Test single author as dict in result"""
        somef_data = {
            "author": [{
                "source": "repository/CITATION.cff",
                "result": {"name": "Jane Smith"}
            }]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 1
        assert result[0]["author_count"] == 1
        assert result[0]["authors"] == ["Jane Smith"]
        assert result[0]["source_file"] == "CITATION.cff"

    def test_multiple_authors_as_list(self):
        """Test multiple authors as list in result"""
        somef_data = {
            "author": [{
                "source": "repository/package.json",
                "result": [
                    {"name": "Author One"},
                    {"name": "Author Two"},
                    {"name": "Author Three"}
                ]
            }]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 1
        assert result[0]["author_count"] == 3
        assert result[0]["authors"] == ["Author One", "Author Two", "Author Three"]
        assert result[0]["source_file"] == "package.json"

    def test_authors_from_different_sources(self):
        """Test extracting authors from multiple sources"""
        somef_data = {
            "author": [
                {
                    "source": "repository/codemeta.json",
                    "result": [{"name": "Author A"}, {"name": "Author B"}]
                },
                {
                    "source": "repository/CITATION.cff",
                    "result": [{"name": "Author A"}]
                },
                {
                    "source": "repository/package.json",
                    "result": [{"name": "Author A"}, {"name": "Author B"}, {"name": "Author C"}]
                }
            ]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 3
        assert result[0]["author_count"] == 2
        assert result[1]["author_count"] == 1
        assert result[2]["author_count"] == 3

    def test_missing_source_field(self):
        """Test entry without source field"""
        somef_data = {
            "author": [{
                "result": [{"name": "Author"}]
            }]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 0

    def test_missing_result_field(self):
        """Test entry without result field"""
        somef_data = {
            "author": [{
                "source": "repository/codemeta.json"
            }]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 0

    def test_empty_result_list(self):
        """Test with empty result list"""
        somef_data = {
            "author": [{
                "source": "repository/codemeta.json",
                "result": []
            }]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 0

    def test_mixed_author_formats(self):
        """Test with mixed author formats in list"""
        somef_data = {
            "author": [{
                "source": "repository/codemeta.json",
                "result": [
                    "String Author",
                    {"name": "Dict Author"},
                    {"email": "email@test.com"}
                ]
            }]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 1
        assert result[0]["author_count"] == 3
        assert "String Author" in result[0]["authors"]
        assert "Dict Author" in result[0]["authors"]
        assert "email@test.com" in result[0]["authors"]

    def test_author_count_zero_filtered_out(self):
        """Test that entries with zero authors are filtered out"""
        somef_data = {
            "author": [
                {
                    "source": "repository/codemeta.json",
                    "result": []
                },
                {
                    "source": "repository/CITATION.cff",
                    "result": [{"name": "Author"}]
                }
            ]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert len(result) == 1
        assert result[0]["source_file"] == "CITATION.cff"

    @pytest.mark.parametrize("source,expected_file", [
        ("repository/codemeta.json", "codemeta.json"),
        ("repository/CITATION.cff", "CITATION.cff"),
        ("repository/package.json", "package.json"),
        ("README.md", "README.md"),
        ("docs/AUTHORS.md", "AUTHORS.md"),
    ])
    def test_source_filename_extraction(self, source, expected_file):
        """Test that source filenames are correctly extracted"""
        somef_data = {
            "author": [{
                "source": source,
                "result": [{"name": "Author"}]
            }]
        }
        
        result = extract_authors_from_somef(somef_data)
        assert result[0]["source_file"] == expected_file


class TestFindAuthorCountInconsistencies:
    """Test suite for find_author_count_inconsistencies function"""

    def test_less_than_two_sources(self):
        """Test with less than 2 sources (no inconsistency possible)"""
        # Empty list
        has_inconsistency, inconsistencies = find_author_count_inconsistencies([])
        assert has_inconsistency is False
        assert inconsistencies == []
        
        # Single source
        sources = [{"author_count": 2, "source_file": "codemeta.json", "source": "repository/codemeta.json", "authors": ["A", "B"]}]
        has_inconsistency, inconsistencies = find_author_count_inconsistencies(sources)
        assert has_inconsistency is False
        assert inconsistencies == []

    def test_all_sources_same_count(self):
        """Test when all sources have the same author count"""
        sources = [
            {"author_count": 2, "source_file": "codemeta.json", "source": "repository/codemeta.json", "authors": ["A", "B"]},
            {"author_count": 2, "source_file": "CITATION.cff", "source": "repository/CITATION.cff", "authors": ["A", "B"]},
            {"author_count": 2, "source_file": "package.json", "source": "repository/package.json", "authors": ["A", "B"]}
        ]
        
        has_inconsistency, inconsistencies = find_author_count_inconsistencies(sources)
        assert has_inconsistency is False
        assert inconsistencies == []

    def test_two_sources_different_counts(self):
        """Test with two sources having different counts"""
        sources = [
            {"author_count": 1, "source_file": "codemeta.json", "source": "repository/codemeta.json", "authors": ["A"]},
            {"author_count": 2, "source_file": "CITATION.cff", "source": "repository/CITATION.cff", "authors": ["A", "B"]}
        ]
        
        has_inconsistency, inconsistencies = find_author_count_inconsistencies(sources)
        assert has_inconsistency is True
        assert len(inconsistencies) == 1
        assert inconsistencies[0]["fewer_count"] == 1
        assert inconsistencies[0]["more_count"] == 2
        assert inconsistencies[0]["difference"] == 1
        assert inconsistencies[0]["source_with_fewer"] == "codemeta.json"
        assert inconsistencies[0]["source_with_more"] == "CITATION.cff"

    def test_multiple_sources_different_counts(self):
        """Test with multiple sources having different counts"""
        sources = [
            {"author_count": 1, "source_file": "codemeta.json", "source": "repository/codemeta.json", "authors": ["A"]},
            {"author_count": 2, "source_file": "CITATION.cff", "source": "repository/CITATION.cff", "authors": ["A", "B"]},
            {"author_count": 3, "source_file": "package.json", "source": "repository/package.json", "authors": ["A", "B", "C"]}
        ]
        
        has_inconsistency, inconsistencies = find_author_count_inconsistencies(sources)
        assert has_inconsistency is True
        # Should have 3 inconsistencies: (1,2), (1,3), (2,3)
        assert len(inconsistencies) == 3

    def test_multiple_sources_some_matching(self):
        """Test with multiple sources where some have matching counts"""
        sources = [
            {"author_count": 2, "source_file": "codemeta.json", "source": "repository/codemeta.json", "authors": ["A", "B"]},
            {"author_count": 2, "source_file": "CITATION.cff", "source": "repository/CITATION.cff", "authors": ["A", "B"]},
            {"author_count": 3, "source_file": "package.json", "source": "repository/package.json", "authors": ["A", "B", "C"]}
        ]
        
        has_inconsistency, inconsistencies = find_author_count_inconsistencies(sources)
        assert has_inconsistency is True
        # Should have 2 inconsistencies: codemeta(2) vs package(3), CITATION(2) vs package(3)
        assert len(inconsistencies) == 2

    def test_inconsistency_details_structure(self):
        """Test that inconsistency details have correct structure"""
        sources = [
            {"author_count": 1, "source_file": "codemeta.json", "source": "repository/codemeta.json", "authors": ["Alice"]},
            {"author_count": 3, "source_file": "CITATION.cff", "source": "repository/CITATION.cff", "authors": ["Alice", "Bob", "Charlie"]}
        ]
        
        has_inconsistency, inconsistencies = find_author_count_inconsistencies(sources)
        assert has_inconsistency is True
        
        inc = inconsistencies[0]
        assert "source_with_fewer" in inc
        assert "source_with_fewer_full" in inc
        assert "fewer_count" in inc
        assert "fewer_authors" in inc
        assert "source_with_more" in inc
        assert "source_with_more_full" in inc
        assert "more_count" in inc
        assert "more_authors" in inc
        assert "difference" in inc
        
        assert inc["fewer_authors"] == ["Alice"]
        assert inc["more_authors"] == ["Alice", "Bob", "Charlie"]

    def test_zero_author_count(self):
        """Test handling of zero author count"""
        sources = [
            {"author_count": 0, "source_file": "codemeta.json", "source": "repository/codemeta.json", "authors": []},
            {"author_count": 1, "source_file": "CITATION.cff", "source": "repository/CITATION.cff", "authors": ["A"]}
        ]
        
        has_inconsistency, inconsistencies = find_author_count_inconsistencies(sources)
        assert has_inconsistency is True
        assert inconsistencies[0]["fewer_count"] == 0
        assert inconsistencies[0]["more_count"] == 1


class TestDetectInconsistentAuthorCount:
    """Test suite for detect_inconsistent_author_count function"""

    def test_no_author_data(self):
        """Test with no author data"""
        result = detect_inconsistent_author_count({}, "test_repo.json")
        
        assert result["has_warning"] is False
        assert result["file_name"] == "test_repo.json"
        assert result["author_sources"] == []
        assert result["inconsistencies"] == []
        assert result["total_sources"] == 0
        assert result["min_author_count"] == 0
        assert result["max_author_count"] == 0

    def test_single_source_no_inconsistency(self):
        """Test with single source (no inconsistency possible)"""
        somef_data = {
            "author": [{
                "source": "repository/codemeta.json",
                "result": [{"name": "Author A"}, {"name": "Author B"}]
            }]
        }
        
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        
        assert result["has_warning"] is False
        assert result["total_sources"] == 1
        assert result["min_author_count"] == 2
        assert result["max_author_count"] == 2
        assert result["inconsistencies"] == []

    def test_multiple_sources_matching_counts(self):
        """Test with multiple sources having matching counts"""
        somef_data = {
            "author": [
                {
                    "source": "repository/codemeta.json",
                    "result": [{"name": "Author A"}, {"name": "Author B"}]
                },
                {
                    "source": "repository/CITATION.cff",
                    "result": [{"name": "Author A"}, {"name": "Author B"}]
                }
            ]
        }
        
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        
        assert result["has_warning"] is False
        assert result["total_sources"] == 2
        assert result["min_author_count"] == 2
        assert result["max_author_count"] == 2

    def test_multiple_sources_different_counts(self):
        """Test with multiple sources having different counts"""
        somef_data = {
            "author": [
                {
                    "source": "repository/codemeta.json",
                    "result": [{"name": "Author A"}]
                },
                {
                    "source": "repository/CITATION.cff",
                    "result": [{"name": "Author A"}, {"name": "Author B"}]
                }
            ]
        }
        
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        
        assert result["has_warning"] is True
        assert result["total_sources"] == 2
        assert result["min_author_count"] == 1
        assert result["max_author_count"] == 2
        assert len(result["inconsistencies"]) == 1

    def test_complex_scenario_three_sources(self):
        """Test complex scenario with three sources"""
        somef_data = {
            "author": [
                {
                    "source": "repository/codemeta.json",
                    "result": [{"name": "Alice"}]
                },
                {
                    "source": "repository/CITATION.cff",
                    "result": [{"name": "Alice"}, {"name": "Bob"}]
                },
                {
                    "source": "repository/package.json",
                    "result": [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}]
                }
            ]
        }
        
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        
        assert result["has_warning"] is True
        assert result["total_sources"] == 3
        assert result["min_author_count"] == 1
        assert result["max_author_count"] == 3
        # Should have 3 inconsistencies: (1,2), (1,3), (2,3)
        assert len(result["inconsistencies"]) == 3

    def test_result_structure(self):
        """Test that result always has the expected structure"""
        somef_data = {}
        result = detect_inconsistent_author_count(somef_data, "test.json")
        
        assert "has_warning" in result
        assert "file_name" in result
        assert "author_sources" in result
        assert "inconsistencies" in result
        assert "total_sources" in result
        assert "min_author_count" in result
        assert "max_author_count" in result

    def test_author_sources_populated(self):
        """Test that author_sources contains detailed information"""
        somef_data = {
            "author": [{
                "source": "repository/codemeta.json",
                "result": [{"name": "Author A"}, {"name": "Author B"}]
            }]
        }
        
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        
        assert len(result["author_sources"]) == 1
        source = result["author_sources"][0]
        assert "source" in source
        assert "source_file" in source
        assert "author_count" in source
        assert "authors" in source

    @pytest.mark.parametrize(
        "somef_data,expected_warning,expected_min,expected_max,expected_inconsistencies", [
            # No inconsistency
            (
                {
                    "author": [
                        {"source": "repository/codemeta.json", "result": [{"name": "A"}]},
                        {"source": "repository/CITATION.cff", "result": [{"name": "A"}]}
                    ]
                },
                False,
                1,
                1,
                0
            ),
            # Simple inconsistency
            (
                {
                    "author": [
                        {"source": "repository/codemeta.json", "result": [{"name": "A"}]},
                        {"source": "repository/CITATION.cff", "result": [{"name": "A"}, {"name": "B"}]}
                    ]
                },
                True,
                1,
                2,
                1
            ),
            # Multiple inconsistencies
            (
                {
                    "author": [
                        {"source": "repository/codemeta.json", "result": [{"name": "A"}]},
                        {"source": "repository/CITATION.cff", "result": [{"name": "A"}, {"name": "B"}]},
                        {"source": "repository/package.json", "result": [{"name": "A"}, {"name": "B"}, {"name": "C"}]}
                    ]
                },
                True,
                1,
                3,
                3
            ),
        ])
    def test_detection_scenarios(self, somef_data, expected_warning, expected_min, 
                                 expected_max, expected_inconsistencies):
        """Test various detection scenarios"""
        result = detect_inconsistent_author_count(somef_data, "test.json")
        
        assert result["has_warning"] == expected_warning
        assert result["min_author_count"] == expected_min
        assert result["max_author_count"] == expected_max
        assert len(result["inconsistencies"]) == expected_inconsistencies

    def test_string_author_handling(self):
        """Test handling of string authors in result"""
        somef_data = {
            "author": [
                {
                    "source": "repository/codemeta.json",
                    "result": "Single Author"
                },
                {
                    "source": "repository/CITATION.cff",
                    "result": [{"name": "Author A"}, {"name": "Author B"}]
                }
            ]
        }
        
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        
        assert result["has_warning"] is True
        assert result["min_author_count"] == 1
        assert result["max_author_count"] == 2

    def test_dict_author_handling(self):
        """Test handling of dict author in result"""
        somef_data = {
            "author": [
                {
                    "source": "repository/codemeta.json",
                    "result": {"name": "Single Author"}
                },
                {
                    "source": "repository/CITATION.cff",
                    "result": [{"name": "Author A"}, {"name": "Author B"}]
                }
            ]
        }
        
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        
        assert result["has_warning"] is True
        assert result["min_author_count"] == 1
        assert result["max_author_count"] == 2

    def test_inconsistency_contains_author_lists(self):
        """Test that inconsistencies contain author lists"""
        somef_data = {
            "author": [
                {
                    "source": "repository/codemeta.json",
                    "result": [{"name": "Alice"}]
                },
                {
                    "source": "repository/CITATION.cff",
                    "result": [{"name": "Alice"}, {"name": "Bob"}, {"name": "Charlie"}]
                }
            ]
        }
        
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        
        assert result["has_warning"] is True
        inc = result["inconsistencies"][0]
        assert inc["fewer_authors"] == ["Alice"]
        assert inc["more_authors"] == ["Alice", "Bob", "Charlie"]
        assert inc["difference"] == 2


# Real-shaped payload from rsmetacheck-bot under SoMEF 0.11.5 / rsmetacheck
# 0.3.7: codemeta.json's author list holds an organisation plus a person, and
# SoMEF flattens both to type="Agent"; pyproject.toml holds only the person.
# This is what P019 actually receives: detect_pitfalls_main applies
# normalize_somef_data first, which explodes multi-source entries per file.
SOMEF_ORG_AND_PERSON = {
    "author": [
        {
            "source": "https://raw.githubusercontent.com/SoftwareUnderstanding/rsmetacheck-bot/main/codemeta.json",
            "result": {
                "value": "Software Understanding",
                "type": "Agent",
                "identifier": "https://github.com/SoftwareUnderstanding",
            },
        },
        {
            "source": "https://raw.githubusercontent.com/SoftwareUnderstanding/rsmetacheck-bot/main/codemeta.json",
            "result": {
                "value": "Tom Francois",
                "type": "Agent",
                "email": "tom.francois@lapp.in2p3.fr",
                "affiliation": "Univ. Savoie Mont-Blanc, CNRS, LAPP",
                "identifier": "https://orcid.org/0000-0001-5226-3089",
                "name": "Tom Francois",
            },
        },
        {
            "source": "https://raw.githubusercontent.com/SoftwareUnderstanding/rsmetacheck-bot/main/pyproject.toml",
            "result": {
                "value": "Tom Francois",
                "type": "Agent",
                "email": "tom.francois@lapp.in2p3.fr",
                "affiliation": "Univ. Savoie Mont-Blanc, CNRS, LAPP",
                "identifier": "https://orcid.org/0000-0001-5226-3089",
                "name": "Tom Francois",
            },
        },
    ]
}

CODEMETA_WITH_ORGANIZATION = """{
  "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
  "@type": "SoftwareSourceCode",
  "author": [
    {"@type": "Organization", "name": "Software Understanding",
     "@id": "https://github.com/SoftwareUnderstanding"},
    {"@type": "Person", "givenName": "Tom", "familyName": "Francois",
     "@id": "https://orcid.org/0000-0001-5226-3089"}
  ]
}"""


class TestDeclaredOrganization:
    """Test suite for _declared_organization function"""

    @pytest.mark.parametrize("result,expected", [
        ({"type": "Organization", "name": "Org"}, True),
        ({"@type": "Organization", "name": "Org"}, True),
        ({"@type": ["Agent", "Organization"], "name": "Org"}, True),
        ({"agent_type": "Organization", "name": "Org"}, True),
        ({"type": "agent, organization", "name": "Org"}, True),
        # Person-ish and ambiguous entries must never be dropped
        ({"type": "Agent", "name": "Tom Francois"}, False),
        ({"type": "Person", "name": "Tom Francois"}, False),
        ({"value": "Tom", "identifier": "https://github.com/tom"}, False),
        ({"name": "Tom"}, False),
        ({}, False),
        ("Tom Francois", False),
        (None, False),
    ])
    def test_declared_organization_scenarios(self, result, expected):
        assert _declared_organization(result) is expected


class TestCodemetaPersons:
    """Test suite for _codemeta_persons function"""

    def test_reads_people_and_skips_organizations(self, monkeypatch):
        monkeypatch.setattr(
            "rsmetacheck.scripts.pitfalls.p019.fetch_text",
            lambda url, **kwargs: CODEMETA_WITH_ORGANIZATION,
        )
        count, names = _codemeta_persons(SOMEF_ORG_AND_PERSON)
        assert count == 1
        assert names == ["Tom Francois"]

    def test_missing_source_url_returns_none(self):
        somef_data = {"author": [{"source": "repository/codemeta.json",
                                  "result": {"name": "Tom"}}]}
        assert _codemeta_persons(somef_data) is None

    def test_unreadable_file_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            "rsmetacheck.scripts.pitfalls.p019.fetch_text",
            lambda url, **kwargs: None,
        )
        assert _codemeta_persons(SOMEF_ORG_AND_PERSON) is None

    def test_invalid_json_returns_none(self, monkeypatch):
        monkeypatch.setattr(
            "rsmetacheck.scripts.pitfalls.p019.fetch_text",
            lambda url, **kwargs: "not json",
        )
        assert _codemeta_persons(SOMEF_ORG_AND_PERSON) is None

    def test_nested_codemeta_is_ignored(self, monkeypatch):
        """A vendored codemeta must not be used as the author source."""
        def _fail(*args, **kwargs):
            raise AssertionError("fetch_text must not be called")

        monkeypatch.setattr("rsmetacheck.scripts.pitfalls.p019.fetch_text", _fail)
        somef_data = {"author": [{
            "source": "https://raw.githubusercontent.com/o/r/main/third_party/x/codemeta.json",
            "result": {"name": "Tom"},
        }]}
        assert _codemeta_persons(somef_data) is None


class TestOrganizationHandling:
    """P019 must not count organisations as authors"""

    def test_org_in_codemeta_is_not_reported(self):
        """The rsmetacheck-bot case: 2 agents vs 1 person is not a finding."""
        result = detect_inconsistent_author_count(SOMEF_ORG_AND_PERSON, "test_repo.json")
        assert result["has_warning"] is False
        assert result["min_author_count"] == result["max_author_count"] == 1
        sources = {s["source_file"]: s["author_count"] for s in result["author_sources"]}
        assert sources == {"codemeta.json": 1, "pyproject.toml": 1}

    def test_declared_organization_entry_is_dropped(self):
        """An entry SoMEF already labels as an organisation is not counted."""
        somef_data = {
            "author": [
                {"source": "repository/codemeta.json",
                 "result": {"name": "Org", "type": "Organization"}},
                {"source": "repository/codemeta.json",
                 "result": {"name": "Tom", "type": "Agent"}},
                {"source": "repository/pyproject.toml",
                 "result": {"name": "Tom", "type": "Agent"}},
            ]
        }
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        assert result["has_warning"] is False
        sources = {s["source_file"]: s["author_count"] for s in result["author_sources"]}
        assert sources == {"codemeta.json": 1, "pyproject.toml": 1}

    def test_source_left_with_no_people_is_omitted(self):
        """A file whose only authors are organisations must not become a 0."""
        somef_data = {
            "author": [
                {"source": "repository/codemeta.json",
                 "result": {"name": "Org", "type": "Organization"}},
                {"source": "repository/pyproject.toml",
                 "result": {"name": "Tom"}},
            ]
        }
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        assert result["has_warning"] is False
        assert [s["source_file"] for s in result["author_sources"]] == ["pyproject.toml"]

    def test_genuine_mismatch_still_detected(self, monkeypatch):
        """Filtering organisations must not mute a real people-count mismatch."""
        monkeypatch.setattr(
            "rsmetacheck.scripts.pitfalls.p019._codemeta_persons",
            lambda somef_data: (3, ["Tom Francois", "Alice", "Bob"]),
        )
        result = detect_inconsistent_author_count(SOMEF_ORG_AND_PERSON, "test_repo.json")
        assert result["has_warning"] is True
        inconsistency = result["inconsistencies"][0]
        assert inconsistency["fewer_count"] == 1
        assert inconsistency["more_count"] == 3
        assert inconsistency["difference"] == 2

    def test_falls_back_to_somef_view_when_file_unreadable(self, monkeypatch):
        """An unreadable codemeta.json keeps the previous (SoMEF) behaviour."""
        monkeypatch.setattr(
            "rsmetacheck.scripts.pitfalls.p019._codemeta_persons",
            lambda somef_data: None,
        )
        result = detect_inconsistent_author_count(SOMEF_ORG_AND_PERSON, "test_repo.json")
        assert result["has_warning"] is True
        assert result["max_author_count"] == 2

    def test_people_only_lists_are_untouched(self):
        """Ordinary repos keep behaving exactly as before."""
        somef_data = {
            "author": [
                {"source": "repository/codemeta.json", "result": [{"name": "Tom"}]},
                {"source": "repository/pyproject.toml", "result": {"name": "Tom"}},
            ]
        }
        result = detect_inconsistent_author_count(somef_data, "test_repo.json")
        assert result["has_warning"] is False
        assert result["total_sources"] == 2
