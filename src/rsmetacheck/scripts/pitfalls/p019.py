import json
import re
from typing import Dict, List, Tuple

from rsmetacheck.utils.pitfall_utils import extract_metadata_source_filename
from rsmetacheck.utils.fetch_utils import find_source_url, fetch_text

# Only these files are metadata sources for P019 (AUTHORS/Dockerfile/etc. are not).
METADATA_AUTHOR_SOURCES = {
    "codemeta.json", "description", "setup.py", "setup.cfg", "package.json",
    "pyproject.toml", "pom.xml", "requirements.txt", "citation.cff",
    "cargo.toml", "composer.json", "bower.json",
}

# Deposit records are not package manifests. SoMEF >= 0.11.5 parses a root
# .zenodo.json and emits its authors with technique code_parser; counting them
# here would report a false author-count inconsistency against the manifest.
EXCLUDED_AUTHOR_SOURCES = {"zenodo.json", ".zenodo.json", "zenodo_deposit.json"}


def extract_authors_from_somef(somef_data: Dict) -> List[Dict[str, any]]:
    """
    Extract author counts grouped by metadata source file.

    SoMEF 0.11.2 emits one entry per author (each with a dict result), so the
    author count for a given source file is the number of entries pointing at
    that file. Aggregating by source file (rather than counting per entry)
    makes "codemeta.json has 37 authors vs setup.py has 1" detectable.
    """
    if "author" not in somef_data:
        return []

    author_entries = somef_data["author"]
    if not isinstance(author_entries, list):
        return []

    grouped = {}
    order = []

    for entry in author_entries:
        if "source" not in entry or "result" not in entry:
            continue

        source = entry["source"]
        result = entry["result"]

        if isinstance(result, list):
            if not result:
                continue
            identifiers = [get_author_identifier(author) for author in result]
        elif isinstance(result, (dict, str)):
            identifiers = [get_author_identifier(result)]
        else:
            continue

        source_file = extract_metadata_source_filename(source)
        if source_file in grouped:
            grouped[source_file]["authors"].extend(identifiers)
            grouped[source_file]["author_count"] += len(identifiers)
        else:
            grouped[source_file] = {
                "source": source,
                "source_file": source_file,
                "author_count": len(identifiers),
                "authors": identifiers,
            }
            order.append(source_file)

    return [grouped[source_file] for source_file in order]


def get_author_identifier(author: any) -> str:
    """
    Extract a string identifier for an author from various formats.
    """
    if isinstance(author, str):
        return author.strip()
    elif isinstance(author, dict):
        if "name" in author:
            return str(author["name"]).strip()
        elif "value" in author:
            return str(author["value"]).strip()
        elif "email" in author:
            return str(author["email"]).strip()
        else:
            return str(author)
    else:
        return str(author)


def _fetch_setup_py_authors(somef_data: Dict) -> Tuple[int, List[str]]:
    """Read the author(s) from setup.py (SoMEF often misses setuptools.setup)."""
    url = find_source_url(somef_data, "setup.py")
    if not url:
        return 0, []
    text = fetch_text(url)
    if not text:
        return 0, []
    match = re.search(r'(?:^|\n)\s*author\s*=\s*["\']([^"\']+)["\']', text)
    if not match:
        return 0, []
    value = match.group(1)
    parts = [p.strip() for p in re.split(r'\s*(?:,|;|\band\b|\s&\s)\s*', value) if p.strip()]
    return len(parts), parts


def _fetch_description_authors(somef_data: Dict) -> Tuple[int, List[str]]:
    """Read Authors@R from an R DESCRIPTION file."""
    url = find_source_url(somef_data, "DESCRIPTION")
    if not url:
        return 0, []
    text = fetch_text(url)
    if not text:
        return 0, []
    names = re.findall(r'person\s*\(\s*["\']([^"\']+)["\']', text)
    count = len(re.findall(r'\bperson\s*\(', text))
    if count == 0:
        return 0, []
    return count, names


def _fetch_package_json_authors(somef_data: Dict) -> Tuple[int, List[str]]:
    """Read the author(s) from package.json."""
    url = find_source_url(somef_data, "package.json")
    if not url:
        return 0, []
    text = fetch_text(url)
    if not text:
        return 0, []
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return 0, []
    author = data.get("author") or data.get("authors")
    if isinstance(author, list):
        authors = [(x.get("name") if isinstance(x, dict) else str(x)) for x in author]
        return len(authors), authors
    if isinstance(author, dict):
        return 1, [str(author.get("name", ""))]
    if isinstance(author, str):
        return 1, [author]
    return 0, []


def find_author_count_inconsistencies(author_sources: List[Dict]) -> Tuple[bool, List[Dict]]:
    """
    Check if there are inconsistencies in author counts across different sources.
    Returns (has_inconsistency, inconsistency_details).
    """
    if len(author_sources) < 2:
        return False, []

    counts = {}
    for source_info in author_sources:
        count = source_info["author_count"]
        if count not in counts:
            counts[count] = []
        counts[count].append(source_info)

    if len(counts) <= 1:
        return False, []

    inconsistencies = []
    sorted_counts = sorted(counts.keys())

    for i in range(len(sorted_counts)):
        lower_count = sorted_counts[i]
        for j in range(i + 1, len(sorted_counts)):
            higher_count = sorted_counts[j]

            for lower_source in counts[lower_count]:
                for higher_source in counts[higher_count]:
                    inconsistencies.append({
                        "source_with_fewer": lower_source["source_file"],
                        "source_with_fewer_full": lower_source["source"],
                        "fewer_count": lower_count,
                        "fewer_authors": lower_source["authors"],
                        "source_with_more": higher_source["source_file"],
                        "source_with_more_full": higher_source["source"],
                        "more_count": higher_count,
                        "more_authors": higher_source["authors"],
                        "difference": higher_count - lower_count
                    })

    return len(inconsistencies) > 0, inconsistencies


def detect_inconsistent_author_count(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect inconsistent author counts across different metadata files.
    Returns detection result with warning info.
    """
    result = {
        "has_warning": False,
        "file_name": file_name,
        "author_sources": [],
        "inconsistencies": [],
        "total_sources": 0,
        "min_author_count": 0,
        "max_author_count": 0
    }

    author_sources = [
        src for src in extract_authors_from_somef(somef_data)
        if src["source_file"].lower() in METADATA_AUTHOR_SOURCES
        and src["source_file"].lower() not in EXCLUDED_AUTHOR_SOURCES
    ]

    # SoMEF 0.11.2 often does not extract setup.py/package.json authors; read
    # those files directly when they are present in the repository.
    existing_files = {s["source_file"].lower() for s in author_sources}
    for src_file, fetcher in (("setup.py", _fetch_setup_py_authors),
                              ("package.json", _fetch_package_json_authors),
                              ("description", _fetch_description_authors)):
        if src_file in existing_files:
            continue
        count, authors = fetcher(somef_data)
        if count and count > 0:
            author_sources.append({
                "source": src_file,
                "source_file": src_file,
                "author_count": count,
                "authors": authors,
            })
            existing_files.add(src_file)

    if not author_sources:
        return result

    result["author_sources"] = author_sources
    result["total_sources"] = len(author_sources)

    counts = [src["author_count"] for src in author_sources]
    result["min_author_count"] = min(counts)
    result["max_author_count"] = max(counts)

    has_inconsistency, inconsistencies = find_author_count_inconsistencies(author_sources)

    if has_inconsistency:
        result["has_warning"] = True
        result["inconsistencies"] = inconsistencies

    return result
