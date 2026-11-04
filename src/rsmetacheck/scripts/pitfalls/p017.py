import re
from typing import Dict, Optional, Tuple

from rsmetacheck.utils.pitfall_utils import extract_metadata_source_filename

_SEMVER_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)")


def _parse_semver(version_str: str) -> Optional[Tuple[int, int, int]]:
    m = _SEMVER_RE.match(version_str)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _versions_match(v1: str, v2: str) -> bool:
    a = v1.strip().lstrip("vV")
    b = v2.strip().lstrip("vV")
    if a == b:
        return True
    sv1 = _parse_semver(a)
    sv2 = _parse_semver(b)
    if sv1 and sv2:
        if sv1[0] == sv2[0] and sv1[1] == sv2[1] and sv1[2] != sv2[2] and abs(sv1[2] - sv2[2]) <= 2:
            return True
    return False


def get_codemeta_version(somef_data: Dict) -> str:
    """
    Get version from codemeta.json.
    """
    if "version" not in somef_data:
        return None

    version_entries = somef_data["version"]
    if not isinstance(version_entries, list):
        return None

    for entry in version_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")

        # Check if it's from codemeta.json
        if "codemeta.json" in source or (technique == "code_parser" and "codemeta" in source.lower()):
            if "result" in entry and "value" in entry["result"]:
                return entry["result"]["value"]

    return None


def get_other_metadata_versions(somef_data: Dict) -> list:
    """
    Get versions from other metadata sources (setup.py, pom.xml, etc).
    """
    if "version" not in somef_data:
        return []

    version_entries = somef_data["version"]
    if not isinstance(version_entries, list):
        return []

    other_versions = []
    metadata_sources = ["codemeta.json", "DESCRIPTION", "composer.json", "package.json", "pom.xml", "pyproject.toml", "requirements.txt", "setup.py"]

    for entry in version_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")

        if "codemeta.json" in source:
            continue

        # Only versions declared in a known package/metadata manifest count as
        # "other" versions. Accepting any code_parser entry let unrelated
        # parsers feed this comparison - notably SoMEF >= 0.11.5's .zenodo.json,
        # whose deposit version legitimately differs from the package version.
        # Entries with no provenance at all cannot be filtered by file name and
        # are still accepted (source matching is case-insensitive: manifest
        # names in the list are not all lower-case, e.g. "DESCRIPTION").
        has_known_source = any(src.lower() in source.lower() for src in metadata_sources)
        if has_known_source or (technique == "code_parser" and not source.strip()):
            if "result" in entry and "value" in entry["result"]:
                other_versions.append({
                    "version": entry["result"]["value"],
                    "source": source,
                    "technique": technique
                })

    return other_versions


def detect_codemeta_version_mismatch_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when codemeta.json version doesn't match other package metadata versions.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "codemeta_version": None,
        "metadata_source_file": None,
        "metadata_source_files": [],
        "other_versions": [],
        "mismatched_versions": []
    }

    codemeta_version = get_codemeta_version(somef_data)
    if not codemeta_version:
        return result

    other_versions = get_other_metadata_versions(somef_data)
    if not other_versions:
        return result

    mismatched_versions = []
    mismatched_source_files = []

    for other_version_entry in other_versions:
        other_version = other_version_entry["version"]

        if not _versions_match(codemeta_version, other_version):
            mismatched_versions.append(other_version_entry)
            mismatched_source_files.append(
                extract_metadata_source_filename(other_version_entry.get("source", ""))
            )

    if mismatched_versions:
        result["has_pitfall"] = True
        result["codemeta_version"] = codemeta_version
        result["other_versions"] = other_versions
        result["mismatched_versions"] = mismatched_versions
        result["metadata_source_file"] = "codemeta.json"
        result["metadata_source_files"] = ["codemeta.json"] + mismatched_source_files

    return result