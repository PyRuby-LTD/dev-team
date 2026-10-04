import shlex
import subprocess
from pathlib import Path

from .config import Role


def build_argv(role: Role, prompt: str, cwd: Path, extra_dir: Path) -> list[str]:
    brief = role.brief()
    # An engine with no system-prompt flag still needs the brief, so it leads the prompt.
    if not any("{brief}" in arg for arg in role.command):
        prompt = brief + "\n\n" + prompt
    values = {
        "prompt": prompt,
        "model": role.model,
        "brief": brief,
        "cwd": str(cwd),
        "extra_dir": str(extra_dir),
        "permission": role.permission,
        "max_turns": str(role.max_turns),
    }
    return [arg.format_map(values) if "{" in arg else arg for arg in role.command]


def run(role: Role, prompt: str, cwd: Path, extra_dir: Path, log: Path) -> tuple[int, str]:
    """Invoke the role's CLI, keep the transcript in log, and return (exit code, reply)."""
    argv = build_argv(role, prompt, cwd, extra_dir)
    header = f"# {role.name} via {role.engine} ({role.model})\n# cwd: {cwd}\n# {shlex.join(argv)}\n\n"
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    except OSError as exc:
        log.write_text(header + f"could not start {argv[0]}: {exc}\n")
        return 127, ""
    log.write_text(header + proc.stdout + ("\n# stderr\n" + proc.stderr if proc.stderr else ""))
    return proc.returncode, proc.stdout
