from typing import Dict
import time
from urllib.parse import urlparse

import requests

from rsmetacheck.utils.fetch_utils import classify_status, HARD_FAILURE


def is_valid_issue_tracker_format(url: str) -> bool:
    """
    Check if URL matches a recognized issue tracker format.
    Validates that the URL has a proper scheme, hostname, and
    a path ending in a recognized issue tracker pattern (/issues, /tickets).
    """
    if not url:
        return False

    try:
        parsed = urlparse(url.strip())
    except Exception:
        return False

    if parsed.scheme not in ('http', 'https'):
        return False

    if not parsed.netloc:
        return False

    path = parsed.path
    if not path or path == '/':
        return False

    path_lower = path.lower()
    valid_patterns = ['/issues', '/tickets']
    for pattern in valid_patterns:
        if path_lower.endswith(pattern) or (pattern + '/') in path_lower:
            return True

    return False


def _is_unreachable(url: str, timeout: int = 10) -> Dict:
    """Return status/error for an issue tracker URL (only hard failures matter)."""
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
    return {
        "status_code": status_code,
        "error": error,
        "verdict": classify_status(status_code, error),
    }


def detect_issue_tracker_format_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when codemeta.json IssueTracker URL does not follow a recognized
    format, or is a dead link (404/410/unresolvable host).
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "issue_url": None,
        "source": None,
        "format_violation": None,
        "status_code": None,
        "error": None,
    }

    if "issue_tracker" not in somef_data:
        return result

    issues_entries = somef_data["issue_tracker"]
    if not isinstance(issues_entries, list):
        return result

    for entry in issues_entries:
        source = entry.get("source", "")
        technique = entry.get("technique", "")

        if "codemeta.json" in source or (technique == "code_parser" and "codemeta" in source.lower()):
            if "result" in entry and "value" in entry["result"]:
                issue_url = entry["result"]["value"]

                if not is_valid_issue_tracker_format(issue_url):
                    result["has_pitfall"] = True
                    result["issue_url"] = issue_url
                    result["source"] = source
                    result["format_violation"] = "URL does not match recognized issue tracker format"
                    break

                url_status = _is_unreachable(issue_url)
                if url_status.get("verdict") == HARD_FAILURE:
                    result["has_pitfall"] = True
                    result["issue_url"] = issue_url
                    result["source"] = source
                    result["status_code"] = url_status["status_code"]
                    result["error"] = url_status["error"]
                    result["format_violation"] = "Issue tracker URL is not reachable"
                    break

    return result