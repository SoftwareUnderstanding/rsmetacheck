import re
from typing import Dict, Optional

from rsmetacheck.utils.fetch_utils import fetch_text, fetch_license_file

# Licences whose text ships an appendix of *instructions to the licensor*
# ("How to Apply These Terms…", "APPENDIX: How to apply…"). The placeholder
# tokens there (<year>, <name of author>, [yyyy], [name of copyright owner],
# <program>) are part of the licence itself, not an unfilled field, so these
# families are never reported as P002.
EXEMPT_FAMILIES = {"gpl", "lgpl", "agpl", "apache", "mpl", "epl", "cddl"}

# Short permissive licences where the copyright line is genuinely the author's
# to fill in. Only the operating header is inspected for these.
CHECK_FAMILIES = {"mit", "mit-0", "bsd", "0bsd", "isc", "x11", "zlib", "unlicense"}

# Order matters: copyleft families first, because their text often quotes other
# licence names (e.g. GPLv3 mentions the Apache License in the compatibility
# section).
FAMILY_SIGNATURES = [
    ("agpl", r"gnu\s+affero\s+general\s+public\s+license"),
    ("lgpl", r"gnu\s+lesser\s+general\s+public\s+license"),
    ("gpl", r"gnu\s+general\s+public\s+license"),
    ("apache", r"apache\s+license"),
    ("mpl", r"mozilla\s+public\s+license"),
    ("epl", r"eclipse\s+public\s+license"),
    ("cddl", r"common\s+development\s+and\s+distribution\s+license"),
    ("x11", r"except\s+as\s+contained\s+in\s+this\s+notice"),
    ("zlib", r"origin\s+of\s+this\s+software\s+must\s+not\s+be\s+misrepresented"),
    ("unlicense", r"free\s+and\s+unencumbered\s+software\s+released\s+into\s+the\s+public\s+domain"),
    ("isc", r"permission\s+to\s+use,\s*copy,\s*modify,\s*and/?or\s+distribute"),
    ("bsd", r"redistribution\s+and\s+use\s+in\s+source\s+and\s+binary\s+forms"),
    ("mit", r"permission\s+is\s+hereby\s+granted,\s*free\s+of\s+charge"),
    ("mit", r"\bmit\s+license\b"),
    ("mit-0", r"\bmit\s+no\s+attribution\b"),
]

# Fixed tokens that only ever appear in an unfilled template.
PLACEHOLDER_PATTERNS = [
    r'<program>',
    r'<year>',
    r'<name of author>',
    r'<name>',
    r'<copyright holders?>',
    r'<owner>',
    r'<author>',
    r'<organization>',
    r'<insert[^>]*>',
    r'<name of copyright owner>',
    r'<yyyy>',
    r'\[year\]',
    r'\[yyyy\]',
    r'\[fullname\]',
    r'\[name\]',
    r'\[owner\]',
    r'\[author\]',
    r'\[copyright holder\]',
    r'\[name of copyright owner\]',
    r'\[insert[^\]]*\]',
    r'\{year\}',
    r'\{yyyy\}',
    r'\{fullname\}',
    r'\{name\}',
    r'\{author\}',
    r'\{email\}',
    r'\byyyy\b',
]

# "Copyright (c) YEAR" / "<year>" / "20XX" in the copyright line itself.
COPYRIGHT_LINE_STUB = re.compile(
    r"copyright[^\n]{0,40}?(?:"
    r"<year>|\[year\]|\{year\}|<yyyy>|\[yyyy\]|\byyyy\b|"
    r"\byear\b|\b4-digit year\b|\b20XX\b|\bname of (?:author|copyright owner)\b"
    r")",
    re.IGNORECASE,
)

# Everything below an anchor is the licence body (grant, conditions, warranty),
# not the copyright header.
HEADER_ANCHORS = [
    r"permission\s+is\s+hereby\s+granted",
    r"permission\s+to\s+use,\s*copy",
    r"redistribution\s+and\s+use",
    r"this\s+software\s+is\s+provided",
    r"the\s+software\s+is\s+provided",
    r"origin\s+of\s+this\s+software",
    r"free\s+and\s+unencumbered\s+software",
]

HEADER_MAX_LINES = 25


