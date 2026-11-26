import re
import subprocess
from typing import Dict, Optional

from rsmetacheck.utils.pitfall_utils import extract_metadata_source_filename

# --- syntactic signals -------------------------------------------------------

# Extra repository shapes beyond the classic forge hosts. `git+`/`ssh://`/`git@`
# remotes and a `/-/` UI path are unambiguous repository markers, whatever the
# host is (self-hosted GitLab/Gitea/Forgejo included).
_FORGE_HINTS = (
    "git+",
    "git://",
    "ssh://",
    "git@",
    "codeberg.org/",
    "gitee.com/",
    "sr.ht/",
    "/-/",
)

_BARE_HOST_RE = re.compile(r'^https?://[^/\s]+/?$')

# How long the git probe may take before we call the answer inconclusive.
_PROBE_TIMEOUT = 8
_probe_cache: Dict[str, str] = {}


def is_repository_url(url: str) -> bool:
    """
    Check if URL appears to be a code repository rather than homepage.
    """
    if not url:
        return False

    url_lower = url.lower()

    if 'github.io' in url_lower:
        return False

    repo_indicators = [
        'github.com/',
        'github.org/',
        'gitlab.com/',
        'gitlab.org/',
        'bitbucket.org/',
        'bitbucket.net/',
        'sourceforge.net/projects/',
        'git.',
        '.git'
    ]

    for indicator in repo_indicators:
        if indicator in url_lower:
            return True

    return False


def is_homepage_url_repo(url: str) -> bool:
    """
    Check if URL appears to be a homepage rather than code repository.
    """
    if not url:
        return False

    url_lower = url.lower()

    if is_repository_url(url):
        return False

    homepage_indicators = [
        '.org/',
        '.com/',
        '.net/',
        '.io/',
        'www.',
        'docs.',
        'documentation',
        'readthedocs',
        'github.io'
    ]

    for indicator in homepage_indicators:
        if indicator in url_lower:
            return True

    return False


def _strip_git_prefix(url: str) -> str:
    return url[4:] if url.lower().startswith("git+") else url


def _looks_like_forge(url: str) -> bool:
    low = url.lower()
    if any(hint in low for hint in _FORGE_HINTS):
        return True
    return low.rstrip("/").endswith(".git")


def _looks_like_bare_homepage(url: str) -> bool:
    """A bare host with no path (e.g. https://opensim.stanford.edu/) is a homepage."""
    return bool(_BARE_HOST_RE.match(url.strip()))


def _probe_git(url: str) -> str:
    """Ask the URL itself whether it is a git repository.

    Returns 'repo', 'not_repo' or 'unreachable'. Only http(s) URLs are probed;
    anything else is treated as inconclusive. Results are cached per process
    because the same URL tends to appear in several metadata entries.
    """
    target = _strip_git_prefix(url.strip())
    if not target.lower().startswith(("http://", "https://")):
        return "unreachable"
    if target in _probe_cache:
        return _probe_cache[target]

    try:
        run = subprocess.run(
            ["git", "ls-remote", "--heads", "--tags", target],
            capture_output=True, text=True, timeout=_PROBE_TIMEOUT,
        )
        if run.returncode == 0:
            verdict = "repo"
        else:
            error = (run.stderr or "").lower()
            unreachable_markers = (
                "connection reset", "could not resolve", "connection refused",
                "timed out", "network is unreachable", "no route to host",
                "temporary failure in name resolution", "unable to access",
                "ssl", "failed to connect",
            )
            verdict = "unreachable" if any(m in error for m in unreachable_markers) else "not_repo"
    except subprocess.TimeoutExpired:
        verdict = "unreachable"
    except Exception:  # noqa: BLE001 - any probe failure is inconclusive
        verdict = "unreachable"

    _probe_cache[target] = verdict
    return verdict


def classify_repository_url(url: str) -> str:
    """Classify a single URL as 'repo', 'homepage' or 'inconclusive'.

    Positive evidence only: a URL is reported as a homepage when it matches a
    homepage shape or when the git probe answers definitively that it is not a
    repository. An unreachable host is inconclusive, never a finding.
    """
    if not isinstance(url, str) or not url.strip():
        return "inconclusive"
    url = url.strip()

    if is_repository_url(url) or _looks_like_forge(url):
        return "repo"
    if is_homepage_url_repo(url) or _looks_like_bare_homepage(url):
        return "homepage"

    verdict = _probe_git(url)
    if verdict == "repo":
        return "repo"
    if verdict == "not_repo":
        return "homepage"
    return "inconclusive"


def classify_repository_value(value: str) -> str:
    """Classify a codeRepository value that may hold several whitespace-joined URLs."""
    if not isinstance(value, str):
        return "inconclusive"
    urls = [u for u in re.split(r'\s+', value.strip()) if u]
    if not urls:
        return "inconclusive"

    verdicts = [classify_repository_url(u) for u in urls]
    if "repo" in verdicts:
        return "repo"
    if "homepage" in verdicts:
        return "homepage"
    return "inconclusive"


def value_contains_repository_url(value: str) -> bool:
    """Backwards-compatible helper: True when the value holds a repository URL."""
    return classify_repository_value(value) == "repo"


def detect_coderepository_homepage_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when code repository in metadata files points to homepage instead of repository.
    Checks all metadata sources and collects all affected files.

    A URL is only reported when there is positive evidence that it is a homepage:
    a homepage shape, or a git probe answering that it is not a repository.
    Unreachable URLs are inconclusive and never produce a finding.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "repository_url": None,
        "source": None,
        "metadata_source_file": None,
        "metadata_source_files": [],
        "is_homepage": False,
        "inconclusive": False
    }

    if "code_repository" not in somef_data:
        return result

    repo_entries = somef_data["code_repository"]
    if not isinstance(repo_entries, list):
        return result

    metadata_sources = ["codemeta.json", "DESCRIPTION", "composer.json", "package.json",
                        "pom.xml", "pyproject.toml", "requirements.txt", "setup.py"]

    for entry in repo_entries:
        technique = entry.get("technique", "")
        source = entry.get("source", "")

        is_metadata_source = (
            technique == "code_parser" or
            technique in metadata_sources or
            any(src in str(source).lower() for src in metadata_sources)
        )

        if not is_metadata_source:
            continue
        if "result" not in entry or "value" not in entry["result"]:
            continue

        repo_url = entry["result"]["value"]
        verdict = classify_repository_value(repo_url)

        if verdict == "homepage":
            source_filename = extract_metadata_source_filename(source)
            if result["repository_url"] is None:
                result["repository_url"] = repo_url
                result["source"] = source if source else f"technique: {technique}"
                result["metadata_source_file"] = source_filename
            result["metadata_source_files"].append(source_filename)
            result["has_pitfall"] = True
            result["is_homepage"] = True
        elif verdict == "inconclusive":
            result["inconclusive"] = True

    return result
