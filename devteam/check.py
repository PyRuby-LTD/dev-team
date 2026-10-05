"""The project's own check: the Makefile target whose result the team trusts."""
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .config import ROOT

TAIL_LINES = 60


@dataclass
class Check:
    command: list
    one: str
    timeout: int


def load(path=None):
    spec = tomllib.loads((path or ROOT / "config" / "roles.toml").read_text())["check"]
    return Check(list(spec["command"]), spec["one"], spec.get("timeout", 1800))


def run(directory, name=None, log=None, config=None):
    """Run the whole check, or one named test; returns (exit code, combined output)."""
    config = config or load()
    argv = config.command + ([config.one.format(name=name)] if name else [])
    try:
        proc = subprocess.run(argv, cwd=directory, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, errors="replace", timeout=config.timeout)
        code, output = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired as exc:
        partial = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        code, output = 124, partial + f"\ntimed out after {config.timeout} seconds\n"
    except OSError as exc:
        code, output = 127, f"could not start {argv[0]}: {exc}\n"
    if log is not None:
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(f"# {' '.join(argv)}\n# cwd: {directory}\n# exit {code}\n\n{output}")
    return code, output


def tail(output, lines=TAIL_LINES):
    kept = output.rstrip("\n").splitlines()
    if len(kept) <= lines:
        return "\n".join(kept)
    return f"... {len(kept) - lines} earlier lines omitted ...\n" + "\n".join(kept[-lines:])


def summary(code, output, command, lines=TAIL_LINES):
    verdict = "Passed" if code == 0 else f"FAILED (exit {code})"
    return f"{verdict}: `{command}`\n\n```text\n{tail(output, lines)}\n```\n"
