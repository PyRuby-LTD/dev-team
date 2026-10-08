"""Mask machine paths in Markdown records and newly committed backlog text."""
import difflib
import os
import re
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from . import config, git


class PathGuard:
    def __init__(self, checkout=None):
        self.checkout = str(checkout) if checkout is not None else None
        values = [self.checkout, str(config.ROOT), sys.executable]
        values.extend(value for value in (sys.prefix, sys.base_prefix)
                      if len(Path(value).parts) >= 3 and value != "/usr/local")
        literals = sorted({value for value in values if value}, key=len, reverse=True)
        paths = [re.escape(value) + r"(?=$|/|[^A-Za-z0-9._-])" for value in literals]
        paths.extend([r"/(?:home|Users|root)/[A-Za-z0-9._-]+", r"/tmp/pytest-of-[A-Za-z0-9._-]+"])
        self.pattern = re.compile(r"(?:^|(?<=file://)|(?<=[^A-Za-z0-9._/-]))(?:" + "|".join(paths) + ")")

    def mask(self, text, selected=None):
        lines = text.splitlines(keepends=True)
        tripped = []
        for index, line in enumerate(lines):
            if selected is not None and index not in selected:
                continue
            original = line
            while match := self.pattern.search(line):
                start = match.start()
                end = match.end()
                while end < len(line) and re.match(r"[A-Za-z0-9._/-]", line[end]):
                    end += 1
                path = line[start:end]
                replacement = "<path>"
                if self.checkout and (path == self.checkout or path.startswith(self.checkout + "/")):
                    replacement = path[len(self.checkout):].lstrip("/") or "."
                line = line[:start] + replacement + line[end:]
            if line != original:
                tripped.append(index + 1)
                lines[index] = line
        return "".join(lines), tripped

    def __call__(self, root, notice):
        # Include staged changes, unstaged changes and untracked, non-ignored files.
        changed = git.run(root, "diff", "--name-only", "--no-renames", "-z", "HEAD")
        if changed.returncode:
            # An unborn branch has no HEAD; all tracked files are new.
            git.must(root, "rev-parse", "--git-dir")
            if git.has_ref(root, "HEAD"):
                raise git.GitError(changed.stderr.strip())
            changed = git.run(root, "ls-files", "-z", "--cached")
        untracked = git.run(root, "ls-files", "-z", "--others", "--exclude-standard")
        names = set(changed.stdout.split("\0")) | set(untracked.stdout.split("\0"))
        for name in sorted(names - {""}):
            path = root / name
            if not path.is_file() or path.is_symlink():
                continue
            try:
                text = path.read_bytes().decode("utf-8")
            except UnicodeError:
                continue  # Named gap: binary files are not inspected.
            old = subprocess.run(["git", "-C", str(root), "show", f"HEAD:{name}"], capture_output=True)
            before = old.stdout.decode("utf-8", errors="replace").splitlines(keepends=True) if old.returncode == 0 else []
            lines = text.splitlines(keepends=True)
            selected = set()
            for tag, _, _, start, end in difflib.SequenceMatcher(None, before, lines, autojunk=False).get_opcodes():
                if tag in {"insert", "replace"}:
                    selected.update(range(start, end))
            item = path.suffix == ".md" and Path(name).parts[0] in {"epics", "stories", "tasks", "bugs", "requests"}
            if item and lines and lines[0].rstrip("\r\n") == "---":
                end = next((i for i in range(1, len(lines)) if lines[i].rstrip("\r\n") == "---"), None)
                if end is not None:
                    selected.difference_update(range(end + 1))
            masked, numbers = self.mask(text, selected)
            if not numbers:
                continue
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
            saved = (root / "log" / path.stem / f"unmasked-{stamp}.md" if item else
                     root / "log" / "unmasked" / f"{stamp}-{name.replace('/', '__')}")
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(text.encode("utf-8"))
            path.write_bytes(masked.encode("utf-8"))
            base = Path(self.checkout) if self.checkout else root.parent
            notice(f"{name}: masked lines {', '.join(map(str, numbers))}; original saved to {os.path.relpath(saved, base)}")
