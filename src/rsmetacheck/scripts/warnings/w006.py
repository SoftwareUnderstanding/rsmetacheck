from typing import Dict, List
import re

from rsmetacheck.utils.pitfall_utils import extract_metadata_source_filename
from rsmetacheck.utils.fetch_utils import fetch_text


def is_valid_identifier(identifier: str) -> bool:
    """
    Check if identifier appears to be a valid unique identifier (DOI, URL) rather than a name.
    """
    if not identifier or not isinstance(identifier, str):
        return False

    identifier = identifier.strip()

    if not identifier:
        return False

    # Check for DOI patterns
    doi_patterns = [
        r'^doi:10\.\d+/.+',  # doi:10.xxxx/yyyy format
        r'^10\.\d+/.+'  # 10.xxxx/yyyy format (bare DOI)
    ]

    for pattern in doi_patterns:
        if re.match(pattern, identifier, re.IGNORECASE):
            return True

    if identifier.lower() in ['doi:', '10.']:
        return False

    url_pattern = r'^https?://.+'
    if re.match(url_pattern, identifier, re.IGNORECASE):
        return True

    if identifier.lower().startswith('ftp://'):
        return False

    if ' ' in identifier and not any(char in identifier for char in ['/', ':', '.']):
        return False

    if identifier.replace(' ', '').replace('-', '').replace('_', '').isalpha():
        return False

    return True


def _is_strict_identifier(value) -> bool:
    """True only for an actual URL or DOI (not citation prose)."""
    if not value or not isinstance(value, str):
        return False
    v = value.strip()
    if re.match(r'^https?://\S+$', v, re.IGNORECASE):
        return True
    if re.match(r'^(doi:)?10\.\d{4,9}/\S+$', v, re.IGNORECASE):
        return True
    return False


def has_doi_in_other_sources(identifier_entries: List[Dict]) -> bool:
    """
    Check if there's a valid DOI in non-codemeta sources.
    """
    for entry in identifier_entries:
        source = entry.get("source", "")

        if "codemeta.json" in source.lower():
            continue

        if "result" in entry and "value" in entry["result"]:
            identifier_value = entry["result"]["value"]

            if isinstance(identifier_value, str):
                # Check for DOI patterns
                doi_patterns = [
                    r'^doi:10\.\d+/.+',  # doi:10.xxxx/yyyy format
                    r'^10\.\d+/.+'  # 10.xxxx/yyyy format (bare DOI)
                ]

                for pattern in doi_patterns:
                    if re.match(pattern, identifier_value, re.IGNORECASE):
                        return True

    return False


def detect_identifier_name_warning(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when codemeta.json identifier is a name instead of a valid unique identifier,
    but an identifier exists elsewhere.
    """
    result = {
        "has_warning": False,
        "file_name": file_name,
        "codemeta_identifier": None,
        "other_identifier": None,
        "codemeta_source": None,
        "other_source": None,
        "has_valid_identifier_elsewhere": False,
        "other_identifiers": []
    }

    if "identifier" not in somef_data:
        return result

    identifier_entries = somef_data["identifier"]
    if not isinstance(identifier_entries, list):
        return result

    codemeta_identifier = None
    codemeta_source = None
    codemeta_has_valid_id = False
    other_identifier = None
    other_source = None
    other_identifiers = []

    for entry in identifier_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")

        is_codemeta = (
                "codemeta.json" in source.lower() or
                (technique == "code_parser" and "codemeta" in source.lower())
        )

        if is_codemeta:
            if "result" in entry and "value" in entry["result"]:
                # SoMEF < 0.11.5 kept an identifier array as one list value;
                # >= 0.11.5 emits one entry per element, so validity and the
                # reported value cannot be decided from the first entry alone.
                # Warn only when NO codemeta identifier is a real unique id,
                # and report the first one that is a bare name.
                raw_value = entry["result"]["value"]
                items = raw_value if isinstance(raw_value, list) else [raw_value]
                for item in items:
                    if not isinstance(item, str):
                        continue
                    if is_valid_identifier(item):
                        codemeta_has_valid_id = True
                    elif codemeta_identifier is None:
                        codemeta_identifier = item
                        codemeta_source = source
                if codemeta_source is None:
                    codemeta_source = source

    for entry in identifier_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")

        is_codemeta = (
                "codemeta.json" in source.lower() or
                (technique == "code_parser" and "codemeta" in source.lower())
        )

        if is_codemeta:
            continue

        if "result" in entry and "value" in entry["result"]:
            identifier_value = entry["result"]["value"]

            if is_valid_identifier(identifier_value):
                other_identifiers.append({
                    "value": identifier_value,
                    "source": source
                })

                if other_identifier is None:
                    other_identifier = identifier_value
                    other_source = source

    # SoMEF 0.11.2 stores citation DOIs under `citation`, not `identifier`.
    if not other_identifier:
        for entry in somef_data.get("citation") or []:
            result_data = entry.get("result") or {}
            for candidate in (result_data.get("value"), result_data.get("url"), result_data.get("doi")):
                if _is_strict_identifier(candidate):
                    other_identifiers.append({"value": candidate, "source": entry.get("source", "citation")})
                    other_identifier = candidate
                    other_source = entry.get("source", "citation")
                    break
            if other_identifier:
                break

    # Fallback: look for a DOI/Zenodo badge in the README itself.
    if not other_identifier:
        readme_entries = somef_data.get("readme_url")
        if isinstance(readme_entries, list):
            for entry in readme_entries:
                url = (entry.get("result") or {}).get("value")
                if not isinstance(url, str):
                    continue
                text = fetch_text(url)
                if not text:
                    continue
                match = re.search(
                    r'10\.\d{4,9}/[^\s"\'<>)\]]+|zenodo\.org/badge/[^\s"\'<>)\]]+',
                    text, re.IGNORECASE)
                if match:
                    value = match.group(0)
                    other_identifiers.append({"value": value, "source": url})
                    other_identifier = value
                    other_source = url
                    break

    result["codemeta_identifier"] = codemeta_identifier
    result["codemeta_source"] = codemeta_source
    result["metadata_source_file"] = extract_metadata_source_filename(codemeta_source) if codemeta_source else "codemeta.json"
    result["other_identifier"] = other_identifier
    result["other_source"] = other_source
    result["other_identifiers"] = other_identifiers
    result["has_valid_identifier_elsewhere"] = len(other_identifiers) > 0

    if (codemeta_identifier and
            not codemeta_has_valid_id and
            not is_valid_identifier(codemeta_identifier) and
            other_identifier):
        result["has_warning"] = True

    return result