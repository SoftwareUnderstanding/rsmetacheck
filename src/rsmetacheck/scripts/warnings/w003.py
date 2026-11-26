import re
from typing import Dict

# Licence-family tokens used to decide whether a piece of metadata prose names
# more than one licence. Word-bounded so "GPL" does not fire inside "LGPL"/"AGPL".
LICENCE_FAMILY = re.compile(
    r"\b(?:MIT|Apache|GPL|LGPL|AGPL|BSD|MPL|CC-?BY|CC0|EPL|CDDL|Unlicense)\b",
    re.IGNORECASE,
)

# Explicit dual-licence phrasing. Deliberately narrow — no `.*` spanning arbitrary
# text, so ordinary GPL boilerplate ("...commands or options", "...version 3 of
# the license, or...") does not match.
EXPLICIT_DUAL_PATTERNS = [
    r"dual[\s-]?licen[cs]ed?",
    r"dually[\s-]?licen[cs]ed?",
    r"multiple[\s-]?licen[cs]es?",
    r"licen[cs]e[sd]?\s+under.{0,40}\b(?:and|or)\b",
    r"available\s+under.{0,30}\b(?:two|multiple|either|both)\b",
    r"choose\b.{0,40}\blicen[cs]e\b",
]

# Basenames that are full licence texts, never a "multiple licences" indicator.
_LICENCE_FILE_RE = re.compile(r"^(licen[cs]e|copying|copyright)([-_.].*)?$", re.IGNORECASE)


def _techniques(technique) -> set:
    if isinstance(technique, (list, tuple)):
        return {str(t).lower() for t in technique}
    return {str(technique).lower()} if technique else set()


def _is_licence_file_source(source) -> bool:
    if not source:
        return False
    name = str(source).rstrip("/").split("/")[-1]
    return bool(_LICENCE_FILE_RE.match(name))


def _has_dual_licence_indicator(text: str, is_licence_file: bool = False) -> bool:
    lower = text.lower()
    for pattern in EXPLICIT_DUAL_PATTERNS:
        if re.search(pattern, lower):
            return True
    # A full licence text names other licence families legitimately (GPL's own
    # prose mentions LGPL/AGPL), so only count families in prose metadata sources.
    if is_licence_file:
        return False
    families = {f.upper() for f in LICENCE_FAMILY.findall(lower)}
    return len(families) >= 2


def detect_dual_license_missing_codemeta_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when repository has multiple licenses but codemeta.json only lists one.
    """
    result = {
        "has_warning": False,
        "file_name": file_name,
        "has_dual_license_indicator": False,
        "codemeta_license_count": 0,
        "dual_license_source": None
    }

    if "license" not in somef_data:
        return result

    license_entries = somef_data["license"]
    if not isinstance(license_entries, list):
        return result

    has_dual_license_indicator = False
    dual_license_source = None
    codemeta_license_count = 0

    for entry in license_entries:
        source = entry.get("source", "")
        techniques = _techniques(entry.get("technique"))

        if "code_parser" in techniques and "codemeta.json" in str(source).lower():
            codemeta_license_count += 1
            continue

        if not has_dual_license_indicator and "result" in entry and "value" in entry["result"]:
            license_text = entry["result"]["value"]
            if isinstance(license_text, str) and _has_dual_licence_indicator(
                    license_text, _is_licence_file_source(source)):
                has_dual_license_indicator = True
                dual_license_source = source

    result["has_dual_license_indicator"] = has_dual_license_indicator
    result["codemeta_license_count"] = codemeta_license_count
    result["dual_license_source"] = dual_license_source

    if has_dual_license_indicator and codemeta_license_count <= 1:
        result["has_warning"] = True

    return result
