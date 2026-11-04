import re
from typing import Dict, Optional

from rsmetacheck.utils.fetch_utils import fetch_text, fetch_license_file


def extract_license_from_file(somef_data: Dict) -> Optional[Dict[str, str]]:
    """
    Extract the first license file entry's content from SoMEF output.

    Kept for backward compatibility (the detector itself scans *all* license
    entries via ``detect_copyright_only_license``).
    """
    license_entries = somef_data.get("license")
    if not isinstance(license_entries, list):
        return None

    for entry in license_entries:
        source = entry.get("source")
        source_str = str(source) if source is not None else ""
        if "LICENSE" not in source_str.upper():
            continue
        result = entry.get("result") or {}
        value = result.get("value")
        if not value:
            return None
        return {"source": source_str, "content": value}

    return None


def detect_copyright_only_license(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect copyright-only license pitfall for a single repository.
    Returns detection result with pitfall info or None if no pitfall found.

    Every license file entry is evaluated (a repository may ship both a
    copyright-only ``LICENSE`` and a full ``LICENSE.md``), and the file text is
    fetched from the source URL when SoMEF only kept the SPDX id.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "license_source": None,
        "is_copyright_only": False
    }

    license_entries = somef_data.get("license")
    if not isinstance(license_entries, list):
        return result

    for entry in license_entries:
        source = entry.get("source")
        source_str = str(source) if source else ""
        if not re.search(r'licen[cs]e|copying|copyright|unlicense', source_str, re.IGNORECASE):
            continue

        if result["license_source"] is None:
            result["license_source"] = source_str

        content = None
        if source_str.startswith(("http://", "https://")):
            content = fetch_text(source_str)
        if content is None:
            value = (entry.get("result") or {}).get("value")
            if isinstance(value, str):
                content = value

        if content and check_copyright_only_license(content):
            result["has_pitfall"] = True
            result["is_copyright_only"] = True
            result["license_source"] = source_str or content[:120]
            break

    # Fallback: no license-file entry was available in the SoMEF output.
    if result["license_source"] is None:
        url, content = fetch_license_file(somef_data)
        if url and content:
            result["license_source"] = url
            if check_copyright_only_license(content):
                result["has_pitfall"] = True
                result["is_copyright_only"] = True

    return result


def check_copyright_only_license(license_content: str) -> bool:
    """
    Check if license file only contains copyright information without actual license terms.
    Example:
    YEAR: 2017
    COPYRIGHT HOLDER: Adam H. Sparks
    """
    if not license_content:
        return False

    content_lower = license_content.lower().strip()
    content_lines = [line.strip() for line in license_content.strip().split('\n') if line.strip()]

    copyright_only_patterns = [
        r'year\s*:\s*\d{4}',  # YEAR: 2017
        r'copyright\s+holder\s*:\s*[a-zA-Z]',  # COPYRIGHT HOLDER: Someone
        r'author\s*:\s*[a-zA-Z]',  # AUTHOR: Someone
        r'copyright\s*©?\s*\d{4}',  # Copyright 2017 or Copyright © 2017
        r'\(c\)\s*\d{4}',  # (C) 2017
    ]

    license_term_patterns = [
        r'permission\s+is\s+hereby\s+granted',
        r'subject\s+to\s+the\s+following\s+conditions',
        r'redistribution\s+and\s+use',
        r'without\s+restriction',
        r'without\s+warranty',
        r'liability',
        r'terms\s+and\s+conditions',
        r'licensed\s+under',
        r'mit\s+license',
        r'apache\s+license',
        r'gnu\s+general\s+public\s+license',
        r'bsd\s+license',
        r'creative\s+commons',
    ]

    has_copyright_info = any(re.search(pattern, content_lower) for pattern in copyright_only_patterns)
    has_license_terms = any(re.search(pattern, content_lower) for pattern in license_term_patterns)

    if has_license_terms:
        return False

    # This will check if it has copyright info but no license terms and is short, it's likely copyright-only
    if has_copyright_info and not has_license_terms and len(content_lines) <= 10:
        return True

    # Check for the exact format "YEAR: xxxx" and "COPYRIGHT HOLDER: xxxx"
    year_pattern_found = bool(re.search(r'year\s*:\s*\d{4}', content_lower))
    copyright_holder_pattern_found = bool(re.search(r'copyright\s+holder\s*:', content_lower))

    if year_pattern_found and copyright_holder_pattern_found:
        if has_license_terms:
            return False
        return True

    if len(content_lines) <= 5:
        meaningful_lines = []

        for line in content_lines:
            line_lower = line.lower()

            if not any(re.search(pattern, line_lower) for pattern in copyright_only_patterns):

                if (len(line.strip()) > 0 and
                    not line.strip().startswith('#') and
                    not line.strip().startswith('//') and
                    line.strip() not in ['', '-', '=', '*']):
                    meaningful_lines.append(line)

        if len(meaningful_lines) <= 1 and has_copyright_info:
            return True

    return False