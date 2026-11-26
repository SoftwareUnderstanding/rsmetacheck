import json
import re
from typing import Dict

from rsmetacheck.utils.fetch_utils import fetch_text, find_source_url

NON_VERSIONED_LANGUAGES = {
    "HTML", "CSS", "Shell", "Makefile",
    "Dockerfile", "Batchfile", "PowerShell", "CMake",
    "JavaScript", "Java", "XSLT",
    "Jupyter Notebook", "Jupyter",
}


def _name_contains_version(name: str) -> bool:
    return bool(re.search(r"\d", name))


_NON_VERSIONED_LOWER = {n.lower() for n in NON_VERSIONED_LANGUAGES}


def _is_non_versioned(name: str) -> bool:
    """Languages that are conventionally declared without a version.

    SoMEF/JSON-LD writers are inconsistent about case ("JavaScript" vs
    "javascript"), so compare case-insensitively.
    """
    return isinstance(name, str) and name.strip().lower() in _NON_VERSIONED_LOWER


def _value_is_list(result_data: Dict) -> bool:
    name_val = result_data.get("name")
    value_val = result_data.get("value")
    return isinstance(name_val, list) or isinstance(value_val, list)


def _techniques(entry: Dict) -> set:
    """SoMEF emits `technique` as a string or a list of strings."""
    technique = entry.get("technique")
    if isinstance(technique, (list, tuple)):
        return {str(t).lower() for t in technique}
    return {str(technique).lower()} if technique else set()


def _language_entry_has_version(entry) -> bool:
    """True when the codemeta programmingLanguage entry declares a version itself."""
    if isinstance(entry, dict):
        if entry.get("version"):
            return True
        name = entry.get("name") or entry.get("value")
        return isinstance(name, str) and bool(re.search(r"\d+\.\d+", name))
    if isinstance(entry, str):
        return bool(re.search(r"\d+\.\d+", entry))
    return False


def _languages_from_codemeta_file(somef_data: Dict):
    """Read programmingLanguage directly from the codemeta.json at the analyzed ref.

    SoMEF writes a `version` into the language entry it emits (e.g.
    ``{"name": "R", "version": "4.4.3"}``) harvested from the runtime platform or
    the GitHub API. That enrichment hides a codemeta file which never declares a
    version itself, which is exactly what this warning is about. When the file can
    be read it is authoritative; when it cannot, the SoMEF view is used instead.

    Returns a list of ``(language_name, declares_version)`` or None.
    """
    url = find_source_url(somef_data, "codemeta.json", codemeta_root_only=True)
    if not url:
        return None
    text = fetch_text(url)
    if not text:
        return None
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    raw = data.get("programmingLanguage")
    if raw is None:
        return None

    entries = raw if isinstance(raw, list) else [raw]
    languages = []
    for entry in entries:
        name = entry.get("name") or entry.get("value") if isinstance(entry, dict) else entry
        if isinstance(name, list):
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        languages.append((name.strip(), _language_entry_has_version(entry)))

    return (languages, url) if languages else None


def detect_programming_language_no_version_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when programming languages or requirements in codemeta.json do not have versions
    (version field is missing or null).
    """
    result = {
        "has_warning": False,
        "file_name": file_name,
        "programming_languages_without_version": [],
        "requirements_without_version": [],
        "source": None
    }

    # 1. Authoritative path: the codemeta file itself.
    from_file = _languages_from_codemeta_file(somef_data)
    if from_file:
        languages, source_url = from_file
        for lang_name, declares_version in languages:
            if declares_version:
                continue
            if _name_contains_version(lang_name):
                continue
            if _is_non_versioned(lang_name):
                continue
            result["programming_languages_without_version"].append(lang_name)
            result["source"] = source_url

        if result["programming_languages_without_version"]:
            result["has_warning"] = True

    # 2. Fallback: SoMEF's own view, used when the file could not be read.
    elif "programming_languages" in somef_data:
        programming_languages_entries = somef_data["programming_languages"]
        if isinstance(programming_languages_entries, list):
            for entry in programming_languages_entries:
                source = entry.get("source", "")
                techniques = _techniques(entry)

                if "code_parser" in techniques and "codemeta.json" in str(source).lower():
                    if "result" in entry:
                        result_data = entry["result"]

                        if "version" not in result_data or result_data.get("version") is None:
                            lang_name = result_data.get("name", "Unknown")

                            if _value_is_list(result_data):
                                continue

                            if isinstance(lang_name, str) and _name_contains_version(lang_name):
                                continue

                            if _is_non_versioned(lang_name):
                                continue

                            result["programming_languages_without_version"].append(lang_name)
                            result["source"] = source
                            result["has_warning"] = True

    if "requirements" in somef_data:
        requirements_entries = somef_data["requirements"]
        if isinstance(requirements_entries, list):
            for entry in requirements_entries:
                source = entry.get("source", "")
                techniques = _techniques(entry)

                if "code_parser" in techniques and "codemeta.json" in str(source).lower():
                    if "result" in entry:
                        result_data = entry["result"]

                        if "version" not in result_data or result_data.get("version") is None:
                            req_name = result_data.get("value", result_data.get("name", "Unknown"))

                            if _is_non_versioned(req_name):
                                continue

                            result["requirements_without_version"].append(req_name)
                            result["source"] = source

    return result
