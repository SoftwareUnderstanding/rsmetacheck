from typing import Dict
import requests
import re
import time
from urllib.parse import urlparse
from rsmetacheck.utils.pitfall_utils import extract_metadata_source_filename
from rsmetacheck.utils.fetch_utils import classify_status, HARD_FAILURE


def is_valid_url_format(url: str) -> bool:
    """
    Check if URL has a valid format.
    """
    if url is None:
        raise ValueError("URL cannot be None")

    if not url or not isinstance(url, str):
        return False

    if url.startswith(('git+', 'git://', 'svn+', 'hg+', 'bzr+')):
        return True

    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


def check_url_status(url: str, timeout: int = 10) -> Dict:
    """
    Check if URL returns a valid response.

    Only definitive failures (404/410 and DNS/connection errors) are treated as
    invalid; transient failures (rate limiting, timeouts, server errors) are
    marked inconclusive so the detector does not produce false positives.
    """
    result = {
        "is_accessible": False,
        "status_code": None,
        "error": None,
        "verdict": "inconclusive",
    }

    if not is_valid_url_format(url):
        result["error"] = "Invalid URL format"
        result["verdict"] = HARD_FAILURE
        return result

    if url.startswith(('git+', 'git://', 'svn+', 'hg+', 'bzr+')):
        result["is_accessible"] = True
        result["status_code"] = 200
        result["verdict"] = "accessible"
        return result

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    status_code = None
    error = None
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=timeout, headers=headers, allow_redirects=True)
            status_code = response.status_code
            error = None
            if status_code == 429 and attempt < 2:
                time.sleep(1 + attempt)
                continue
            break
        except requests.exceptions.RequestException as e:
            status_code = None
            error = str(e)
            if attempt < 2:
                time.sleep(0.5)
                continue
            break
        except Exception as e:
            status_code = None
            error = f"Unexpected error: {str(e)}"
            break

    result["status_code"] = status_code
    result["error"] = error
    result["verdict"] = classify_status(status_code, error)
    result["is_accessible"] = result["verdict"] == "accessible"

    return result


def _is_invalid_url(url_status: Dict) -> bool:
    """True if a URL is definitively invalid (hard failure).

    Accepts both the new status dict (with a ``verdict``) and the legacy shape
    (only ``status_code``/``error``) produced by older test doubles.
    """
    verdict = url_status.get("verdict")
    if verdict:
        return verdict == HARD_FAILURE
    if url_status.get("status_code") in (404, 410):
        return True
    error = url_status.get("error")
    return isinstance(error, str) and "Invalid URL format" in error


def extract_urls_from_requirements(requirement_text: str) -> list:
    """
    Extract URLs from software requirement text.
    """
    if not requirement_text:
        return []

    url_patterns = [
        r'https?://[^\s<>"\']+',  # HTTP/HTTPS URLs
        r'www\.[^\s<>"\']+',  # URLs starting with www
    ]

    urls = []
    for pattern in url_patterns:
        matches = re.findall(pattern, requirement_text, re.IGNORECASE)
        urls.extend(matches)

    cleaned_urls = []
    for url in urls:
        url = re.sub(r'[,;.!?)]$', '', url)
        if url:
            cleaned_urls.append(url)

    return cleaned_urls


def detect_invalid_software_requirement_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when metadata files have software requirements pointing to invalid pages.
    Checks all metadata sources and collects all affected files.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "invalid_urls": [],
        "source": None,
        "metadata_source_file": None,
        "metadata_source_files": [],
        "requirement_text": None
    }

    if "requirements" not in somef_data:
        return result

    req_entries = somef_data["requirements"]
    if not isinstance(req_entries, list):
        return result

    metadata_sources = ["codemeta.json", "description", "composer.json", "package.json", "pom.xml", "pyproject.toml",
                        "requirements.txt", "setup.py"]

    for entry in req_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")

        is_metadata_source = (
                technique == "code_parser" and
                any(src in source.lower() for src in metadata_sources)
        )

        if is_metadata_source:
            if "result" in entry and "value" in entry["result"]:
                req_value = entry["result"]["value"]

                if isinstance(req_value, str) and is_valid_url_format(req_value):
                    url_status = check_url_status(req_value)

                    if _is_invalid_url(url_status):
                        source_filename = extract_metadata_source_filename(source)
                        if result["source"] is None:
                            result["source"] = source
                            result["metadata_source_file"] = source_filename
                            result["requirement_text"] = req_value
                        result["invalid_urls"].append({
                            "url": req_value,
                            "status_code": url_status["status_code"],
                            "error": url_status["error"]
                        })
                        result["metadata_source_files"].append(source_filename)
                        result["has_pitfall"] = True
                else:
                    requirement_text = ""
                    if isinstance(req_value, str):
                        requirement_text = req_value
                    elif isinstance(req_value, list):
                        requirement_text = " ".join(str(item) for item in req_value)
                    elif isinstance(req_value, dict):
                        for key in ["name", "value", "description", "text"]:
                            if key in req_value:
                                requirement_text += str(req_value[key]) + " "

                    if requirement_text:
                        urls = extract_urls_from_requirements(requirement_text)

                        if urls:
                            invalid_urls = []

                            for url in urls:
                                url_status = check_url_status(url)

                                if _is_invalid_url(url_status):
                                    invalid_urls.append({
                                        "url": url,
                                        "status_code": url_status["status_code"],
                                        "error": url_status["error"]
                                    })

                            if invalid_urls:
                                source_filename = extract_metadata_source_filename(source)
                                if result["source"] is None:
                                    result["source"] = source
                                    result["metadata_source_file"] = source_filename
                                    result["requirement_text"] = requirement_text
                                result["invalid_urls"].extend(invalid_urls)
                                result["metadata_source_files"].append(source_filename)
                                result["has_pitfall"] = True

    return result