def extract_license_from_file(somef_data: Dict) -> Optional[Dict[str, str]]:
    """
    Extract the LICENSE file content.

    SoMEF keeps only the SPDX id in the license entry's ``value``, so the actual
    file text is fetched from the entry's ``source`` URL when available.
    """
    license_entries = somef_data.get("license")
    if not isinstance(license_entries, list):
        return None

    for entry in license_entries:
        if "source" not in entry:
            continue
        source = entry["source"]
        source_str = str(source)
        if not re.search(r'licen[cs]e|copying|copyright|unlicense', source_str, re.IGNORECASE):
            continue

        if source_str.startswith(("http://", "https://")):
            content = fetch_text(source_str)
            if content:
                return {"source": source_str, "content": content}

        result = entry.get("result") or {}
        value = result.get("value")
        if isinstance(value, str) and value.strip():
            return {"source": source_str, "content": value}

    # Fallback: SoMEF may have merged the license entries and dropped the
    # LICENSE/COPYING source. Probe the repository root for a license file.
    url, content = fetch_license_file(somef_data)
    if url and content:
        return {"source": url, "content": content}

    return None


def detect_license_family(license_content: str) -> str:
    """Classify the licence family from its text. Returns "" when unknown.

    The title area is inspected first: GPLv3's compatibility section mentions the
    GNU Affero GPL, so a whole-text scan would mislabel GPLv3 as AGPL.
    """
    if not license_content:
        return ""

    head = "\n".join(license_content.splitlines()[:8]).lower()
    body = license_content.lower()

    for scope in (head, body):
        for name, pattern in FAMILY_SIGNATURES:
            if re.search(pattern, scope):
                return _refine_family(name, body)

    return ""


def _refine_family(family: str, text: str) -> str:
    """Disambiguate the BSD variants that share the ISC grant wording."""
    if family == "isc":
        flat = re.sub(r"\s+", " ", text)
        if re.search(r"zero[- ]clause|\b0bsd\b", flat):
            return "0bsd"
        # Without the retention clause the grant is 0BSD rather than ISC.
        if "provided that the above copyright" not in flat:
            return "0bsd"
    return family


def operative_region(license_content: str, max_lines: int = HEADER_MAX_LINES) -> str:
    """
    Return the copyright/attribution header of a licence: everything before the
    body grant, capped at ``max_lines`` lines.
    """
    lines = license_content.splitlines()
    cut = len(lines)
    for index, line in enumerate(lines):
        if index >= max_lines:
            break
        lowered = line.lower()
        if any(re.search(anchor, lowered) for anchor in HEADER_ANCHORS):
            cut = index
            break
    return "\n".join(lines[:min(cut, max_lines)])


def find_placeholders(region: str):
    """Return the placeholder tokens found in ``region`` (deduplicated, ordered)."""
    found = []
    lowered = region.lower()
    for pattern in PLACEHOLDER_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            token = match.group(0)
            if token not in found:
                found.append(token)
    # A bare "YEAR"/"4-digit year" stub only matters when no explicit token was
    # found; otherwise it just repeats the same evidence with prose attached.
    if not found:
        stub = COPYRIGHT_LINE_STUB.search(region)
        if stub:
            found.append(stub.group(0).strip())
    return found


def analyze_license_placeholders(license_content: str) -> Dict:
    """
    Decide whether a licence file carries unfilled template placeholders.

    GPL/LGPL/AGPL/Apache/MPL/EPL/CDDL are exempt: their placeholder tokens belong
    to the licence's own "how to apply" appendix. Permissive licences
    (MIT/MIT-0/BSD/0BSD/ISC/X11/zlib/Unlicense) are checked in the copyright
    header only, and an unrecognised licence is treated the same way so that
    arbitrary prose cannot be mistaken for a template.
    """
    analysis = {
        "family": "",
        "decision": "no_content",
        "placeholders": [],
        "has_pitfall": False,
        "region": "",
    }
    if not license_content or not license_content.strip():
        return analysis

    family = detect_license_family(license_content)
    analysis["family"] = family

    if family in EXEMPT_FAMILIES:
        analysis["decision"] = "exempt_appendix_family"
        return analysis

    region = operative_region(license_content)
    analysis["region"] = region
    placeholders = find_placeholders(region)
    analysis["placeholders"] = placeholders

    if placeholders:
        analysis["decision"] = "placeholder_in_copyright_header"
        analysis["has_pitfall"] = True
    else:
        analysis["decision"] = "clean"
    return analysis


def check_license_template_placeholders(license_content: str) -> bool:
    """True when the licence's copyright header still carries template tokens."""
    return analyze_license_placeholders(license_content)["has_pitfall"]


def detect_license_template_placeholders(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect license template placeholder pitfall for a single repository.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "license_source": None,
        "placeholders_found": False,
        "license_family": None,
        "placeholders": [],
        "decision": None,
    }

    license_info = extract_license_from_file(somef_data)

    if license_info:
        analysis = analyze_license_placeholders(license_info["content"])
        result["license_source"] = license_info["source"]
        result["license_family"] = analysis["family"] or None
        result["placeholders"] = analysis["placeholders"]
        result["decision"] = analysis["decision"]

        if analysis["has_pitfall"]:
            result["has_pitfall"] = True
            result["placeholders_found"] = True

    return result
