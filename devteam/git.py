"""The git operations the harness relies on: the backlog branch and per-item code branches."""
import subprocess
from pathlib import Path

BACKLOG_BRANCH = "devteam-backlog"
BACKLOG_DIR = "backlog"


class GitError(Exception):
    pass


def run(directory, *args):
    return subprocess.run(["git", "-C", str(directory), *args], capture_output=True, text=True)


def must(directory, *args):
    out = run(directory, *args)
    if out.returncode:
        raise GitError(f"git {' '.join(args)}: {out.stderr.strip() or out.stdout.strip()}")
    return out.stdout.strip()


def checkout(directory):
    """The repository's main working tree, even when asked from inside the backlog worktree."""
    out = run(directory, "worktree", "list", "--porcelain")
    if out.returncode or not out.stdout.startswith("worktree "):
        return None
    return Path(out.stdout.splitlines()[0].removeprefix("worktree "))


def current_branch(directory):
    return run(directory, "symbolic-ref", "--quiet", "--short", "HEAD").stdout.strip() or None


def has_ref(directory, ref):
    return run(directory, "rev-parse", "--verify", "--quiet", ref).returncode == 0


def clean(directory):
    return must(directory, "status", "--porcelain") == ""


def base_of(directory, branch):
    return run(directory, "config", "--get", f"branch.{branch}.base").stdout.strip() or None


def fetch(directory, remote):
    must(directory, "fetch", remote)


def fast_forward(directory, branch, remote_ref):
    """Check ancestry before switching; an ahead-only branch keeps its commits."""
    for ref in (f"refs/heads/{branch}", f"refs/remotes/{remote_ref}"):
        if not has_ref(directory, ref):
            raise GitError(f"missing ref {ref}")
    local = f"refs/heads/{branch}"
    remote = f"refs/remotes/{remote_ref}"
    for ancestor, descendant in ((local, remote), (remote, local)):
        result = run(directory, "merge-base", "--is-ancestor", ancestor, descendant)
        if result.returncode == 0:
            break
        if result.returncode != 1:
            raise GitError(result.stderr.strip() or result.stdout.strip())
    else:
        raise GitError(f"base branch {branch} has diverged from {remote_ref}")
    must(directory, "switch", "-q", branch)
    must(directory, "merge", "--ff-only", remote)


def commit_all(directory, message, *paths):
    """Commit everything, or just the given paths; returns False when nothing changed."""
    must(directory, "add", "-A", "--", *(paths or (".",)))
    if run(directory, "diff", "--cached", "--quiet", "--", *(paths or (".",))).returncode == 0:
        return False
    must(directory, "commit", "-q", "-m", message, "--", *(paths or (".",)))
    return True


def ensure_backlog(top):
    """Check out the backlog branch at backlog/, creating the branch if it does not exist anywhere."""
    path = Path(top) / BACKLOG_DIR
    if (path / ".git").exists():
        return path
    if path.exists() and any(path.iterdir()):
        raise GitError(f"{path} exists but is not the {BACKLOG_BRANCH} worktree")
    common = Path(top, must(top, "rev-parse", "--git-common-dir"))
    exclude = common / "info" / "exclude"
    exclude.parent.mkdir(exist_ok=True)
    existing = exclude.read_text() if exclude.exists() else ""
    if f"/{BACKLOG_DIR}/" not in existing.splitlines():
        exclude.write_text(existing + ("" if existing.endswith("\n") or not existing else "\n") + f"/{BACKLOG_DIR}/\n")
    must(top, "worktree", "prune")
    if has_ref(top, f"refs/heads/{BACKLOG_BRANCH}"):
        must(top, "worktree", "add", str(path), BACKLOG_BRANCH)
    elif has_ref(top, f"refs/remotes/origin/{BACKLOG_BRANCH}"):
        must(top, "worktree", "add", "-b", BACKLOG_BRANCH, str(path), f"origin/{BACKLOG_BRANCH}")
    else:
        must(top, "worktree", "add", "--orphan", "-b", BACKLOG_BRANCH, str(path))
        (path / ".gitignore").write_text("log/\n")
        commit_all(path, "Start the backlog")
    return path
