"""Shared HTTP helpers for rsmetacheck detectors.

Kept dependency-light (only `requests`) so individual detectors can be tested
with the standard `@patch('...pXXX.requests.get')` approach.
"""
import re
import time
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    ),
}

# --- pure classification ---------------------------------------------------

ACCESSIBLE = "accessible"
HARD_FAILURE = "hard_failure"
INCONCLUSIVE = "inconclusive"


def classify_status(status_code: Optional[int], error: Optional[str]) -> str:
    """Classify an HTTP result into accessible / hard_failure / inconclusive.

    Only definitive failures are treated as hard failures (404/410 and DNS /
    connection-refused errors). Transient conditions (rate limiting, server
    errors, timeouts, SSL issues) are inconclusive so detectors do not emit
    false positives when the network flakes.
    """
    if status_code is not None:
        if 200 <= status_code < 400 and status_code != 300:
            return ACCESSIBLE
        if status_code in (404, 410):
            return HARD_FAILURE
        return INCONCLUSIVE
    if error:
        low = error.lower()
        if any(token in low for token in (
                "gaierror", "name or service not known", "getaddrinfo",
                "connectionrefusederror", "errno 111", "connection refused")):
            return HARD_FAILURE
        return INCONCLUSIVE
    return INCONCLUSIVE


def is_hard_failure(status_code: Optional[int], error: Optional[str]) -> bool:
    return classify_status(status_code, error) == HARD_FAILURE


# --- network text fetching (cached) ---------------------------------------

_cache: Dict[str, Optional[str]] = {}


def fetch_text(url: str, timeout: int = 20, retries: int = 1) -> Optional[str]:
    """Fetch a text file over HTTP(S), with an in-memory cache.

    Used to read LICENSE / codemeta.json / pyproject.toml / README from the raw
    source URL recorded in a SoMEF output, so detectors can inspect content that
    SoMEF 0.11.2 no longer embeds in the JSON.
    """
    if not url or not url.startswith(("http://", "https://")):
        return None
    if url in _cache:
        return _cache[url]

    text: Optional[str] = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(url, timeout=timeout, headers=DEFAULT_HEADERS,
                                    allow_redirects=True)
            if response.status_code == 200:
                text = response.text
                break
            if response.status_code == 429 and attempt < retries:
                time.sleep(1 + attempt)
                continue
            break
        except requests.exceptions.RequestException:
            if attempt < retries:
                time.sleep(0.5)
                continue
            break

    _cache[url] = text
    return text


# --- source URL helpers ----------------------------------------------------

def _as_strings(value: Any):
    if isinstance(value, (list, tuple)):
        return [str(x) for x in value]
    return [str(value)]


def is_root_codemeta_url(source: str) -> bool:
    """True if `source` looks like a repository-level (non-nested) codemeta.json.

    A root codemeta source is either a relative path (e.g. ``codemeta.json`` or
    ``repository/codemeta.json``) or a raw GitHub URL with at most
    ``<owner>/<repo>/<ref>/codemeta.json``. Deeply nested or vendored codemetas
    (``.../third_party/.../codemeta.json``, ``.../docs/joss/.../codemeta.json``)
    have more path segments and are ignored by codemeta-based detectors.
    """
    if not source:
        return False
    try:
        parts = [seg for seg in urlparse(str(source)).path.split("/") if seg]
        return parts[-1].lower() == "codemeta.json" and len(parts) <= 4
    except Exception:
        return False


def is_vendored_source(source: str) -> bool:
    """True if the source path points inside a vendored third-party directory."""
    if not source:
        return False
    low = str(source).lower()
    return any(f"/{d}/" in low for d in (
        "third_party", "third-party", "externals", "external", "vendor",
        "subprojects", "deps", "node_modules"))


def find_source_url(somef_data: Dict, target_filename: str,
                    codemeta_root_only: bool = False) -> Optional[str]:
    """Return the first source URL whose path mentions `target_filename`."""
    target = target_filename.lower()
    for value in somef_data.values():
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source")
            if not source:
                continue
            for src in _as_strings(source):
                if not src.startswith(("http://", "https://")):
                    continue
                if target not in src.lower():
                    continue
                if codemeta_root_only and not is_root_codemeta_url(src):
                    continue
                return src
    return None


_RAW_GITHUB_RE = re.compile(r'^https?://raw\.githubusercontent\.com/([^/]+)/([^/]+)/([^/]+)/')

LICENSE_FILENAMES = [
    "LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE", "LICENCE.md",
    "LICENCE.txt", "COPYING", "COPYING.md", "COPYING.txt", "COPYRIGHT",
    "LICENSE.rst", "COPYING.LESSER",
]


def find_repo_root_url(somef_data: Dict) -> Optional[str]:
    """Derive the repository root URL at the analyzed ref from any SoMEF source.

    For a pinned run the ref is the recorded commit SHA, so probing files under
    this root stays at the same revision (no drift).
    """
    for value in somef_data.values():
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            source = entry.get("source")
            if not source:
                continue
            for src in _as_strings(source):
                if not src.startswith(("http://", "https://")):
                    continue
                m = _RAW_GITHUB_RE.match(src)
                if m:
                    return f"https://raw.githubusercontent.com/{m.group(1)}/{m.group(2)}/{m.group(3)}/"
                if "/-/raw/" in src:
                    pre, rest = src.split("/-/raw/", 1)
                    ref = rest.split("/", 1)[0]
                    if ref:
                        return f"{pre}/-/raw/{ref}/"
    return None


def fetch_license_file(somef_data: Dict) -> Tuple[Optional[str], Optional[str]]:
    """Probe the repository root for a license file and return (url, text).

    Used when SoMEF merged/normalized the license entries and dropped the
    LICENSE/COPYING file source (so no entry points at the file itself).
    Returns (None, None) when nothing is found.
    """
    root = find_repo_root_url(somef_data)
    if not root:
        return None, None
    for filename in LICENSE_FILENAMES:
        url = root + filename
        text = fetch_text(url)
        if text and text.strip():
            return url, text
    return None, None
