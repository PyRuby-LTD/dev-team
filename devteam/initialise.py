"""Quick-start an empty product; leave existing code and commits to its owner."""
import re
import shutil
from pathlib import Path

from . import git

GITHUB_ORIGIN = re.compile(
    r"(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
)
PLACEHOLDER = '''.PHONY: regression

regression:
	@echo "regression unimplemented: wire up the product's checks" >&2
	@exit 1
'''


def github_origin(url: str) -> bool:
    return GITHUB_ORIGIN.fullmatch(url) is not None


def has_regression(text: str) -> bool:
    # Look at target declarations, not recipes, comments or variable assignments.
    for line in text.splitlines():
        if not line or line[0].isspace():
            continue
        targets, separator, recipe = line.split("#", 1)[0].partition(":")
        if separator and "=" not in targets and not recipe.startswith("="):
            if "regression" in targets.split():
                return True
    return False


def quick_start(top: Path) -> bool:
    if not git.has_ref(top, "HEAD"):
        return True
    commits = git.must(top, "rev-list", "HEAD").splitlines()
    return len(commits) == 1 and git.must(
        top, "diff-tree", "--root", "--no-commit-id", "--name-only", "-r", "HEAD"
    ).splitlines() == ["Makefile"]


def initialise(directory: Path):
    top = git.checkout(directory)
    if top is None:
        raise git.GitError("init requires a Git repository")
    branch = git.current_branch(top)
    if branch is None:
        raise git.GitError("init requires a current branch; HEAD is detached")
    if branch.startswith("devteam/"):
        raise git.GitError(f"init cannot run on an item branch: {branch}")
    origin = git.run(top, "config", "--get", "remote.origin.url").stdout.strip()
    if not github_origin(origin):
        raise git.GitError("init requires a GitHub origin (host exactly github.com)")

    for command in ("claude", "codex", "gh"):
        if shutil.which(command) is None:
            print(f"WARNING: {command} is missing from PATH")

    makefile = top / "Makefile"
    created = not makefile.exists()
    if created:
        makefile.write_text(PLACEHOLDER)
    elif not has_regression(makefile.read_text()):
        print("WARNING: Makefile has no regression target; wire up make regression and commit before dev-team tui")

    if quick_start(top):
        if not git.has_ref(top, "HEAD"):
            git.commit_all(top, "Set up product regression target", "Makefile")
            print(f"Committed Makefile on {branch}")
        head = git.must(top, "rev-parse", "HEAD")
        remote = git.run(top, "ls-remote", "--exit-code", "origin", f"refs/heads/{branch}")
        if remote.returncode == 2:
            git.must(top, "push", "-u", "origin", branch)
            print(f"Pushed {branch} to origin")
        elif remote.returncode:
            raise git.GitError(remote.stderr.strip() or remote.stdout.strip())
        elif remote.stdout.split()[0] == head:
            print(f"Product is already set up on {branch}")
        else:
            print(f"WARNING: origin already has {branch} at a different commit; nothing pushed")
    elif created:
        print("Wire up make regression and commit before running dev-team tui")

    backlog = git.ensure_backlog(top)
    print(f"Backlog is set up at {backlog}")
