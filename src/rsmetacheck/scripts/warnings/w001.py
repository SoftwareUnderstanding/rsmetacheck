from typing import Dict, List, Tuple, Optional
import re
from rsmetacheck.utils.pitfall_utils import extract_metadata_source_filename


def extract_requirements_from_metadata(somef_data: Dict) -> List[Dict]:
    """
    Extract requirements from metadata files in SoMEF output.
    Returns a list of dicts with source and requirements info.
    """
    if "requirements" not in somef_data:
        return []

    requirements_entries = somef_data["requirements"]
    if not isinstance(requirements_entries, list):
        return []

    metadata_sources = ["codemeta.json", "DESCRIPTION", "composer.json", "package.json", "pom.xml", "pyproject.toml",
                        "requirements.txt", "setup.py"]

    results = []
    for entry in requirements_entries:
        if "source" in entry:
            source = entry["source"]
            if any(meta_file in source for meta_file in metadata_sources):
                if "result" in entry:
                    results.append({
                        "source": source,
                        "requirement": entry["result"]
                    })

    return results


def check_requirement_has_version(req_name: str) -> bool:
    """
    Check if a single requirement has version information.
    Returns True if version is present and non-empty, False otherwise.
    """
    version_operators = ["==", ">=", "<=", ">", "<", "~=", "!=", "^", "~"]
    if any(op in req_name for op in version_operators) or re.search(r'\bv?\d+(\.\d+)+\b', req_name):
        return True
    return False


def is_uri_requirement(value: str) -> bool:
    """True when a "requirement" is really a link rather than a dependency.

    requirements lists sometimes contain a pointer to the requirements file, a
    VCS remote, an archived SWHID or a local path. Those are not dependencies and
    cannot carry a version, so they must not count towards W001.
    """
    if not isinstance(value, str):
        return False
    v = value.strip()
    if not v:
        return False
    if v.lower().startswith(('http://', 'https://', 'git+', 'git://', 'ssh://',
                             'svn://', 'hg://', 'bzr://', 'ftp://', 'file:')):
        return True
    if re.match(r'^git@[^:\s]+:', v):
        return True
    if re.search(r'\bswh:1:', v, re.IGNORECASE):
        return True
    if v.startswith(('./', '../', '/')):
        return True
    return False


def analyze_requirements_versions(requirements_data: Dict) -> Tuple[int, int, List[str]]:
    """
    Analyze requirements to count versioned vs unversioned dependencies.
    Returns (total_requirements, unversioned_count, unversioned_names).
    """
    requirement = requirements_data["requirement"]

    if isinstance(requirement, dict):
        requirements_list = [requirement]
    elif isinstance(requirement, list):
        requirements_list = requirement
    else:
        return 0, 0, []

    total_requirements = 0
    unversioned_count = 0
    unversioned_names = []

    for req in requirements_list:
        if isinstance(req, dict):
            req_name = req.get("name", req.get("value", "unknown"))
            if isinstance(req_name, str) and bool(re.search(r'\b(npm|bash|cd|pip|install)\b', req_name.lower())):
                continue

            # A link (requirements-file pointer, VCS remote, SWHID, path) is not
            # a dependency — skip it instead of calling it unversioned.
            if isinstance(req_name, str) and is_uri_requirement(req_name):
                continue

            if isinstance(req_name, str) and ',' in req_name:
                parts = [p.strip() for p in req_name.split(',')]
            else:
                parts = [req_name]

            for part in parts:
                if not part: continue
                if isinstance(part, str) and is_uri_requirement(part): continue
                total_requirements += 1
                has_version_field = "version" in req and bool(req["version"])
                has_version_str = isinstance(part, str) and check_requirement_has_version(part)
                
                if not (has_version_field or has_version_str):
                    unversioned_count += 1
                    unversioned_names.append(part)

    return total_requirements, unversioned_count, unversioned_names


def detect_unversioned_requirements(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect unversioned requirements warning for a single repository.
    Returns detection result with warning info.
    """
    result = {
        "has_warning": False,
        "file_name": file_name,
        "metadata_source": None,
        "metadata_source_file": None,
        "total_requirements": 0,
        "unversioned_count": 0,
        "unversioned_requirements": [],
        "percentage_unversioned": 0.0
    }

    requirements_data_list = extract_requirements_from_metadata(somef_data)

    if not requirements_data_list:
        return result

    result["metadata_source"] = requirements_data_list[0]["source"]
    result["metadata_source_file"] = extract_metadata_source_filename(requirements_data_list[0]["source"])

    total_reqs = 0
    unversioned_count = 0
    unversioned_names = []

    for req_data in requirements_data_list:
        cur_total, cur_unversioned, cur_names = analyze_requirements_versions(req_data)
        total_reqs += cur_total
        unversioned_count += cur_unversioned
        unversioned_names.extend(cur_names)

    result["total_requirements"] = total_reqs
    result["unversioned_count"] = unversioned_count
    result["unversioned_requirements"] = list(dict.fromkeys(unversioned_names))

    if total_reqs > 0:
        result["percentage_unversioned"] = round((unversioned_count / total_reqs) * 100, 2)

        if unversioned_count > 0:
            result["has_warning"] = True

    return result