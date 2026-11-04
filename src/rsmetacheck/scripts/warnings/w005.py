from typing import Dict, List
import re
from rsmetacheck.utils.pitfall_utils import extract_metadata_source_filename


_VERSION_OPERATOR_RE = re.compile(r'(?:~=|==|!=|<=|>=|<|>|===)')
_VERSION_SPECIFIER_RE = re.compile(r'^(?:~=|==|!=|<=|>=|<|>|===)\s*\S+$')


def _is_version_range_string(req_str: str) -> bool:
    """
    Detect a single requirement with a PEP 440 style version range, e.g.
    "rdflib==>=7.0,<8.0" or "numpy>=1.20,<2.0". A comma inside such a
    specifier separates version constraints, not multiple dependencies.
    """
    parts = re.split(r',\s*', req_str)
    if len(parts) < 2:
        return False

    name_part = parts[0].strip()
    if not _VERSION_OPERATOR_RE.search(name_part):
        return False

    rest = parts[1:]
    return all(
        part and _VERSION_SPECIFIER_RE.match(part) and not re.search(r'\s', part)
        for part in rest
    )


def detect_multiple_requirements_in_string(requirement_string: str) -> List[str]:
    """
    Detect if a requirement string contains multiple requirements.
    Returns list of detected requirements or empty list if just one.
    """
    if not requirement_string or not isinstance(requirement_string, str):
        return []

    if "\n" in requirement_string:
        return []

    if len(requirement_string) > 500:
        return []

    # Clean the string
    req_str = requirement_string.strip()

    # Not a package list: Software Heritage identifiers, URLs/VCS refs, and
    # natural-language prose ("at least one of ... e.g. NEURON, NEST, ...").
    if re.search(r'\bswh:1:', req_str):
        return []
    if req_str.startswith(('http://', 'https://', 'git+', 'git://')):
        return []
    if re.search(r'\b(?:e\.g\.|i\.e\.|such as|at least one|for example)\b', req_str, re.IGNORECASE):
        return []

    # Patterns that might indicate multiple requirements
    if bool(re.search(r'\b(npm|bash|cd|pip|install)\b', req_str.lower())):
        return []

    detected_requirements = []

    if re.search(r',\s*', req_str):
        if _is_version_range_string(req_str):
            return []
        parts = re.split(r',\s*', req_str)
        if len(parts) > 1:
            detected_requirements = [part.strip() for part in parts if part.strip()]
    elif re.search(r';\s*', req_str):
        parts = re.split(r';\s*', req_str)
        if len(parts) > 1:
            detected_requirements = [part.strip() for part in parts if part.strip()]
    elif re.match(r'^([A-Z][a-zA-Z0-9]*(\s+|$)){2,}$', req_str):
        parts = re.split(r'\s+', req_str)
        if len(parts) > 1:
            detected_requirements = [part.strip() for part in parts if part.strip()]
    elif re.search(r'\s{2,}', req_str):
        parts = re.split(r'\s{2,}', req_str)
        if len(parts) > 1:
            detected_requirements = [part.strip() for part in parts if part.strip()]

    return detected_requirements if len(detected_requirements) > 1 else []


def detect_multiple_requirements_string_warning(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when software requirements have multiple requirements written as one string.
    Checks all metadata sources and collects all affected files.
    """
    result = {
        "has_warning": False,
        "file_name": file_name,
        "requirement_string": None,
        "detected_requirements": [],
        "source": None,
        "metadata_source_file": None,
        "metadata_source_files": [],
        "count_detected": 0
    }

    if "requirements" not in somef_data:
        return result

    requirements_entries = somef_data["requirements"]
    if not isinstance(requirements_entries, list):
        return result

    metadata_sources = ["codemeta.json", "DESCRIPTION", "composer.json", "package.json", "pom.xml", "pyproject.toml", "requirements.txt", "setup.py"]

    for entry in requirements_entries:
        technique = entry.get("technique", "")
        source = entry.get("source", "")

        if technique in metadata_sources or any(
                src in source.lower() for src in ["codemeta.json", "setup.py", "pom.xml"]):
            if "result" in entry and "value" in entry["result"]:
                requirement_value = entry["result"]["value"]

                if isinstance(requirement_value, str):
                    detected_reqs = detect_multiple_requirements_in_string(requirement_value)

                    if detected_reqs:
                        if result["requirement_string"] is None:
                            result["requirement_string"] = requirement_value
                            result["detected_requirements"] = detected_reqs
                            result["source"] = source if source else f"technique: {technique}"
                            result["metadata_source_file"] = extract_metadata_source_filename(source)
                            result["count_detected"] = len(detected_reqs)
                        source_filename = extract_metadata_source_filename(source)
                        result["metadata_source_files"].append(source_filename)
                        result["has_warning"] = True

                elif isinstance(requirement_value, list) and len(requirement_value) == 1:
                    single_req = requirement_value[0]
                    if isinstance(single_req, str):
                        detected_reqs = detect_multiple_requirements_in_string(single_req)

                        if detected_reqs:
                            if result["requirement_string"] is None:
                                result["requirement_string"] = single_req
                                result["detected_requirements"] = detected_reqs
                                result["source"] = source if source else f"technique: {technique}"
                                result["metadata_source_file"] = extract_metadata_source_filename(source)
                                result["count_detected"] = len(detected_reqs)
                            source_filename = extract_metadata_source_filename(source)
                            result["metadata_source_files"].append(source_filename)
                            result["has_warning"] = True

    return result