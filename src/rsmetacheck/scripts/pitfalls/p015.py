from typing import Dict
import json
import os
import time
from urllib.parse import urlparse, quote

import requests

from rsmetacheck.utils.fetch_utils import classify_status, HARD_FAILURE, find_source_url, fetch_text

GITHUB_HOSTS = {"github.com", "www.github.com"}
_TOKEN_ENV_VARS = ("GITHUB_API_TOKEN", "GITHUB_TOKEN", "GH_TOKEN")


def is_valid_url_format(url: str) -> bool:
    """
    Check if URL has a valid format.
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False


# ---------------------------------------------------------------- GitHub API path
#
# GitHub serves /actions/... as a client-side route: the HTML page answers 200
# even when the workflow file does not exist, so an HTTP check cannot tell a
# live CI link from a dead one. GitHub-hosted Actions URLs are therefore
# resolved through the REST API, which answers 404 for a missing workflow.

def parse_github_actions_url(url: str):
    """
    Describe the GitHub Actions target behind a URL, or return None when the URL
    is not a GitHub Actions link.

    Supported shapes:
      /{owner}/{repo}/actions/workflows/{file}
      /{owner}/{repo}/actions
      /{owner}/{repo}/workflows/{file}/badge.svg
      /{owner}/{repo}/blob/{ref}/.github/workflows/{file}
      /{owner}/{repo}/tree/{ref}/.github/workflows
    """
    if not url or not isinstance(url, str):
        return None
    try:
        parsed = urlparse(url.strip())
    except Exception:
        return None
    if parsed.netloc.lower() not in GITHUB_HOSTS:
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        return None
    owner, repo, rest = parts[0], parts[1], parts[2:]

    if rest[:2] == ["actions", "workflows"]:
        if len(rest) >= 3:
            return {"kind": "workflow_file", "owner": owner, "repo": repo, "file": rest[2]}
        return {"kind": "actions_list", "owner": owner, "repo": repo}

    if rest[:1] == ["actions"]:
        return {"kind": "actions_list", "owner": owner, "repo": repo}

    if rest[:1] == ["workflows"] and len(rest) >= 3 and rest[2].startswith("badge"):
        return {"kind": "workflow_file", "owner": owner, "repo": repo,
                "file": rest[1], "badge": True}

    # /blob/<ref>/.github/workflows[/<file>]  and  /tree/<ref>/.github/workflows
    if rest[:1] in (["blob"], ["tree"]) and len(rest) >= 4 and rest[2:4] == [".github", "workflows"]:
        kind = "workflow_blob" if rest[0] == "blob" else "tree_workflows"
        target = {"kind": kind, "owner": owner, "repo": repo, "ref": rest[1]}
        if len(rest) >= 5:
            target["file"] = "/".join(rest[4:])
        return target

    return None


def _github_token():
    """Token for API calls, conventional env vars first (the bot sets GITHUB_API_TOKEN)."""
    for var in _TOKEN_ENV_VARS:
        value = os.environ.get(var)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _safe_json(response):
    try:
        data = response.json()
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _github_api_get(path: str, timeout: int = 10) -> Dict:
    """GET api.github.com{path}; never raises, returns status/payload/error."""
    url = "https://api.github.com" + path
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = _github_token()
    if token:
        headers["Authorization"] = f"token {token}"

    status_code = None
    error = None
    for attempt in range(3):
        try:
            response = requests.get(url, headers=headers, timeout=timeout)
            status_code = response.status_code
            error = None
            if status_code == 429 and attempt < 2:
                time.sleep(1 + attempt)
                continue
            return {"status_code": status_code, "payload": _safe_json(response), "error": None}
        except requests.exceptions.RequestException as exc:
            status_code = None
            error = str(exc)
            if attempt < 2:
                time.sleep(0.5)
                continue
            break
        except Exception as exc:  # noqa: BLE001 - defers to inconclusive
            status_code = None
            error = f"Unexpected error: {exc}"
            break
    return {"status_code": status_code, "payload": None, "error": error}


def check_github_ci_status(url: str, timeout: int = 10) -> Dict:
    """
    Resolve a GitHub Actions CI URL through the REST API.

    hard_failure only when the API states the workflow does not exist while the
    repository itself is readable; a private/missing repository or a rate limit
    stays inconclusive so the check cannot blame CI for an access problem.
    """
    result = {
        "is_accessible": False,
        "status_code": None,
        "error": None,
        "verdict": "inconclusive",
        "check_method": "github_api",
        "api_status": None,
        "repo_status": None,
        "workflow_state": None,
        "target": None,
    }

    target = parse_github_actions_url(url)
    if target is None:
        result["error"] = "Not a GitHub Actions URL"
        return result

    result["target"] = target
    owner, repo = target["owner"], target["repo"]

    def repo_readable() -> bool:
        probe = _github_api_get(f"/repos/{owner}/{repo}", timeout=timeout)
        result["repo_status"] = probe["status_code"]
        return probe["status_code"] == 200

    def hard_failure(message: str, status_code=None):
        result["verdict"] = HARD_FAILURE
        result["status_code"] = status_code
        result["error"] = message
        return result

    def accessible(state=None):
        result["verdict"] = "accessible"
        result["is_accessible"] = True
        if state is not None:
            result["workflow_state"] = state
        return result

    kind = target["kind"]

    if kind == "workflow_file":
        file_name = target["file"]
        response = _github_api_get(
            f"/repos/{owner}/{repo}/actions/workflows/{quote(file_name, safe='')}", timeout=timeout)
        result["api_status"] = response["status_code"]
        if response["status_code"] == 200:
            return accessible((response["payload"] or {}).get("state"))
        if response["status_code"] in (404, 410):
            if repo_readable():
                return hard_failure(
                    f"workflow '{file_name}' does not exist in {owner}/{repo}",
                    response["status_code"])
            return result  # repository missing or private: not CI's fault
        if response["status_code"] in (401, 403, 429):
            result["error"] = "GitHub API rate limited or unauthorised"
            return result
        result["error"] = response["error"]
        return result

    if kind == "workflow_blob":
        file_name = target.get("file")
        path = f"/repos/{owner}/{repo}/contents/.github/workflows"
        if file_name:
            path += "/" + quote(file_name, safe="/")
        query = f"?ref={quote(target['ref'], safe='')}" if target.get("ref") else ""
        response = _github_api_get(path + query, timeout=timeout)
        result["api_status"] = response["status_code"]
        if response["status_code"] == 200:
            return accessible()
        if response["status_code"] in (404, 410):
            if repo_readable():
                return hard_failure(
                    f"workflow path '{file_name or '.github/workflows'}' does not exist on ref "
                    f"'{target.get('ref')}'", response["status_code"])
            return result
        result["error"] = response["error"]
        return result

    if kind == "tree_workflows":
        query = f"?ref={quote(target['ref'], safe='')}" if target.get("ref") else ""
        response = _github_api_get(
            f"/repos/{owner}/{repo}/contents/.github/workflows{query}", timeout=timeout)
        result["api_status"] = response["status_code"]
        if response["status_code"] == 200:
            payload = response["payload"]
            entries = payload if isinstance(payload, list) else None
            if entries is not None and len(entries) == 0:
                return hard_failure("no workflows present in .github/workflows", 200)
            return accessible()
        if response["status_code"] in (404, 410) and repo_readable():
            return hard_failure("'.github/workflows' does not exist in the repository",
                                response["status_code"])
        result["error"] = response["error"]
        return result

    # actions_list: the repository Actions page itself
    response = _github_api_get(f"/repos/{owner}/{repo}/actions/workflows", timeout=timeout)
    result["api_status"] = response["status_code"]
    if response["status_code"] == 200:
        total = (response["payload"] or {}).get("total_count")
        if isinstance(total, int) and total == 0:
            return hard_failure("repository has no workflows configured", 200)
        return accessible()
    if response["status_code"] in (404, 410) and repo_readable():
        return hard_failure("repository has no Actions enabled", response["status_code"])
    result["error"] = response["error"]
    return result


# ---------------------------------------------------------------- HTTP path

def _check_ci_url_status_html(url: str, timeout: int = 10) -> Dict:
    """
    Check a non-GitHub CI URL over HTTP.

    Only definitive failures (404/410/DNS/refused) are treated as unreachable;
    transient errors are inconclusive to avoid false positives.
    """
    result = {
        "is_accessible": False,
        "status_code": None,
        "error": None,
        "verdict": "inconclusive",
        "check_method": "http",
    }

    if not is_valid_url_format(url):
        result["error"] = "Invalid URL format"
        result["verdict"] = HARD_FAILURE
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


def check_ci_url_status(url: str, timeout: int = 10) -> Dict:
    """
    Check a CI URL. GitHub Actions links go through the REST API (HTML always
    answers 200 for /actions/...); everything else falls back to HTTP.
    """
    if parse_github_actions_url(url) is not None:
        return check_github_ci_status(url, timeout)
    return _check_ci_url_status_html(url, timeout)


def _is_unreachable(url_status: Dict) -> bool:
    """True if a CI URL is definitively unreachable (hard failure)."""
    verdict = url_status.get("verdict")
    if verdict:
        return verdict == HARD_FAILURE
    if url_status.get("status_code") in (404, 410):
        return True
    error = url_status.get("error")
    return isinstance(error, str) and "Invalid URL format" in error


def _codemeta_ci_urls(somef_data: Dict):
    """CI URLs declared in codemeta.json (contIntegration / continuousIntegration).

    SoMEF does not always surface the codemeta continuous-integration field under
    the ``continuous_integration`` category, so fall back to reading the
    codemeta.json file directly. A list value is flattened.
    """
    urls = []
    entries = somef_data.get("continuous_integration")
    if isinstance(entries, list):
        for entry in entries:
            source = str(entry.get("source", ""))
            technique = entry.get("technique", "")
            if "codemeta.json" in source.lower() or (
                    technique == "code_parser" and "codemeta" in source.lower()):
                value = (entry.get("result") or {}).get("value")
                if isinstance(value, str):
                    urls.append(value)
                elif isinstance(value, list):
                    urls.extend(v for v in value if isinstance(v, str))

    if urls:
        return urls

    codemeta_url = find_source_url(somef_data, "codemeta.json", codemeta_root_only=True)
    if codemeta_url:
        text = fetch_text(codemeta_url)
        if text:
            try:
                data = json.loads(text)
            except (json.JSONDecodeError, ValueError):
                data = {}
            for key in ("continuousIntegration", "contIntegration", "codemeta:contIntegration"):
                value = data.get(key)
                if isinstance(value, str) and value.startswith(("http://", "https://")):
                    urls.append(value)
                elif isinstance(value, dict) and isinstance(value.get("url"), str):
                    urls.append(value["url"])
                elif isinstance(value, list):
                    urls.extend(v for v in value if isinstance(v, str))

    return urls


def detect_ci_404_pitfall(somef_data: Dict, file_name: str) -> Dict:
    """
    Detect when codemeta.json continuous integration link points to a dead end.
    """
    result = {
        "has_pitfall": False,
        "file_name": file_name,
        "ci_url": None,
        "source": None,
        "status_code": None,
        "error": None,
        "check_method": None,
        "api_status": None,
        "workflow_state": None,
    }

    for ci_url in _codemeta_ci_urls(somef_data):
        url_status = check_ci_url_status(ci_url)

        if _is_unreachable(url_status):
            result["has_pitfall"] = True
            result["ci_url"] = ci_url
            result["source"] = "codemeta.json"
            result["status_code"] = url_status.get("status_code")
            result["error"] = url_status.get("error")
            result["check_method"] = url_status.get("check_method")
            result["api_status"] = url_status.get("api_status")
            result["workflow_state"] = url_status.get("workflow_state")
            break

    return result
