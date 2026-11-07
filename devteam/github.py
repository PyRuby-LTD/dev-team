"""The pull request lookups the harness makes with gh, run in the checkout so gh finds the product's repository."""
import json
import subprocess

TIMEOUT = 60


class GitHubError(Exception):
    pass


def _gh(checkout, *args):
    call = "gh " + " ".join(args)
    try:
        result = subprocess.run(["gh", *args], cwd=checkout, capture_output=True, text=True, errors="replace",
                                timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        raise GitHubError(f"{call}: timed out after {TIMEOUT} seconds") from None
    except OSError as exc:
        raise GitHubError(f"{call}: {exc}") from None
    if result.returncode:
        raise GitHubError(f"{call}: exit {result.returncode}: {result.stderr.strip()}")
    return call, result.stdout


def state(checkout, number):
    """OPEN, CLOSED or MERGED."""
    call, out = _gh(checkout, "pr", "view", str(number), "--json", "state")
    try:
        data = json.loads(out)
        if not isinstance(data, dict) or data.get("state") not in ("OPEN", "CLOSED", "MERGED"):
            raise ValueError("expected state OPEN, CLOSED or MERGED")
    except ValueError as exc:
        raise GitHubError(f"{call}: invalid JSON response: {exc}") from None
    return data["state"]


def _pages(checkout, endpoint):
    # gh --paginate prints one JSON array per page, back to back.
    call, out = _gh(checkout, "api", endpoint, "--paginate")
    decoder = json.JSONDecoder()
    remaining, entries = out.strip(), []
    try:
        while remaining:
            page, end = decoder.raw_decode(remaining)
            if not isinstance(page, list) or not all(isinstance(entry, dict) for entry in page):
                raise ValueError("expected an array of objects")
            entries.extend(page)
            remaining = remaining[end:].lstrip()
    except ValueError as exc:
        raise GitHubError(f"{call}: invalid JSON response: {exc}") from None
    return entries


def _author(entry):
    user = entry.get("user")
    return str(user.get("login") or "unknown") if isinstance(user, dict) else "unknown"


def _body(entry):
    body = entry.get("body")
    return body if isinstance(body, str) else ""


def comments(checkout, number):
    """Every submitted review, inline comment and conversation comment on the pull request, oldest kind first."""
    # Not an f-string: gh fills in {owner} and {repo} from the checkout's remote.
    repo = "repos/{owner}/{repo}"
    found = []
    for review in _pages(checkout, f"{repo}/pulls/{number}/reviews"):
        if review.get("state") != "PENDING" and review.get("submitted_at") and _body(review):
            found.append({"kind": "review", "author": _author(review), "state": str(review.get("state")),
                          "body": _body(review)})
    for comment in _pages(checkout, f"{repo}/pulls/{number}/comments"):
        location = str(comment.get("path") or "")
        if comment.get("subject_type") != "file":
            if comment.get("line") is not None:
                location += f" line {comment['line']}"
            elif comment.get("original_line") is not None:
                location += f" line {comment['original_line']} (outdated)"
        found.append({"kind": "inline", "author": _author(comment), "location": location, "body": _body(comment)})
    for comment in _pages(checkout, f"{repo}/issues/{number}/comments"):
        found.append({"kind": "conversation", "author": _author(comment), "body": _body(comment)})
    return found
