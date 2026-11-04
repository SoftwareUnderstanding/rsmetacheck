from typing import Dict
import re


def extract_version_from_download_url(url: str) -> str:
    """
    Extract version number from download URL.
    """
    if not url:
        return None

    # Common version patterns in download URLs
    version_patterns = [
        r'/archive/(?:v)?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9\-\.]*)?)\.',  # /archive/3.8.0. or /archive/v1.2.3.
        r'/archive/(?:v)?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9\-\.]*)?)$',
        # /archive/3.8.0 or /archive/v1.2.3 (end of string)
        r'/refs/tags/(?:v)?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9\-\.]*)?)',  # /archive/refs/tags/v1.2.3.zip
        r'/releases/tag/(?:[^/]*?[-_])?(?:v)?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9\-\.]*)?)$',  # /releases/tag/name-1.2.3
        r'[-_](?:v)?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9\-\.]*)?)\.',  # -3.8.0.tar.gz or _v1.2.3.zip
        r'/(?:v)?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9\-\.]*)?)/[^/]*$',  # /3.8.0/something
    ]

    for pattern in version_patterns:
        match = re.search(pattern, url)
        if match:
            version = match.group(1)
            # Remove any trailing file extension artifacts
            # This handles cases where .tar, .zip etc might be captured
            version = re.sub(r'\.(tar|gz|zip|bz2|xz|tgz).*$', '', version)
            return version

    return None


def normalize_version(version: str) -> str:
    """
    Normalize version string for comparison by removing 'v' prefix and standardizing format.
    """
    if not version:
        return None

    normalized = version.strip()

    if not normalized:
        return None

    normalized = normalized.lower()
    if normalized.startswith('v'):
        normalized = normalized[1:]

    return normalized if normalized else None


def get_latest_release_version(somef_data: Dict) -> str:
    """
    Get the latest release version from releases data.
    """
    if "releases" not in somef_data:
        return None

    releases = somef_data["releases"]
    if not isinstance(releases, list) or not releases:
        return None

    latest_release = releases[0]
    if "result" in latest_release:
        result = latest_release["result"]

        if "tag" in result and result["tag"]:
            tag = result["tag"].strip()
            if tag:
                version_match = re.search(r'(?:v)?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9\-\.]*)?)', tag)
                if version_match:
                    return normalize_version(version_match.group(1))

        if "name" in result and result["name"]:
            name = result["name"]
            version_match = re.search(r'(?:v)?(\d+\.\d+(?:\.\d+)?(?:[a-zA-Z0-9\-\.]*)?)', name)
            if version_match:
                return normalize_version(version_match.group(1))

    return None


def detect_outdated_download_url_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when codemeta.json downloadURL is outdated compared to latest release.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "download_url": None,
        "download_version": None,
        "latest_release_version": None,
        "source": None
    }

    if "download_url" not in somef_data:
        return result

    download_entries = somef_data["download_url"]
    if not isinstance(download_entries, list):
        return result

    codemeta_download_url = None
    codemeta_source = None

    for entry in download_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")

        if ("codemeta.json" in source.lower() or
                (technique == "code_parser" and "codemeta" in source.lower())):
            if "result" in entry and "value" in entry["result"]:
                codemeta_download_url = entry["result"]["value"]
                codemeta_source = source
                break

    if not codemeta_download_url:
        return result

    download_version = extract_version_from_download_url(codemeta_download_url)
    if not download_version:
        return result

    normalized_download_version = normalize_version(download_version)
    if not normalized_download_version:
        return result

    latest_version = get_latest_release_version(somef_data)
    if not latest_version:
        return result

    normalized_latest_version = normalize_version(latest_version)
    if not normalized_latest_version:
        return result

    if normalized_download_version != normalized_latest_version:
        result["has_pitfall"] = True
        result["download_url"] = codemeta_download_url
        result["download_version"] = download_version
        result["latest_release_version"] = latest_version
        result["source"] = codemeta_source

    return result