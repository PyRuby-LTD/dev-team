"""The git operations the harness relies on: the backlog branch and per-item code branches."""
import json
import re
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


def pushed_head(directory, branch):
    return run(directory, "config", "--get", f"branch.{branch}.pushed").stdout.strip() or None


def remote_head(directory, branch):
    ref = f"refs/remotes/origin/{branch}"
    return must(directory, "rev-parse", ref) if has_ref(directory, ref) else None


def check_foreign(directory, branch):
    """Accounted-for remote history and locally incorporated commits are safe to rewrite."""
    remote = remote_head(directory, branch)
    if remote is None:
        return None
    exclusions = [branch]
    recorded = pushed_head(directory, branch)
    if recorded:
        exclusions.append(recorded)
    foreign = must(directory, "rev-list", "--oneline", remote, "--not", *exclusions)
    if foreign:
        raise GitError(f"the remote branch has foreign commits: {foreign}")
    return remote


def push_branch(directory, branch):
    must(directory, "fetch", "--prune", "origin")
    remote = check_foreign(directory, branch)
    recorded = pushed_head(directory, branch)
    if remote != recorded and remote is not None:
        raise GitError(f"the remote branch moved from its recorded head: {remote}")
    # An empty expectation also protects a first push against a concurrent creation.
    must(directory, "push", "-q", "-u", f"--force-with-lease=refs/heads/{branch}:{recorded or ''}",
         "origin", branch)
    must(directory, "config", f"branch.{branch}.pushed", must(directory, "rev-parse", branch))


def merging(directory):
    return has_ref(directory, "MERGE_HEAD")


def conflicted_files(directory):
    return must(directory, "diff", "--name-only", "--diff-filter=U", "-z").strip('\0').split('\0')


def finish_merge(directory, files):
    for name in files:
        path = Path(directory) / name
        if path.is_file() and re.search(rb"^(?:<{7,}|={7,}|>{7,}|\|{7,})(?: |\r?$)", path.read_bytes(), re.MULTILINE):
            raise GitError(f"conflict markers remain in {name}")
    must(directory, "add", "-A")
    must(directory, "commit", "-q", "--no-edit")


def sync_branch(directory, branch, base):
    """Rebase once, falling back to a single merge for conflict resolution."""
    remote = f"refs/remotes/origin/{base}"
    must(directory, "fetch", "--prune", "origin")
    if not has_ref(directory, remote):
        raise GitError(f"missing ref {remote}")
    accounted = check_foreign(directory, branch)
    if accounted:
        must(directory, "config", f"branch.{branch}.pushed", accounted)
    must(directory, "switch", "-q", branch)
    if run(directory, "merge-base", "--is-ancestor", remote, branch).returncode == 0:
        return "completed"
    merges = must(directory, "rev-list", "--first-parent", "--merges", f"{remote}..{branch}").splitlines()
    merged_base = any(
        run(directory, "merge-base", "--is-ancestor", parent, remote).returncode == 0
        for commit in merges for parent in must(directory, "rev-list", "--parents", "-n", "1", commit).split()[2:])
    if not merged_base:
        if run(directory, "rebase", remote).returncode == 0:
            return "completed"
        must(directory, "rebase", "--abort")
    result = run(directory, "merge", "--no-commit", "--no-ff", remote)
    files = [name for name in conflicted_files(directory) if name]
    if result.returncode and not files:
        raise GitError(result.stderr.strip() or result.stdout.strip())
    if files:
        must(directory, "config", f"branch.{branch}.conflicts", json.dumps(files))
        return "conflicted"
    finish_merge(directory, [])
    return "completed"
