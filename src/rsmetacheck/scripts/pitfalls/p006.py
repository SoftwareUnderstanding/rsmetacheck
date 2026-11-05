from typing import Dict
import re

from rsmetacheck.utils.pitfall_utils import extract_metadata_source_filename
from rsmetacheck.utils.fetch_utils import find_source_url, fetch_text


def is_local_file_license(license_value: str) -> bool:
    """
    Check if license value points to a local file instead of stating the license name.
    """
    if not license_value or not isinstance(license_value, str):
        return False

    license_value = re.sub(r'^\s*licen[cs]e\s+file\s*:?\s*', '', license_value, flags=re.IGNORECASE)

    license_lower = license_value.lower().strip()

    if license_lower.startswith('http://') or license_lower.startswith('https://'):
        return False
    if 'http' in license_lower:
        # e.g. "GPL version 3, http://www.gnu.org/licenses/gpl-3.0.txt" names the license
        return False

    if license_value.startswith('./') or license_value.startswith('../'):
        return True

    if ('/' in license_value or '\\' in license_value):
        return True

    license_file_names = [
        'license', 'license.md', 'license.txt', 'license.rst',
        'copying', 'copying.md', 'copying.txt',
        'copyright', 'copyright.md', 'copyright.txt',
        'licence', 'licence.md', 'licence.txt',  # British spelling
        'readme.md', 'doc.txt', 'file.rst'
    ]

    if license_lower in license_file_names:
        return True

    file_extensions = ['.md', '.txt', '.rst']
    if any(license_lower.endswith(ext) for ext in file_extensions):
        return True

    return False


def detect_local_file_license_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when license in metadata files points to a local file instead of stating the name.
    Checks all metadata sources and collects all affected files.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "license_value": None,
        "source": None,
        "metadata_source_file": None,
        "metadata_source_files": [],
        "is_local_file": False
    }

    if "license" not in somef_data:
        return result

    license_entries = somef_data["license"]
    if not isinstance(license_entries, list):
        return result

    metadata_sources = ["codemeta.json", "description", "composer.json", "package.json", "pom.xml", "pyproject.toml", "requirements.txt", "setup.py"]

    for entry in license_entries:
        technique = entry.get("technique", "")
        source = entry.get("source", "")

        # Require the licence value to come from a metadata manifest. The bare
        # `technique == "code_parser"` branch also matched non-manifest parsers
        # (e.g. SoMEF >= 0.11.5 parses .zenodo.json), which reports licence
        # identifiers rather than a path/name that this check is about. Entries
        # that carry no provenance at all are still accepted.
        has_known_source = any(src in source.lower() for src in metadata_sources)
        if has_known_source or (technique == "code_parser" and not source.strip()):
            if "result" in entry and "value" in entry["result"]:
                license_value = entry["result"]["value"]

                if is_local_file_license(license_value):
                    source_filename = extract_metadata_source_filename(source)
                    if result["license_value"] is None:
                        result["license_value"] = license_value
                        result["source"] = source if source else f"technique: {technique}"
                        result["metadata_source_file"] = source_filename
                    result["metadata_source_files"].append(source_filename)
                    result["has_pitfall"] = True
                    result["is_local_file"] = True

    if not result["has_pitfall"]:
        pyproject_url = find_source_url(somef_data, "pyproject.toml")
        if pyproject_url:
            text = fetch_text(pyproject_url)
            if text:
                license_match = re.search(r'^\s*license\s*=\s*(.*)$', text, re.MULTILINE)
                if license_match:
                    raw = license_match.group(1).strip()
                    file_match = re.search(r'file\s*=\s*["\']([^"\']+)["\']', raw)
                    if file_match:
                        value = file_match.group(1)
                    else:
                        simple = re.search(r'["\']([^"\']+)["\']', raw)
                        value = simple.group(1) if simple else raw
                    if value and is_local_file_license(value):
                        result["has_pitfall"] = True
                        result["is_local_file"] = True
                        result["license_value"] = value
                        result["source"] = pyproject_url
                        result["metadata_source_file"] = "pyproject.toml"
                        result["metadata_source_files"].append("pyproject.toml")

    return result