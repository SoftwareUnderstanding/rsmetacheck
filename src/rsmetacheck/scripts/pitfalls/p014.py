from typing import Dict
import re


def is_bare_doi(identifier: str) -> bool:
    """
    Check if identifier is a bare DOI without full https://doi.org/ URL.
    """
    if not identifier or not isinstance(identifier, str):
        return False

    identifier = identifier.strip()

    # If it already starts with https://doi.org/, it's not bare
    if identifier.startswith('https://doi.org/'):
        return False

    # Check if it's a bare DOI pattern
    bare_doi_patterns = [
        r'^doi:10\.\d+/',  # doi:10.1234/example
        r'^10\.\d+/',  # 10.1234/example
    ]

    for pattern in bare_doi_patterns:
        if re.match(pattern, identifier):
            return True

    return False


def detect_bare_doi_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when codemeta.json uses bare DOIs in identifier field instead of full URL.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "identifier_value": None,
        "source": None,
        "is_bare_doi": False
    }

    if "identifier" not in somef_data:
        return result

    identifier_entries = somef_data["identifier"]
    if not isinstance(identifier_entries, list):
        return result

    for entry in identifier_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")

        if "codemeta.json" in source or (technique == "code_parser" and "codemeta" in source.lower()):
            if "result" in entry and "value" in entry["result"]:
                identifier_value = entry["result"]["value"]

                # SoMEF < 0.11.5 kept an identifier array as a single list value;
                # >= 0.11.5 emits one entry per element. Accept both shapes.
                candidates = identifier_value if isinstance(identifier_value, list) else [identifier_value]

                for candidate in candidates:
                    if is_bare_doi(candidate):
                        result["has_pitfall"] = True
                        result["identifier_value"] = candidate
                        result["source"] = source
                        result["is_bare_doi"] = True
                        break
                if result["has_pitfall"]:
                    break

    return result