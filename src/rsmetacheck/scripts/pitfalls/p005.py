from typing import Dict
import re

def is_software_archive_url(url: str) -> bool:
    """
    Check if URL points to a software archive instead of a research paper.
    """
    if not url or not isinstance(url, str):
        return False

    url = url.lower().strip()

    # Patterns that indicate software archives
    software_archive_patterns = [
        r'zenodo\.org',  # Zenodo software archives
        r'figshare\.com',  # Figshare software archives
        r'github\.com/.*/releases',  # GitHub releases
        r'sourceforge\.net',  # SourceForge
        r'archive\.org',  # Internet Archive
        r'codeocean\.com',  # CodeOcean
        r'osf\.io',  # Open Science Framework (when used for software)
        r'doi\.org/10\.5281',  # Zenodo DOIs
        r'10\.5281/zenodo\.',  # bare Zenodo DOI (10.5281/zenodo.xxx)
    ]

    for pattern in software_archive_patterns:
        if re.search(pattern, url):
            return True

    return False


def detect_reference_publication_archive_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when codemeta.json referencePublication refers to software archive instead of paper.

    SoMEF 0.11.2 stores the codemeta.json ``referencePublication`` value under the
    ``citation`` category (there is no ``reference_publication`` key in the output),
    so this detector reads ``citation`` entries sourced from codemeta.json.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "reference_url": None,
        "source": None,
        "is_software_archive": False
    }

    citation_entries = somef_data.get("citation")
    if not isinstance(citation_entries, list):
        citation_entries = []

    legacy_entries = somef_data.get("reference_publication")
    if isinstance(legacy_entries, list):
        citation_entries = citation_entries + legacy_entries

    for entry in citation_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")
        source_str = str(source)

        if "codemeta.json" in source_str.lower() or (
                technique == "code_parser" and "codemeta" in source_str.lower()):
            result_data = entry.get("result") or {}
            ref_url = result_data.get("value") or result_data.get("url") or result_data.get("doi")

            if isinstance(ref_url, str) and is_software_archive_url(ref_url):
                result["has_pitfall"] = True
                result["reference_url"] = ref_url
                result["source"] = source
                result["is_software_archive"] = True
                break

    return result